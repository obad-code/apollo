"""Agents mode: the crew - a wheel of agents, the dashboard under it, an
agent brought forward with its live card, and the workflow map."""
import pathlib
import re

FULL = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"
HTML = (FULL / "index.html").read_text(encoding="utf-8")
APP = (FULL / "app.js").read_text(encoding="utf-8")


def section():
    agents = HTML[HTML.index('<section id="agents"'):]
    return agents[:agents.index("\n  </section>")]


def test_the_wheel_sits_over_the_board():
    agents = section()
    assert agents.index('id="crew-wheel"') < agents.index('id="crew-board"')
    for key in ("lyla", "theia", "moneypenny", "q"):
        assert f'id="agent-{key}" class="agent-card"' in agents


def test_every_agent_is_on_the_wheel_and_a_pick_brings_it_forward():
    assert "const AGENTS = ['LYLA', 'THEIA', 'MONEYPENNY', 'Q'];" in APP
    assert "onPick: (i) => focusAgent(AGENTS[i % AGENTS.length])" in APP
    assert "function focusAgent(key)" in APP and "function openMap(" in APP


def test_the_map_follows_the_focus_by_itself():
    assert re.search(r"crew\.timer = setTimeout\(\(\) => openMap\(key\), CrewView\.FOCUS_MS\);", APP)


def test_nothing_is_forward_until_you_pick():
    agents = section()
    assert 'id="crew-focus" class="crew-layer" hidden' in agents
    assert 'id="crew-map" class="crew-layer" hidden' in agents
