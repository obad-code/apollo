import emailer


def test_notify_is_silent_without_setup_and_never_raises(monkeypatch):
    monkeypatch.delenv("APOLLO_SMTP_USER", raising=False)
    monkeypatch.delenv("APOLLO_SMTP_PASSWORD", raising=False)
    assert emailer.notify("s", "t") is False
    monkeypatch.setenv("APOLLO_SMTP_USER", "me@example.com")
    monkeypatch.setenv("APOLLO_SMTP_PASSWORD", "secret")
    monkeypatch.setattr(emailer, "_deliver", lambda found, msg: (_ for _ in ()).throw(OSError("down")))
    assert emailer.notify("s", "t") is False


def test_a_picture_is_attached(tmp_path, monkeypatch):
    monkeypatch.setenv("APOLLO_SMTP_USER", "me@example.com")
    monkeypatch.setenv("APOLLO_SMTP_PASSWORD", "secret")
    png = tmp_path / "preview.png"
    png.write_bytes(b"\x89PNG fake")
    got = []
    monkeypatch.setattr(emailer, "_deliver", lambda found, msg: got.append(msg))
    assert emailer.notify("Short ready", "body", attachments=[str(png)]) is True
    parts = list(got[0].iter_attachments())
    assert len(parts) == 1 and parts[0].get_filename() == "preview.png"
