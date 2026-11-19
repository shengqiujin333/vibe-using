"""Bounded, read-only UIA hit testing for Chromium without renderer HWNDs.

ElementFromPoint queries accessibility metadata; it does not move/click the
mouse. This is a supplemental route when the top-level raw UIA tree is hollow.
Only points whose *visible* top-level HWND is the selected app are inspected;
an overlaid program is never scanned accidentally.
"""
from __future__ import annotations

from typing import Any

from .models import WindowInfo


def select_content_ancestor(hit: Any, *, max_parents: int = 14) -> Any:
    """Prefer a DocumentControl on the hit element's ancestor chain.

    If no document is present, prefer a named group near the hit. Does not
    leave the current UIA subtree to collect unrelated app data.
    """
    chain = []
    current = hit
    for _ in range(max_parents):
        if current is None:
            break
        chain.append(current)
        try:
            current = current.GetParentControl()
        except Exception:
            break
    for candidate in chain:
        if getattr(candidate, "ControlTypeName", "") == "DocumentControl":
            return candidate
    for candidate in reversed(chain):
        if (getattr(candidate, "ControlTypeName", "") in {"GroupControl", "PaneControl"} and
            getattr(candidate, "Name", "") and
            getattr(candidate, "ClassName", "") != "Chrome_WidgetWin_1"):
            return candidate
    return hit


def probe_ui_roots(adapter: Any, windows: list[WindowInfo], pid: int) -> tuple[list[tuple[WindowInfo, Any]], str]:
    """Look up to six UIA elements under the *visible* selected application.

    Probe failure is diagnostic, not proof that the application lacks controls.
    It may be covered by the scanner itself or another window.
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.WindowFromPoint.argtypes = (wintypes.POINT,)
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetAncestor.restype = wintypes.HWND
    user32.IsIconic.argtypes = (wintypes.HWND,)
    user32.IsIconic.restype = wintypes.BOOL

    roots: list[tuple[WindowInfo, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    occluded = 0
    queried = 0
    errors = 0
    # Probe top toolbar and content regions, but never click/move/focus.
    offsets = ((0.25, 0.10), (0.50, 0.10), (0.75, 0.10),
               (0.25, 0.38), (0.50, 0.38), (0.75, 0.38))
    for window in windows:
        if window.pid != pid or len(roots) >= 6:
            continue
        if user32.IsIconic(window.hwnd):
            continue
        rect = wintypes.RECT()
        if not user32.GetWindowRect(window.hwnd, ctypes.byref(rect)):
            continue
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width < 80 or height < 80:
            continue
        for dx, dy in offsets:
            x = int(rect.left + dx * width)
            y = int(rect.top + dy * height)
            covering = user32.WindowFromPoint(wintypes.POINT(x, y))
            if not covering or int(user32.GetAncestor(covering, 2)) != window.hwnd:
                occluded += 1
                continue
            queried += 1
            try:
                hit = adapter.auto.ControlFromPoint(x, y)
                if not hit:
                    continue
                root = select_content_ancestor(hit)
                signature = (str(getattr(root, "ControlTypeName", "")),
                             str(getattr(root, "Name", "")),
                             str(getattr(root, "AutomationId", "")),
                             str(getattr(root, "BoundingRectangle", "")))
                if signature in seen:
                    continue
                seen.add(signature)
                roots.append((window, root))
            except Exception:
                errors += 1
            if len(roots) >= 6:
                break
    return roots, f"UIA 屏幕点查询={queried}，被其他窗口遮挡或不可见={occluded}，查询异常={errors}，候选子树={len(roots)}"
