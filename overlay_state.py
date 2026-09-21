"""How the overlay moves, with no window in sight.

Two things live here because they are the parts worth testing: a spring, and
the small state machine that decides what is on screen. The painting is in
`overlay_paint`, the window is in `orb`.

The spring is critically damped on purpose. A bouncy panel is charming once
and irritating on the two hundredth turn of the day, and this one opens
directly under whatever you are reading. It is also retargetable: the panel's
height changes while it is still moving - live speech re-wraps on every word -
so the spring has to bend toward a new target from wherever it is, rather
than restarting and stuttering.
"""

import math

REST = "rest"
LISTENING = "listening"
SEARCHING = "searching"
RESULT = "result"
REPLY = "reply"

PANEL_W = 430            # the width the design gives the card
SPARKLE_H = 150
PANEL_MIN_H = 104          # the orb, your line and the caption under it


class Spring:
    """A critically damped spring: fast, and it never overshoots."""

    def __init__(self, value=0.0, response=0.34, damping=1.0):
        self.value = float(value)
        self.target = float(value)
        self.velocity = 0.0
        self.response = response          # seconds to "there"
        self.damping = damping

    def to(self, target):
        self.target = float(target)

    def step(self, dt):
        """Advance by `dt`, exactly.

        The closed-form solution for a critically damped spring, not a
        step-by-step integration: measured, the integrated version was stable
        at 60 and 30 frames a second and blew up to -8000 at 20, which is
        what a stalled frame looks like. This one cannot, at any step size.
        """
        dt = max(0.0, min(0.25, dt))
        if dt == 0.0 or self.resting:
            return self.value
        frequency = 2 * math.pi / max(0.0001, self.response)
        offset = self.value - self.target
        decay = math.exp(-frequency * dt)
        velocity_term = self.velocity + frequency * offset
        self.value = self.target + (offset + velocity_term * dt) * decay
        self.velocity = (self.velocity - velocity_term * frequency * dt) * decay
        if abs(self.target - self.value) < 0.05 and abs(self.velocity) < 0.5:
            self.value, self.velocity = self.target, 0.0
        return self.value

    @property
    def resting(self):
        return self.value == self.target and self.velocity == 0.0


class OverlayState:
    """Which state the overlay is in, and how far through the change it is."""

    OPEN_RESPONSE = 0.42        # entries are unhurried
    SHUT_RESPONSE = 0.24        # exits get out of the way

    def __init__(self):
        self.state = REST
        self._open = Spring(0.0, response=self.OPEN_RESPONSE)
        self._ring = Spring(1.0, response=0.3)

    def set(self, state):
        if state == self.state:
            return
        self.state = state
        panel = state in (LISTENING, SEARCHING, RESULT, REPLY)
        self._open.response = self.OPEN_RESPONSE if panel else self.SHUT_RESPONSE
        self._open.to(1.0 if panel else 0.0)
        self._ring.to(0.0 if panel else 1.0)

    def step(self, dt):
        self._open.step(dt)
        self._ring.step(dt)

    @property
    def panel_open(self):
        return max(0.0, min(1.0, self._open.value))

    @property
    def ring_fade(self):
        return max(0.0, min(1.0, self._ring.value))

    @property
    def resting(self):
        return self._open.resting and self._ring.resting


def layout_for(state, content_height=0, sparkle_height=SPARKLE_H, overhang=0):
    """Where everything sits, measured from the top of the window.

    `overhang` is how far above the screen's top edge the window starts - the
    resting ring hangs there - so the panel's top is always exactly the
    screen's edge, whatever the window is doing.
    """
    panel_h = max(PANEL_MIN_H, PANEL_MIN_H + max(0, content_height))
    return {"panel_y": overhang,
            "panel_h": panel_h,
            "panel_w": PANEL_W,
            "horizon_y": overhang + panel_h,
            "sparkle_y": overhang + panel_h,
            "sparkle_h": sparkle_height,
            "window_h": overhang + panel_h + sparkle_height}
