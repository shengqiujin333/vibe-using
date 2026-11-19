"""Classify where UIA controls can be located, without claiming they are clickable.

A provider can return an enabled Toggle pattern for an element with no meaningful
screen rectangle (e.g. a hidden checkbox input in Chromium).  Keep such elements
in raw inventory but do not present them as on-screen commands.
"""
from __future__ import annotations

from typing import Any


def location_status(node: dict[str, Any]) -> str:
    """Return one of ``offscreen``, ``no_geometry``, or ``located``.

    UIA IsOffscreen is the provider's report, not proof of actual visibility.
    A positive bounding rectangle is necessary, not sufficient, for being visible.
    The rectangle contains [left, top, right, bottom]; negative screen
    coordinates are valid on multi-monitor configurations.
    """
    if node.get("offscreen") is True:
        return "offscreen"
    rect = node.get("rect")
    if not isinstance(rect, (list, tuple)) or len(rect) != 4:
        return "no_geometry"
    try:
        x1, y1, x2, y2 = [float(v) for v in rect]
    except (ValueError, TypeError, OverflowError):
        return "no_geometry"
    from math import isfinite
    if not all(isfinite(v) for v in (x1, y1, x2, y2)) or x2 <= x1 or y2 <= y1:
        return "no_geometry"
    return "located"


def location_explanation(node: dict[str, Any]) -> str:
    status = location_status(node)
    if status == "offscreen":
        return "UIA 标记屏幕外；当前未确认可操作"
    if status == "no_geometry":
        return "无有效屏幕矩形；可能隐藏/未布局/虚拟元素，不能按坐标定位"
    return "有有效屏幕矩形（仍需实际可见性及遮挡检查）"


def is_property_control(node: dict[str, Any]) -> bool:
    """Heuristic: an editor's attribute inspector is not a top-level command list."""
    if node.get("role") not in {"CheckBoxControl", "EditControl", "ComboBoxControl", "RadioButtonControl", "SpinnerControl", "SliderControl"}:
        return False
    s = f"{node.get('path', '')} {node.get('automation_id', '')}".lower()
    return any(fragment in s for fragment in (
        "property_panel", "properties_panel", "attribute_panel", "sch-attribute-tabs",
    ))


def tree_visible_ids(nodes: list[dict[str, Any]], *, only_located: bool) -> set[int]:
    """Show real-sized controls and their ancestor chain for usable tree navigation.

    When filtering, unnamed non-action leaf nodes are omitted; users can disable
    the filter to inspect the full UIA inventory including zero-sized controls.
    """
    if not only_located:
        return {n["id"] for n in nodes}
    by_id = {n["id"]: n for n in nodes}
    selected: set[int] = set()
    for node in nodes:
        if location_status(node) != "located":
            continue
        if not (node.get("name") or node.get("action_candidate")):
            continue
        seen: set[int] = set()
        item: dict[str, Any] | None = node
        while item is not None and item["id"] not in seen:
            seen.add(item["id"])
            selected.add(item["id"])
            item = by_id.get(item.get("parent_id"))
    return selected
