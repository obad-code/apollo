from overlay_state import LISTENING, REST, RESULT, OverlayState, Spring, layout_for


def settle(spring, steps=400, dt=1 / 60):
    for _ in range(steps):
        spring.step(dt)
    return spring.value


def test_spring_reaches_its_target_without_overshooting():
    spring = Spring(0.0)
    spring.to(100.0)
    seen = []
    for _ in range(240):
        spring.step(1 / 60)
        seen.append(spring.value)
    assert max(seen) <= 100.6                       # no bounce past the target
    assert abs(seen[-1] - 100.0) < 0.5
    assert spring.resting


def test_spring_retargets_without_jumping():
    spring = Spring(0.0)
    spring.to(200.0)
    for _ in range(12):
        spring.step(1 / 60)
    midway = spring.value
    assert 0 < midway < 200
    spring.to(50.0)
    spring.step(1 / 60)
    assert abs(spring.value - midway) < 12          # continues, never restarts


def test_spring_is_frame_rate_independent():
    fast, slow = Spring(0.0), Spring(0.0)
    fast.to(100.0)
    slow.to(100.0)
    for _ in range(60):
        fast.step(1 / 60)
    for _ in range(20):
        slow.step(1 / 20)
    assert abs(fast.value - slow.value) < 3.0


def test_state_opens_and_closes_the_panel():
    state = OverlayState()
    assert state.state == REST and state.panel_open == 0.0
    state.set(LISTENING)
    for _ in range(120):
        state.step(1 / 60)
    assert state.panel_open > 0.98
    state.set(REST)
    for _ in range(120):
        state.step(1 / 60)
    assert state.panel_open < 0.02


def test_exits_are_quicker_than_entries():
    opening, closing = OverlayState(), OverlayState()
    opening.set(LISTENING)
    closing.set(LISTENING)
    for _ in range(200):
        closing.step(1 / 60)
    closing.set(REST)
    steps_open = steps_shut = 0
    while opening.panel_open < 0.9 and steps_open < 600:
        opening.step(1 / 60)
        steps_open += 1
    while closing.panel_open > 0.1 and steps_shut < 600:
        closing.step(1 / 60)
        steps_shut += 1
    assert steps_shut < steps_open


def test_panel_top_is_fixed_to_the_screen_edge():
    small = layout_for(LISTENING, content_height=0, sparkle_height=150)
    big = layout_for(RESULT, content_height=120, sparkle_height=150)
    assert small["panel_y"] == big["panel_y"]
    assert big["panel_h"] > small["panel_h"]
    assert big["window_h"] > small["window_h"]
    assert big["horizon_y"] == big["panel_y"] + big["panel_h"]
