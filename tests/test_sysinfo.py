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
