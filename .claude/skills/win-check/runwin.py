import sys, types
from unittest import mock
for name in ("winerror","win32api","win32gui","win32con","win32process","win32event","win32file","win32clipboard","pythoncom","pywintypes","win32com","win32com.client","winreg","pycaw","pycaw.pycaw","comtypes","comtypes.client","webview","pystray"):
    sys.modules.setdefault(name, mock.MagicMock())
import pytest
sys.exit(pytest.main(sys.argv[1:]))
