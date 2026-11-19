"""Detect missing Chromium accessibility contents and recover without UI clicks.

A shallow Chrome_WidgetWin_1 tree is not evidence that a UI has no features.
This module is platform neutral for testing; Windows messaging lives elsewhere.
"""
from __future__ import annotations

from .models import ScanResult


def missing_chromium_contents(result: ScanResult) -> bool:
    """Flag a likely provider failure, never a proof of a complete UI scan.

    The target must be Chromium-backed *and* the tree must have almost no
    named content. A small legitimate dialog must not be assumed broken.
    """
    if result.truncated or not result.nodes:
        return False
    chromium = any(n.class_name.startswith("Chrome_WidgetWin_") for n in result.nodes)
    if not chromium:
        return False
    # A healthy Chromium web document usually exposes groups, text and actions.
    named_children = [n for n in result.nodes if n.parent_id is not None and n.name]
    actions = [n for n in result.nodes if n.action_candidate and n.name]
    document = any(n.role == "DocumentControl" for n in result.nodes)
    return not document and not actions and len(named_children) <= 2 and len(result.nodes) <= 60


def missing_chromium_contents_data(nodes: list[dict]) -> bool:
    """Report-only equivalent that also handles SQLite snapshots from old versions."""
    if not nodes or not any(str(n.get("class_name", "")).startswith("Chrome_WidgetWin_") for n in nodes):
        return False
    named_children = [n for n in nodes if n.get("parent_id") is not None and n.get("name")]
    actions = [n for n in nodes if n.get("name") and n.get("action_candidate")]
    return (len(nodes) <= 60 and len(named_children) <= 2 and not actions and
            not any(n.get("role") == "DocumentControl" for n in nodes))


def coverage_warning(*, attempted: bool, activated: int = 0, renderer_count: int = 0) -> str:
    if not attempted:
        detail = "没有执行恢复尝试。"
    elif not renderer_count:
        detail = "没有找到 Chromium 渲染子窗口，因此无法发送辅助功能激活请求。"
    elif not activated:
        detail = "已找到渲染子窗口，但辅助功能激活请求失败或超时。"
    else:
        detail = "已请求激活 Chromium 辅助功能，但重新扫描仍未获得内容控件树。"
    return (
        "扫描不完整：当前仅获取到 Chromium 窗口外壳，未获取应用内部菜单和控件。"
        + detail
        + " 请确保软件窗口未最小化、位于当前桌面且内容已加载后重试；"
        "必要时检查软件是否支持启用 Chromium 辅助功能。"
    )
