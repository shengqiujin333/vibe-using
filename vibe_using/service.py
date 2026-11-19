"""Windows scanning entry: safely retry thin Chromium accessibility trees."""
from __future__ import annotations

import time
from typing import Callable

from .chromium_recovery import coverage_warning, missing_chromium_contents
from .models import WindowInfo, ScanResult
from .scanner import Limits, scan_process
from .windows_chromium import ActivationResult


def scan_with_recovery(
    windows: list[WindowInfo], pid: int, limits: Limits, adapter_factory: Callable[[], object],
    activate: Callable[[list[int]], ActivationResult],
    *,
    delay: Callable[[float], None] = time.sleep,
) -> ScanResult:
    """Retry only when a Chromium root is suspiciously hollow; never click UI.

    An optional renderer-root scan helps if Chromium does not join the child
    content under the main HWND's UIA control view after activation.
    """
    first = scan_process(windows, pid, adapter_factory(), limits)
    if not missing_chromium_contents(first):
        return first
    try:
        attempt = activate([w.hwnd for w in windows if w.pid == pid])
    except Exception as exc:
        first.errors.append(coverage_warning(attempted=True))
        first.errors.append(f"Chromium 辅助功能激活异常：{type(exc).__name__}: {exc}")
        return first
    if attempt.signaled:
        delay(0.2)
        recovered = scan_process(windows, pid, adapter_factory(), limits)
        if not missing_chromium_contents(recovered):
            return recovered
        # Some providers expose the document only from the child renderer HWND.
        # Keep the richer tree rather than hiding it under a nearly empty shell.
        for hwnd in attempt.handles[:4]:
            child = WindowInfo(hwnd=hwnd, pid=pid, title="Chromium 内嵌渲染界面（辅助入口）")
            candidate = scan_process([child], pid, adapter_factory(), limits)
            # A child HWND with just more anonymous PaneControl nodes is NOT a
            # successful recovery. Require actual content evidence.
            named_actions = sum(bool(n.name) and n.action_candidate for n in candidate.nodes)
            named_content = sum(bool(n.name) and n.parent_id is not None for n in candidate.nodes)
            if (len(candidate.nodes) > len(recovered.nodes) and
                (named_actions > 0 or named_content >= 3 or
                 any(n.role == "DocumentControl" for n in candidate.nodes))):
                candidate.title = first.title
                candidate.errors.append("注意：通过子渲染窗口采集，结果是内嵌界面，不是另一个顶层窗口。")
                return candidate
        first = recovered
    first.errors.append(coverage_warning(attempted=True, activated=attempt.signaled, renderer_count=len(attempt.handles)))
    first.errors.extend(attempt.errors)
    return first


def scan_windows(windows: list[WindowInfo], pid: int, limits: Limits, include_text: bool = False) -> ScanResult:
    from .uia_backend import UiaAdapter, com_apartment
    from .windows_chromium import activate_renderer_accessibility

    with com_apartment():
        return scan_with_recovery(
            windows, pid, limits, lambda: UiaAdapter(include_text=include_text),
            activate_renderer_accessibility,
        )
