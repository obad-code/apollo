"""Away mode: while you are out of the house the PC stays up with Claude
open, so you can reach it from your phone; while you are home it may rest.

You have left when you say so ("أنا طالع", the going_out tool), or when your
phone has been off the home Wi-Fi for a while (phone.py) and nobody is at
the keyboard - a phone dropping off the Wi-Fi while you type is not you
leaving. You are back when you touch the PC, or when the phone comes home
after it was gone.

`Keeper` does the two things away mode is for. It asks Windows not to sleep
(SetThreadExecutionState, which holds only while the thread that asked is
alive, so it is called from Apollo's watcher thread, which lives as long as
Apollo), and opens the Claude app if it is not already open. Back home it
hands sleep back to the power plan. The screen may still turn off either
way; only sleep is held off.
"""

import ctypes
import logging
import os
import subprocess

log = logging.getLogger("apollo.away")

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
# The Claude desktop app, as Windows knows it (Get-StartApps).
CLAUDE_APP = "Claude_pzs8sxrjxfjjc!Claude"


class Away:
    # How long after you asked a touch still counts as the asking: letting go
    # of the chord you held to say it.
    GRACE = 1.0

    def __init__(self, gone_after=15 * 60, quiet_after=10 * 60):
        self.gone_after = gone_after
        self.quiet_after = quiet_after
        self.away = False
        self.since = None           # when you went
        self._phone_last = None     # when the phone was last on the Wi-Fi
        self._phone_gone = False    # ...and whether it has since been off it a while

    def leaving(self, now):
        """You said you are going out. True if that changed anything."""
        changed = not self.away
        self.away = True
        self.since = now
        self._phone_gone = False    # only an absence from now on counts
        return changed

    def update(self, now, idle, phone=None):
        """`idle` is seconds since you last touched the PC; `phone` is whether
        it is on the Wi-Fi now, or None when there is no phone to go by.
        True if you left or came back."""
        before = self.away
        returned = gone = False
        if phone is True:
            returned = self.away and self._phone_gone
            self._phone_last = now
            self._phone_gone = False
        elif phone is False:
            if self._phone_last is None:
                self._phone_last = now
            if now - self._phone_last >= self.gone_after:
                self._phone_gone = gone = True
        if self.away and (returned or now - idle > self.since + self.GRACE):
            self.away = False
        elif not self.away and gone and idle >= self.quiet_after:
            self.away = True
            self.since = now
        return self.away != before


def _set_state(flags):
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ctypes.c_uint(flags))
    except (AttributeError, OSError):
        pass


def claude_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq claude.exe", "/NH"],
                             capture_output=True, text=True, timeout=5,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return True                 # cannot tell: do not open a second one
    return "claude.exe" in out.stdout.lower()


def open_claude():
    try:
        os.startfile("shell:AppsFolder\\" + CLAUDE_APP)
    except OSError as e:
        log.info("could not open Claude: %s", e)


class Keeper:
    def __init__(self, set_state=_set_state, running=claude_running, launch=open_claude):
        self._set = set_state
        self._running = running
        self._launch = launch

    def apply(self, away):
        if away:
            self._set(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
            if not self._running():
                self._launch()
            log.info("away: the PC stays up, Claude is open")
        else:
            self._set(ES_CONTINUOUS)
            log.info("home: the PC may rest")
