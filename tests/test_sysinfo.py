import sysinfo


def test_snapshot_has_cpu_and_ram():
    snap = sysinfo.snapshot()
    assert 0 <= snap["cpu"] <= 100
    assert 0 < snap["ram"] <= 100


def test_gpu_is_optional(monkeypatch):
    monkeypatch.setattr(sysinfo, "_nvml", lambda: None)
    sysinfo._handle = None
    snap = sysinfo.snapshot()
    assert snap["gpu"] is None and snap["gpu_name"] == ""


def test_gpu_reads_nvml_when_present():
    gpu = sysinfo.gpu()
    if gpu is None:
        return                      # no NVIDIA card here; nothing to assert
    assert 0 <= gpu["load"] <= 100 and gpu["name"]


def test_the_link_is_how_long_the_internet_takes_to_answer(monkeypatch):
    asked = []
    monkeypatch.setattr(sysinfo, "_connect_ms", lambda: asked.append(1) or 23)
    monkeypatch.setattr(sysinfo, "_link", {"at": -1e9, "ms": None})
    assert sysinfo.link_ms(now=100.0) == 23
    assert sysinfo.link_ms(now=105.0) == 23 and len(asked) == 1      # not asked again so soon
    monkeypatch.setattr(sysinfo, "_connect_ms", lambda: None)
    assert sysinfo.link_ms(now=100.0 + sysinfo.LINK_EVERY) is None     # and none when it is down


def test_the_snapshot_carries_the_link_and_the_card_s_heat(monkeypatch):
    monkeypatch.setattr(sysinfo, "gpu", lambda: {"load": 3, "name": "RTX", "vram": 2.1, "temp": 51})
    monkeypatch.setattr(sysinfo, "link_ms", lambda: 18)
    snap = sysinfo.snapshot()
    assert snap["gpu_temp"] == 51 and snap["link_ms"] == 18
