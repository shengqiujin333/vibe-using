"""Read-only attempts to activate Chromium's Windows accessibility provider.

Chromium 138+ may expose a native UIA tree without an intermediate
Chrome_RenderWidgetHostHWND child. Therefore a missing renderer HWND is not a
reason to give up: we can query the target *top-level* Chromium HWND too.
WM_GETOBJECT is an accessibility request; it never invokes a UI command.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActivationResult:
    handles: tuple[int, ...] = ()
    signaled: int = 0
    errors: tuple[str, ...] = ()
    top_level_requests: int = 0


def _window_class(user32: object, hwnd: int) -> str:
    import ctypes
    from ctypes import wintypes

    user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetClassNameW.restype = ctypes.c_int
    buf = ctypes.create_unicode_buffer(256)
    return buf.value if user32.GetClassNameW(hwnd, buf, len(buf)) else ""


def renderer_hwnds(top_level_hwnds: list[int]) -> tuple[int, ...]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumChildWindows.argtypes = (wintypes.HWND, callback_type, wintypes.LPARAM)
    user32.EnumChildWindows.restype = wintypes.BOOL
    result: list[int] = []
    seen: set[int] = set()

    def visit(hwnd: int, _data: int) -> bool:
        if _window_class(user32, hwnd).startswith("Chrome_RenderWidgetHostHWND"):
            value = int(hwnd)
            if value not in seen:
                seen.add(value)
                result.append(value)
        return True

    callback = callback_type(visit)
    for hwnd in top_level_hwnds[:8]:
        user32.EnumChildWindows(hwnd, callback, 0)
    return tuple(result)


def activation_targets(
    top_level_hwnds: list[int], renderer_handles: tuple[int, ...],
    class_lookup,
) -> tuple[tuple[int, int, str], ...]:
    """(HWND, object id, description). Renderer first, root fallback always.

    The root fallback is only allowed for actual Chromium HWNDs, not arbitrary
    windows. Object ID 1 is Chromium's historical accessibility handshake;
    OBJID_CLIENT (-4) requests the normal accessible client object.
    """
    targets = [(hwnd, 1, "renderer") for hwnd in renderer_handles[:8]]
    for hwnd in top_level_hwnds[:4]:
        if class_lookup(hwnd).startswith("Chrome_WidgetWin_"):
            targets.append((hwnd, 1, "top-level custom object"))
            targets.append((hwnd, -4, "top-level OBJID_CLIENT"))
    return tuple(targets)


def activate_renderer_accessibility(top_level_hwnds: list[int], *, timeout_ms: int = 250) -> ActivationResult:
    """Ask renderer AND top-level Chrome windows to expose accessibility.

    'signaled' means the window replied, *not* that the UIA tree recovered.
    The caller must rescan and verify actual named content.
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    try:
        handles = renderer_hwnds(top_level_hwnds)
        targets = activation_targets(top_level_hwnds, handles, lambda h: _window_class(user32, h))
    except (OSError, ValueError) as exc:
        return ActivationResult(errors=(f"枚举 Chromium 窗口失败：{type(exc).__name__}: {exc}",))

    user32.SendMessageTimeoutW.argtypes = (
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
    )
    user32.SendMessageTimeoutW.restype = wintypes.LPARAM
    signaled = 0
    root_requests = 0
    errors: list[str] = []
    for hwnd, object_id, label in targets:
        result = ctypes.c_size_t()
        if label.startswith("top-level"):
            root_requests += 1
        try:
            ok = user32.SendMessageTimeoutW(
                hwnd, 0x003D, 0, object_id, 0x0002, timeout_ms, ctypes.byref(result)
            )
            if ok:
                signaled += 1
            else:
                errors.append(f"{label} HWND={hwnd}: WM_GETOBJECT 无响应或超时")
        except OSError as exc:
            errors.append(f"{label} HWND={hwnd}: {type(exc).__name__}: {exc}")
    return ActivationResult(tuple(handles), signaled, tuple(errors), root_requests)
