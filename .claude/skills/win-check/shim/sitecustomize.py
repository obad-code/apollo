import ctypes, sys, types
from unittest import mock
if not hasattr(ctypes, "windll"):
    ctypes.windll = mock.MagicMock()
    ctypes.WinDLL = mock.MagicMock()
    ctypes.WINFUNCTYPE = ctypes.CFUNCTYPE
    ctypes.WinError = lambda *a, **k: OSError(*a)
    ctypes.get_last_error = lambda: 0
    ctypes.FormatError = lambda *a: ""
for name in ("sounddevice", "keyboard", "pyttsx3", "winreg", "webview", "pycaw", "comtypes", "winsound", "pystray", "piper"):
    if name not in sys.modules:
        try:
            __import__(name)
        except Exception:
            sys.modules[name] = mock.MagicMock()
