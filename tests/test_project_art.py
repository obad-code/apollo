import project_art


def test_a_project_without_a_picture_is_asked_for_once(tmp_path, monkeypatch):
    monkeypatch.setattr(project_art, "ART", str(tmp_path))
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    asked = []
    monkeypatch.setattr(project_art, "want", lambda name, about="": asked.append(name))
    snap = {"repos": [{"name": "obad-code/apollo", "about": "voice assistant"}], "folders": [], "sessions": []}
    project_art.decorate(snap)
    assert snap["repos"][0]["art"] == "" and asked == ["obad-code/apollo"]


def test_a_drawn_picture_is_found_by_name(tmp_path, monkeypatch):
    monkeypatch.setattr(project_art, "ART", str(tmp_path))
    (tmp_path / (project_art.slug("Apollo") + ".png")).write_bytes(b"x")
    assert project_art.src("Apollo") == f"art/{project_art.slug('Apollo')}.png"
