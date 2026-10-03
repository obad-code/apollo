"""Agents mode: each agent by its mark down the left, and a click on one
opens its process beside them - LYLA, THEIA, MONEYPENNY and Q."""
import pathlib
import re

FULL = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"
HTML = (FULL / "index.html").read_text(encoding="utf-8")
APP = (FULL / "app.js").read_text(encoding="utf-8")


def test_the_marks_sit_down_the_left_of_the_process():
    agents = HTML[HTML.index('<section id="agents"'):]
    agents = agents[:agents.index("</section>")]
    assert agents.index('id="agent-rail"') < agents.index('id="agent-stage"')
    for key in ("lyla", "theia", "moneypenny", "q"):
        assert f'id="agent-{key}" class="agent-card"' in agents


def test_every_agent_is_listed_and_a_click_opens_it():
    assert "const AGENTS = ['LYLA', 'THEIA', 'MONEYPENNY', 'Q'];" in APP
    assert re.search(r"\$\('agent-marks'\)\.addEventListener\('click'", APP)
    assert "function openAgent(key)" in APP


def test_nothing_is_open_until_you_pick():
    assert re.search(r"agentOpen: null,", APP)
    assert 'id="agent-pick"' in HTML
