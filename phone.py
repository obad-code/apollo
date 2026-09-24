"""Whether your phone is on the home Wi-Fi - which is how Apollo tells you
have gone out (away.py).

The phone is named by its Wi-Fi address (its MAC, as it shows in the phone's
Wi-Fi settings for this network), its IP address, or both, saved as
APOLLO_PHONE. A phone that answers a ping is home; so is one whose address
is in the PC's ARP table, which is how a phone that sleeps through pings is
still found. If it is in neither, the local network is pinged through once
(no more than every few minutes) to wake the table, and asked again.

A phone asleep in a pocket in the next room can miss a check or two; away
mode waits for it to be gone a quarter of an hour before believing it.
"""

import logging
import os
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("apollo.phone")

IP = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")
MAC = re.compile(r"\b([0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5})\b")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def normalise(mac):
    return mac.lower().replace(":", "-")


def parse_arp(text):
    """`arp -a` -> {ip: mac}."""
    table = {}
    for line in str(text or "").splitlines():
        ip, mac = IP.search(line), MAC.search(line)
        if ip and mac:
            table[ip.group(1)] = normalise(mac.group(1))
    return table


def _ping(ip, wait_ms=800):
    try:
        out = subprocess.run(["ping", "-n", "1", "-w", str(wait_ms), ip], capture_output=True,
                             text=True, timeout=wait_ms / 1000 + 3, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0 and "ttl=" in out.stdout.lower()


def _arp():
    try:
        return subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5,
                              creationflags=NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _sweep():
    """Ping every address on this PC's /24 once, briefly, to fill the ARP table."""
    mine = re.search(r"Interface:\s*(\d+\.\d+\.\d+)\.\d+", _arp())
    if not mine:
        return
    prefix = mine.group(1)
    with ThreadPoolExecutor(max_workers=64) as pool:
        list(pool.map(lambda n: _ping(f"{prefix}.{n}", 300), range(1, 255)))


class Phone:
    def __init__(self, ident, ping=_ping, arp=_arp, sweep=_sweep, sweep_every=300):
        ident = str(ident or "")
        ip, mac = IP.search(ident), MAC.search(ident)
        self.ip = ip.group(1) if ip else None
        self.mac = normalise(mac.group(1)) if mac else None
        self._ping, self._arp, self._sweep = ping, arp, sweep
        self._sweep_every = sweep_every
        self._swept = None

    def seen(self):
        if self.ip and self._ping(self.ip):
            return True
        if not self.mac:
            return False
        if self.mac in parse_arp(self._arp()).values():
            return True
        now = time.monotonic()
        if self._swept is None or now - self._swept >= self._sweep_every:
            self._swept = now
            self._sweep()
            return self.mac in parse_arp(self._arp()).values()
        return False


def saved_ident():
    """APOLLO_PHONE, from the environment or where `setx` saved it."""
    value = os.environ.get("APOLLO_PHONE")
    if value:
        return value.strip()
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
            return str(winreg.QueryValueEx(handle, "APOLLO_PHONE")[0]).strip() or None
    except OSError:
        return None


class Watch:
    """Checks the phone once a minute on its own thread - a ping can take a
    second, and the watcher ticks 25 times one - and keeps the answer."""

    def __init__(self, phone, every=60.0):
        self._phone = phone
        self._every = every
        self._state = None
        self._stopping = threading.Event()

    def state(self):
        return self._state

    def start(self):
        threading.Thread(target=self._run, daemon=True, name="apollo-phone").start()
        return self

    def stop(self):
        self._stopping.set()

    def _run(self):
        while not self._stopping.is_set():
            try:
                self._state = bool(self._phone.seen())
            except Exception:  # noqa: BLE001 - unknown, not gone
                self._state = None
            self._stopping.wait(self._every)
