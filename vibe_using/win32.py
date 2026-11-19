"""List visible titled top-level windows, without manipulating them."""
from __future__ import annotations

import sys
from .models import WindowInfo


def list_windows() -> list[WindowInfo]:
    if sys.platform != "win32":
        raise OSError("Window enumeration requires Windows")

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    found: list[WindowInfo] = []

    @callback_type
    def enum_callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        text = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, text, length + 1)
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value and text.value.strip():
            found.append(WindowInfo(hwnd=int(hwnd), pid=int(pid.value), title=text.value.strip()))
        return True

    if not user32.EnumWindows(enum_callback, 0):
        raise OSError("EnumWindows failed")
    return sorted(found, key=lambda w: (w.title.casefold(), w.pid, w.hwnd))
