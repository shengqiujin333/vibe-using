"""Bounded, optional Chromium UIA activation via WM_GETOBJECT (no GUI clicks).

Certain Chromium applications do not expose the renderer accessibility tree
until an accessibility client asks for it. We never spawn/restart target apps,
inject code, or perform user-visible menu actions.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActivationResult:
    handles: tuple[int, ...] = ()
    signaled: int = 0
    errors: tuple[str, ...] = ()


def renderer_hwnds(top_level_hwnds: list[int]) -> tuple[int, ...]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumChildWindows.argtypes = (wintypes.HWND, callback_type, wintypes.LPARAM)
    user32.EnumChildWindows.restype = wintypes.BOOL
    user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetClassNameW.restype = ctypes.c_int
    result: list[int] = []
    seen: set[int] = set()

    def visit(hwnd: int, _data: int) -> bool:
        text = ctypes.create_unicode_buffer(256)
        if user32.GetClassNameW(hwnd, text, len(text)) and text.value.startswith("Chrome_RenderWidgetHostHWND"):
            value = int(hwnd)
            if value not in seen:
                seen.add(value)
                result.append(value)
        return True

    callback = callback_type(visit)
    for hwnd in top_level_hwnds:
        # EnumChildWindows returns 0 if the callback aborts; our callback never does.
        user32.EnumChildWindows(hwnd, callback, 0)
    return tuple(result)


def activate_renderer_accessibility(top_level_hwnds: list[int], *, timeout_ms: int = 250) -> ActivationResult:
    """Ask renderer windows for an accessibility object, with a short timeout.

    Message choice matches the Chromium UIA compatibility workaround used in
    common Windows UIA tools. Sending WM_GETOBJECT does *not* invoke app controls.
    """
    import ctypes
    from ctypes import wintypes

    try:
        handles = renderer_hwnds(top_level_hwnds)
    except OSError as exc:
        return ActivationResult(errors=(f"枚举 Chromium 子窗口失败：{exc}",))
    if not handles:
        return ActivationResult()
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SendMessageTimeoutW.argtypes = (
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
    )
    user32.SendMessageTimeoutW.restype = wintypes.LPARAM
    signaled = 0
    errors: list[str] = []
    for hwnd in handles[:8]:
        reply = ctypes.c_size_t()
        try:
            # WM_GETOBJECT = 0x003D, lParam=1 is used by Chromium UIA workarounds.
            ok = user32.SendMessageTimeoutW(hwnd, 0x003D, 0, 1, 0x0002, timeout_ms, ctypes.byref(reply))
            if ok:
                signaled += 1
            else:
                errors.append(f"渲染 HWND {hwnd}: WM_GETOBJECT 超时或拒绝")
        except OSError as exc:
            errors.append(f"渲染 HWND {hwnd}: {type(exc).__name__}: {exc}")
    return ActivationResult(handles=handles, signaled=signaled, errors=tuple(errors))
