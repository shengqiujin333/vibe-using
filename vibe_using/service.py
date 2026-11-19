"""Windows UIA scanning with independently checked Chromium recovery routes."""
from __future__ import annotations

import time
from typing import Any, Callable

from .chromium_recovery import coverage_warning, missing_chromium_contents
from .models import WindowInfo, ScanResult
from .scanner import Limits, scan_process
from .windows_chromium import ActivationResult


def _content_score(result: ScanResult) -> tuple[int, int, int]:
    named = sum(bool(n.name) for n in result.nodes if n.parent_id is not None)
    actions = sum(bool(n.name) and n.action_candidate for n in result.nodes)
    docs = sum(n.role == "DocumentControl" for n in result.nodes)
    return docs, actions, named


def _has_real_content(result: ScanResult) -> bool:
    docs, actions, named = _content_score(result)
    return docs > 0 or (actions >= 2 and named >= 3) or named >= 5


def scan_with_recovery(
    windows: list[WindowInfo], pid: int, limits: Limits, adapter_factory: Callable[[], Any],
    activate: Callable[[list[int]], ActivationResult],
    *,
    delay: Callable[[float], None] = time.sleep,
    point_probe: Callable[[Any, list[WindowInfo], int], tuple[list[tuple[WindowInfo, Any]], str]] | None = None,
) -> ScanResult:
    """Try Chromium HWND accessibility and, if needed, bounded UIA hit testing.

    Never click, move cursor, focus an app, invoke controls or alter app settings.
    Recovery may be partial and is labelled as such.
    """
    adapter = adapter_factory()
    first = scan_process(windows, pid, adapter, limits)
    if not missing_chromium_contents(first):
        return first

    try:
        attempt = activate([w.hwnd for w in windows if w.pid == pid])
    except Exception as exc:
        attempt = ActivationResult(errors=(f"Chromium 辅助功能请求异常：{type(exc).__name__}: {exc}",))

    recovered = first
    if attempt.signaled:
        delay(0.2)
        recovered = scan_process(windows, pid, adapter_factory(), limits)
        if not missing_chromium_contents(recovered):
            recovered.errors.append("Chromium 辅助功能请求后已获取内部控件树；请根据实际控件核对覆盖范围。")
            return recovered

        # Older versions have renderer HWND roots. Scan them only if found.
        for hwnd in attempt.handles[:4]:
            child = WindowInfo(hwnd=hwnd, pid=pid, title="Chromium 内嵌渲染界面（辅助入口）")
            candidate = scan_process([child], pid, adapter_factory(), limits)
            if _has_real_content(candidate) and _content_score(candidate) > _content_score(recovered):
                candidate.title = first.title
                candidate.errors.append("通过 Chromium 内嵌界面子渲染窗口采集：该内容树不代表全部应用界面。")
                return candidate

    probe_diagnostic = ""
    if point_probe is not None:
        try:
            probe_adapter = adapter_factory()
            probes, probe_diagnostic = point_probe(probe_adapter, windows, pid)
            # Each point-anchored scan has its own budget; restrict to 6 probes.
            for window, root in probes[:6]:
                candidate = scan_process(
                    [window], pid, probe_adapter, limits,
                    roots_by_hwnd={window.hwnd: root},
                )
                if _has_real_content(candidate) and _content_score(candidate) > _content_score(recovered):
                    recovered = candidate
            if recovered is not first and _has_real_content(recovered):
                recovered.errors.append(
                    "UIA 屏幕点查询获得部分控件；这只是当前可见区域的子树，并非完整功能清单。"
                )
                recovered.errors.append(probe_diagnostic)
                return recovered
        except Exception as exc:
            probe_diagnostic = f"UIA 屏幕点查询异常：{type(exc).__name__}: {exc}"

    # Surface a transparent failure rather than claiming there are no features.
    recovered.errors.append(coverage_warning(
        attempted=True, activated=attempt.signaled,
        renderer_count=len(attempt.handles), root_requests=attempt.top_level_requests,
    ))
    recovered.errors.extend(attempt.errors)
    if probe_diagnostic:
        recovered.errors.append(probe_diagnostic)
    return recovered


def scan_windows(windows: list[WindowInfo], pid: int, limits: Limits, include_text: bool = False) -> ScanResult:
    from .uia_backend import UiaAdapter, com_apartment
    from .windows_chromium import activate_renderer_accessibility
    from .windows_probe import probe_ui_roots

    with com_apartment():
        return scan_with_recovery(
            windows, pid, limits, lambda: UiaAdapter(include_text=include_text),
            activate_renderer_accessibility, point_probe=probe_ui_roots,
        )
