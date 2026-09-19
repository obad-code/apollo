"""What the machine is doing: CPU, memory, and the NVIDIA card if there is one.

NVML is read through ctypes rather than by running nvidia-smi: measured at
1.7 ms against about 80 ms for spawning the tool, and the display asks every
few seconds.
"""

import ctypes
import logging

import psutil

log = logging.getLogger("apollo.sysinfo")

_nvml_lib = None
_handle = None
_tried = False


class _Utilization(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


def _nvml():
    """The NVML library, loaded once. None on a machine without it."""
    global _nvml_lib, _tried
    if _tried:
        return _nvml_lib
    _tried = True
    for name in ("nvml.dll", r"C:\Windows\System32\nvml.dll", "libnvidia-ml.so.1"):
        try:
            library = ctypes.CDLL(name)
        except OSError:
            continue
        if library.nvmlInit_v2() == 0:
            _nvml_lib = library
            break
    return _nvml_lib


def gpu():
    """Load, memory and name for GPU 0, or None."""
    global _handle
    library = _nvml()
    if library is None:
        return None
    try:
        if _handle is None:
            handle = ctypes.c_void_p()
            if library.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(handle)) != 0:
                return None
            _handle = handle
        used = _Utilization()
        if library.nvmlDeviceGetUtilizationRates(_handle, ctypes.byref(used)) != 0:
            return None
        memory = (ctypes.c_ulonglong * 3)()
        library.nvmlDeviceGetMemoryInfo(_handle, ctypes.byref(memory))
        name = ctypes.create_string_buffer(96)
        library.nvmlDeviceGetName(_handle, name, 96)
        return {"load": int(used.gpu), "name": name.value.decode(errors="replace"),
                "vram": round(memory[2] / 1e9, 1), "vram_total": round(memory[0] / 1e9, 1)}
    except Exception:  # noqa: BLE001 - telemetry is never worth an exception
        return None


def snapshot():
    """One reading of the machine, for the display and the briefing."""
    card = gpu()
    return {"cpu": round(psutil.cpu_percent(interval=None)),
            "ram": round(psutil.virtual_memory().percent),
            "gpu": card["load"] if card else None,
            "gpu_name": card["name"] if card else "",
            "vram": card["vram"] if card else None}
