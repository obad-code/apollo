import myprojects


def test_your_projects_their_boards_and_theias_notes(tmp_path):
    root = str(tmp_path)
    a = myprojects.add("Apollo", "my voice assistant", root=root)
    assert myprojects.add("apollo", root=root)["id"] == a["id"]           # no twins
    myprojects.add("Nolock", root=root)
    assert [p["name"] for p in myprojects.all(root)][0] == "Nolock"        # newest touched first
    board = {"items": [{"type": "note", "text": "Ship v1 by Friday"}, {"type": "file", "name": "plan.pdf"}], "view": {}}
    myprojects.save_board(a["id"], board, "data:image/png;base64,AAAA", root=root)
    assert myprojects.board(a["id"], root)["items"][0]["text"] == "Ship v1 by Friday"
    asked = []
    notes = myprojects.review(a["id"], "", ask=lambda png, prompt: asked.append(prompt) or
                              "SUMMARY: On track.\nNEXT:\n- Write the tests\nQUESTION: What is v1?", root=root)
    assert notes["summary"] == "On track." and "Ship v1 by Friday" in asked[0] and "plan.pdf" in asked[0]
    assert myprojects.get(a["id"], root)["theia"]["seen"] is False
    myprojects.seen(a["id"], root)
    assert myprojects.get(a["id"], root)["theia"]["seen"] is True
    assert myprojects.remove(a["id"], root) and myprojects.get(a["id"], root) is None


def test_a_project_needs_a_name(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        myprojects.add("  ", root=str(tmp_path))
