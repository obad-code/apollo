"""The scanner: a file dropped on the display, read and judged.

Read, never run and never opened with its own program: every check here
looks at the file's bytes. What it looks for:

  what it is     by its first bytes, not its name - a program named
                 holiday.jpg is a program, and says so
  its name       a second extension hiding the real one (invoice.pdf.exe),
                 or a name turned backwards by a right-to-left mark
  a program      its sections (packed ones hide what they do), what it
                 imports (writing into other programs, watching keys,
                 downloading), and its signature - checked by Windows
  documents      Office macros and parts fetched from the internet, a PDF's
                 scripts and launch actions
  scripts        the commands malware runs: download-and-run, encoded
                 PowerShell, switching Defender off, deleting backups
  archives       programs and scripts inside, and entries it cannot read
  origin         the "mark of the web" Windows puts on a download
  Defender       Windows Defender's own scan of the file (MpCmdRun), told
                 not to remove anything - the verdict is yours

A report: {name, path, size, kind, ext, sha256, verdict, headline,
findings: [{level, text}], defender, signature, origin, urls, pe, lookup,
took}. verdict is "clean", "caution", "danger", or "error" when there was
no file to read. Nothing here raises.
"""

import hashlib
import math
import os
import re
import struct
import subprocess
import time
import urllib.parse
import zipfile

READ_MOST = 16 * 2**20          # the bytes the content checks look at
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

DANGER, CAUTION, INFO = "danger", "caution", "info"

# Extensions Windows runs rather than opens.
RUNNABLE = {".exe", ".scr", ".com", ".pif", ".bat", ".cmd", ".ps1", ".vbs", ".vbe", ".js", ".jse",
            ".wsf", ".wsh", ".hta", ".msi", ".msp", ".lnk", ".dll", ".cpl", ".jar", ".reg", ".sys"}
# ...and the ones a document or a picture has, which a program must not.
LOOKS_HARMLESS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".pdf", ".txt", ".doc", ".docx",
                  ".xls", ".xlsx", ".ppt", ".pptx", ".mp3", ".mp4", ".mov", ".avi", ".mkv", ".wav",
                  ".csv", ".rtf", ".zip", ".rar", ".7z"}
SCRIPTS = {".ps1", ".bat", ".cmd", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".hta", ".sh", ".py", ".reg"}

MAGIC = (
    (b"MZ", "program"), (b"%PDF", "pdf"), (b"PK\x03\x04", "zip"), (b"\xD0\xCF\x11\xE0", "ole"),
    (b"Rar!", "rar"), (b"7z\xBC\xAF\x27\x1C", "7z"), (b"\x89PNG", "image"), (b"\xFF\xD8\xFF", "image"),
    (b"GIF8", "image"), (b"\x4C\x00\x00\x00\x01\x14\x02\x00", "shortcut"), (b"\x7fELF", "elf"),
)


def _u16(data, at):
    return struct.unpack_from("<H", data, at)[0]


def _u32(data, at):
    return struct.unpack_from("<I", data, at)[0]


def entropy(data):
    """Bits a byte, 0-8: packed or encrypted content sits near 8."""
    if not data:
        return 0.0
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    total = len(data)
    return -sum(c / total * math.log2(c / total) for c in counts if c)


# -- a Windows program ------------------------------------------------------------

def parse_pe(data):
    """A PE's header, sections and imports - or None if it is not one."""
    try:
        if data[:2] != b"MZ":
            return None
        pe = _u32(data, 0x3C)
        if data[pe:pe + 4] != b"PE\0\0":
            return None
        coff = pe + 4
        count, stamp, optional_size, flags = (_u16(data, coff + 2), _u32(data, coff + 4),
                                              _u16(data, coff + 16), _u16(data, coff + 18))
        optional = coff + 20
        magic = _u16(data, optional)
        bits = 64 if magic == 0x20B else 32
        directories = optional + (112 if bits == 64 else 96)
        import_rva = _u32(data, directories + 8)
        signed_size = _u32(data, directories + 4 * 8 + 4)
        sections = []
        for n in range(min(count, 96)):
            at = optional + optional_size + n * 40
            name = data[at:at + 8].rstrip(b"\0").decode("ascii", "replace")
            vsize, vaddr, raw_size, raw_at = (_u32(data, at + 8), _u32(data, at + 12),
                                              _u32(data, at + 16), _u32(data, at + 20))
            chars = _u32(data, at + 36)
            sections.append({"name": name, "vaddr": vaddr, "vsize": vsize, "raw_at": raw_at,
                             "raw_size": raw_size, "exec": bool(chars & 0x20000000),
                             "entropy": round(entropy(data[raw_at:raw_at + raw_size]), 2)})

        def offset(rva):
            for s in sections:
                if s["vaddr"] <= rva < s["vaddr"] + max(s["vsize"], s["raw_size"]):
                    return rva - s["vaddr"] + s["raw_at"]
            return None

        def cstring(at, most=256):
            end = data.find(b"\0", at, at + most)
            return data[at:end if end >= 0 else at + most].decode("ascii", "replace")

        imports = {}
        at = offset(import_rva) if import_rva else None
        while at is not None and at + 20 <= len(data) and len(imports) < 256:
            lookup, name_rva, first = _u32(data, at), _u32(data, at + 12), _u32(data, at + 16)
            if not name_rva:
                break
            dll_at = offset(name_rva)
            dll = cstring(dll_at).lower() if dll_at is not None else "?"
            functions = []
            thunk = offset(lookup or first)
            step = 8 if bits == 64 else 4
            while thunk is not None and thunk + step <= len(data) and len(functions) < 2000:
                value = struct.unpack_from("<Q" if bits == 64 else "<I", data, thunk)[0]
                if not value:
                    break
                if not value >> (63 if bits == 64 else 31):         # by name, not ordinal
                    name_at = offset(value & 0x7FFFFFFF)
                    if name_at is not None:
                        functions.append(cstring(name_at + 2))
                thunk += step
            imports.setdefault(dll, []).extend(functions)
            at += 20
        return {"bits": bits, "dll": bool(flags & 0x2000), "built": stamp,
                "sections": [{k: s[k] for k in ("name", "entropy", "exec")} for s in sections],
                "imports": sum(len(f) for f in imports.values()), "libraries": sorted(imports),
                "signed_part": signed_size > 0, "_imports": imports}
    except (struct.error, IndexError, ValueError):
        return None


# What an import says a program can do, when several of a kind are there.
POWERS = (
    ({"virtualallocex", "writeprocessmemory", "createremotethread", "ntunmapviewofsection",
      "queueuserapc", "setthreadcontext"}, 2,
     "can write into other programs' memory and run code there - what injectors do"),
    ({"setwindowshookexa", "setwindowshookexw", "getasynckeystate"}, 2,
     "can watch the keys you press"),
    ({"urldownloadtofilea", "urldownloadtofilew"}, 1,
     "can download files from the internet by itself"),
)


def judge_imports(imports):
    names = {f.lower() for functions in imports.values() for f in functions}
    return [{"level": CAUTION, "text": f"It {text}."} for wanted, least, text in POWERS
            if len(names & wanted) >= least]


# -- documents, scripts, archives -------------------------------------------------

PDF_ACTIONS = ((rb"/Launch", DANGER, "The PDF would start a program when opened."),
               (rb"/JavaScript|/JS\b", CAUTION, "The PDF has scripts in it."),
               (rb"/OpenAction|/AA\b", CAUTION, "The PDF does something by itself as it opens."),
               (rb"/EmbeddedFile", CAUTION, "The PDF carries other files inside it."))

SCRIPT_SIGNS = (
    (r"downloadstring|downloadfile|invoke-webrequest|\biwr\b|start-bitstransfer|bitsadmin\s+/transfer"
     r"|certutil\s+-urlcache|urldownloadtofile", "downloads something"),
    (r"\biex\b|invoke-expression|frombase64string|-enc(odedcommand)?\s+[a-z0-9+/=]{20,}",
     "runs code it builds or decodes"),
    (r"add-mppreference|set-mppreference\s+-disable|disablerealtimemonitoring", "switches Defender off"),
    (r"vssadmin\s+delete|wbadmin\s+delete|bcdedit\s+/set", "deletes your backups"),
    (r"mshta\s|regsvr32\s+/i:http|rundll32\s+javascript", "runs code the way malware hides it"),
    (r"currentversion\\run\b|schtasks\s+/create", "makes itself start with Windows"),
)


def judge_script(text):
    found = [what for pattern, what in SCRIPT_SIGNS if re.search(pattern, text, re.IGNORECASE)]
    if not found:
        return []
    level = DANGER if len(found) >= 2 or "switches Defender off" in found else CAUTION
    return [{"level": level, "text": "The script " + ", and ".join(found) + "."}]


def judge_zip(path, ext):
    findings = []
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = [e.filename for e in entries]
            if any(e.flag_bits & 0x1 for e in entries):
                findings.append({"level": CAUTION, "text": "Some of what is inside is locked with a "
                                                           "password, so it cannot be checked."})
            if any(n.lower().endswith("vbaproject.bin") for n in names):
                findings.append({"level": CAUTION, "text": "The document has macros - code that runs "
                                                           "when it is opened with editing on."})
            office = any(n.startswith(("word/", "xl/", "ppt/")) for n in names)
            if office:
                for name in names:
                    if name.endswith(".rels"):
                        rels = archive.read(name)[:200000]
                        if b'TargetMode="External"' in rels and re.search(rb"https?://", rels):
                            findings.append({"level": CAUTION, "text": "The document fetches parts of "
                                                                       "itself from the internet when opened."})
                            break
            else:
                inside = [n for n in names if os.path.splitext(n.lower())[1] in RUNNABLE]
                if inside:
                    shown = ", ".join(os.path.basename(n) for n in inside[:3])
                    more = f" and {len(inside) - 3} more" if len(inside) > 3 else ""
                    findings.append({"level": CAUTION, "text": f"There are programs or scripts inside: "
                                                               f"{shown}{more}."})
    except (zipfile.BadZipFile, OSError, RuntimeError, ValueError):
        if ext not in (".docx", ".xlsx", ".pptx"):
            findings.append({"level": INFO, "text": "The archive could not be read inside."})
    return findings


URL = re.compile(rb"https?://[A-Za-z0-9._~:/?#@!$&'()*+,;=%-]{4,200}")


def urls_in(data, most=8):
    found = []
    for match in URL.finditer(data):
        url = match.group(0).decode("ascii", "replace").rstrip(".,;)'\"")
        if url not in found:
            found.append(url)
        if len(found) >= most:
            break
    return found


def origin(path):
    """Where Windows says a download came from (the mark of the web)."""
    try:
        with open(path + ":Zone.Identifier", encoding="utf-8", errors="replace") as stream:
            text = stream.read(4096)
    except OSError:
        return None
    host = re.search(r"HostUrl=(\S+)", text)
    if host:
        return urllib.parse.urlparse(host.group(1)).netloc or host.group(1)[:80]
    zone = re.search(r"ZoneId=(\d)", text)
    return "the internet" if zone and zone.group(1) in ("3", "4") else None


# -- Windows' own verdicts ------------------------------------------------------------

def check_signature(path):
    """Windows' check of a program's signature: {status, signer}. The path
    goes in through the environment, never into the command's text."""
    script = ("$s = Get-AuthenticodeSignature -LiteralPath $env:APOLLO_SCAN_PATH; "
              "$s.Status.ToString(); if ($s.SignerCertificate) { $s.SignerCertificate.Subject }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                             capture_output=True, text=True, timeout=30, creationflags=CREATE_NO_WINDOW,
                             env={**os.environ, "APOLLO_SCAN_PATH": path})
    except (OSError, subprocess.SubprocessError):
        return {"status": "Unknown", "signer": ""}
    lines = [line.strip() for line in out.stdout.splitlines() if line.strip()]
    return {"status": lines[0] if lines else "Unknown", "signer": lines[1] if len(lines) > 1 else ""}


def defender_path():
    platform = r"C:\ProgramData\Microsoft\Windows Defender\Platform"
    try:
        for version in sorted(os.listdir(platform), reverse=True):
            exe = os.path.join(platform, version, "MpCmdRun.exe")
            if os.path.isfile(exe):
                return exe
    except OSError:
        pass
    exe = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Windows Defender",
                       "MpCmdRun.exe")
    return exe if os.path.isfile(exe) else None


def parse_defender(code, out):
    threats = re.findall(r"Threat\s*:\s*(.+)", out or "")
    if code == 0 and not threats:
        return {"ran": True, "clean": True}
    if code == 2 or threats:
        return {"ran": True, "clean": False, "threat": threats[0].strip() if threats else "a threat"}
    last = [line.strip() for line in (out or "").splitlines() if line.strip()]
    return {"ran": False, "why": last[-1][:120] if last else f"it stopped with {code}"}


def run_defender(path, timeout=180):
    """Windows Defender's scan of this one file, told to remove nothing."""
    exe = defender_path()
    if not exe:
        return {"ran": False, "why": "Windows Defender is not on this PC"}
    try:
        out = subprocess.run([exe, "-Scan", "-ScanType", "3", "-File", path, "-DisableRemediation"],
                             capture_output=True, text=True, timeout=timeout,
                             creationflags=CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:
        return {"ran": False, "why": "Defender took too long"}
    except OSError as e:
        return {"ran": False, "why": str(e)[:120]}
    return parse_defender(out.returncode, out.stdout)


# -- the scan ---------------------------------------------------------------------------

KINDS = {"program": "Windows program", "pdf": "PDF document", "zip": "ZIP archive",
         "ole": "Old Office document or installer", "rar": "RAR archive", "7z": "7-Zip archive",
         "image": "Image", "shortcut": "Shortcut", "elf": "Linux program"}
OFFICE = {".docx": "Word document", ".docm": "Word document with macros", ".xlsx": "Excel workbook",
          ".xlsm": "Excel workbook with macros", ".pptx": "PowerPoint deck", ".pptm": "PowerPoint deck with macros"}


def _kind(magic, ext, data):
    if magic == "program":
        return "Windows program"
    if magic == "zip" and ext in OFFICE:
        return OFFICE[ext]
    if magic in KINDS:
        return KINDS[magic]
    if ext in SCRIPTS:
        return "Script"
    sample = data[:4096]
    if sample and sum(32 <= b < 127 or b in (9, 10, 13) for b in sample) / len(sample) > 0.9:
        return "Text"
    return "Unknown"


def scan(path, defender=run_defender, signature=check_signature, on_step=None):
    began = time.monotonic()
    path = str(path or "")
    name = os.path.basename(path)
    step = on_step or (lambda text: None)
    if not os.path.isfile(path):
        return {"name": name, "path": path, "verdict": "error", "findings": [],
                "headline": "That is not a file - drop a file, not a folder."}

    step("reading it")
    sha = hashlib.sha256()
    size = 0
    head = bytearray()
    try:
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(1 << 20)
                if not chunk:
                    break
                sha.update(chunk)
                size += len(chunk)
                if len(head) < READ_MOST:
                    head.extend(chunk[:READ_MOST - len(head)])
    except OSError as e:
        return {"name": name, "path": path, "verdict": "error", "findings": [],
                "headline": f"It could not be read: {e.strerror or e}"}
    data = bytes(head)
    ext = os.path.splitext(name.lower())[1]
    magic = next((kind for mark, kind in MAGIC if data.startswith(mark)), None)
    findings = []

    # The name.
    if "\u202e" in name:
        findings.append({"level": DANGER, "text": "The name is turned backwards to hide its real "
                                                  "extension."})
    stem_ext = os.path.splitext(os.path.splitext(name.lower())[0])[1]
    if ext in RUNNABLE and stem_ext in LOOKS_HARMLESS:
        findings.append({"level": DANGER, "text": f"It is named to look like {name[:-len(ext)]} "
                                                  f"but it is really a {ext} file."})
    if magic == "program" and ext in LOOKS_HARMLESS:
        findings.append({"level": DANGER, "text": f"It is a program pretending to be a {ext} file."})

    kind = _kind(magic, ext, data)
    pe = None
    sig = None
    if magic == "program":
        step("reading the program")
        parsed = parse_pe(data)
        if parsed:
            imports = parsed.pop("_imports")
            pe = parsed
            kind = "Windows program (DLL)" if parsed["dll"] else "Windows program"
            findings += judge_imports(imports)
            packed = [s["name"] for s in parsed["sections"]
                      if s["name"].upper().startswith("UPX") or (s["exec"] and s["entropy"] > 7.2)]
            if packed:
                findings.append({"level": CAUTION, "text": "It is packed - squeezed so what it does "
                                                           "cannot be read."})
    if magic == "program" or ext in (".msi", ".msp"):
        step("checking its signature")
        sig = signature(path)
        status = sig.get("status", "Unknown")
        if status == "Valid":
            who = re.search(r"CN=([^,]+)", sig.get("signer", ""))
            findings.append({"level": INFO, "text": f"Signed by {who.group(1) if who else 'its maker'}, "
                                                    "and the signature holds."})
        elif status == "HashMismatch":
            findings.append({"level": DANGER, "text": "It was changed after it was signed."})
        elif status == "NotSigned":
            findings.append({"level": CAUTION, "text": "It is not signed, so there is no telling who "
                                                       "made it."})
        else:
            findings.append({"level": CAUTION, "text": f"Its signature does not check out ({status})."})

    if magic == "pdf":
        for pattern, level, text in PDF_ACTIONS:
            if re.search(pattern, data):
                findings.append({"level": level, "text": text})
    if magic == "zip":
        step("looking inside")
        findings += judge_zip(path, ext)
    if magic == "ole" and (b"VBA" in data or b"_VBA_PROJECT" in data or b"M\0a\0c\0r\0o\0s" in data):
        findings.append({"level": CAUTION, "text": "The document has macros - code that runs when it "
                                                   "is opened with editing on."})
    if magic == "shortcut" and re.search(rb"p\0?o\0?w\0?e\0?r\0?s\0?h\0?e\0?l\0?l|c\0?m\0?d\0?\.\0?e\0?x\0?e",
                                         data, re.IGNORECASE):
        findings.append({"level": DANGER, "text": "The shortcut runs a command, not a file."})
    if ext in SCRIPTS or kind in ("Script", "Text"):
        findings += judge_script(data.decode("utf-8", "replace") + "\n"
                                 + data.decode("utf-16-le", "replace") if b"\0" in data[:200]
                                 else data.decode("utf-8", "replace"))

    came = origin(path)
    if came:
        findings.append({"level": INFO, "text": f"Downloaded from {came}."})

    step("Windows Defender is scanning it")
    verdict_of_defender = defender(path) or {"ran": False, "why": "no answer"}
    if verdict_of_defender.get("ran") and not verdict_of_defender.get("clean"):
        findings.insert(0, {"level": DANGER, "text": f"Windows Defender found "
                                                     f"{verdict_of_defender.get('threat', 'a threat')}."})

    levels = {f["level"] for f in findings}
    verdict = DANGER if DANGER in levels else CAUTION if CAUTION in levels else "clean"
    if verdict == DANGER:
        headline = "Don't open it. " + next(f["text"] for f in findings if f["level"] == DANGER)
    elif verdict == CAUTION:
        headline = "Be careful with it. " + next(f["text"] for f in findings if f["level"] == CAUTION)
    else:
        headline = "Nothing wrong found" + (" - and Windows Defender agrees."
                                            if verdict_of_defender.get("ran") else ".")
    order = {DANGER: 0, CAUTION: 1, INFO: 2}
    findings.sort(key=lambda f: order[f["level"]])
    digest = sha.hexdigest()
    return {"name": name, "path": path, "size": size, "kind": kind, "ext": ext, "sha256": digest,
            "verdict": verdict, "headline": headline, "findings": findings,
            "defender": verdict_of_defender, "signature": sig, "origin": came,
            "urls": urls_in(data), "pe": pe,
            "lookup": f"https://www.virustotal.com/gui/file/{digest}",
            "took": round(time.monotonic() - began, 1)}
