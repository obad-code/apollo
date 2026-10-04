import json

import qfixes


def test_q_looks_suggests_and_learns_the_users_taste(tmp_path):
    path = str(tmp_path / "q.json")
    seen = []
    rows = [{"title": "Bigger clock", "area": "top left", "detail": "x"},
            {"title": "Softer glow", "area": "news", "detail": "y"}]
    new = qfixes.look(grab=lambda: b"jpg", ask=lambda pic, prompt: seen.append(prompt) or json.dumps(rows), path=path)
    assert [s["title"] for s in new] == ["Bigger clock", "Softer glow"]
    assert not qfixes.due(path=path)
    filed = []
    r = qfixes.send(new[0]["id"], file_issue=lambda t, b: filed.append((t, b)) or {"url": "u", "number": 7}, path=path)
    assert r["number"] == 7 and filed[0][0] == "UI: Bigger clock"
    qfixes.no(new[1]["id"], path=path)
    qfixes.look(grab=lambda: b"jpg", ask=lambda pic, prompt: seen.append(prompt) or "[]", path=path)
    assert "Bigger clock" in seen[-1] and "Softer glow" in seen[-1]     # what was sent and what was dropped
    assert qfixes.board(path=path)["new"] == 0


def test_pointing_at_something_files_it(tmp_path):
    path = str(tmp_path / "q.json")
    filed = []
    r = qfixes.report("the text is too small", {"selector": "#clock", "text": "17:19"},
                      file_issue=lambda t, b: filed.append(b) or {"url": "u", "number": 9}, path=path)
    assert r["ok"] and "#clock" in filed[0]
    assert not qfixes.report("", {}, file_issue=lambda t, b: {}, path=path)["ok"]
