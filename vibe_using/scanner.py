"""Bounded, read-only traversal of selected process windows.

The adapter is injected so the traversal is fully testable without Windows.
No Click, Invoke, SetValue, Focus or Expand operations are permitted here.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable, Iterable, Mapping, Protocol

from .models import Node, ScanResult, WindowInfo
from .knowledge import enrich_nodes

ACTION_ROLES = frozenset({
    "ButtonControl", "MenuItemControl", "HyperlinkControl", "TabItemControl",
    "CheckBoxControl", "RadioButtonControl", "ComboBoxControl",
    "TreeItemControl", "ListItemControl", "SplitButtonControl",
})


class Adapter(Protocol):
    def from_handle(self, hwnd: int) -> Any: ...
    def describe(self, control: Any) -> dict[str, Any]: ...
    def children(self, control: Any) -> list[Any]: ...


@dataclass(frozen=True)
class Limits:
    max_depth: int = 12
    max_nodes: int = 6000
    max_seconds: float = 30.0
    max_children: int = 1000

    def __post_init__(self) -> None:
        if min(self.max_depth, self.max_nodes, self.max_children) < 1 or self.max_seconds <= 0:
            raise ValueError("All limits must be positive")


def scan_process(
    windows: Iterable[WindowInfo],
    pid: int,
    adapter: Adapter,
    limits: Limits = Limits(),
    *,
    clock: Callable[[], float] = time.monotonic,
    roots_by_hwnd: Mapping[int, Any] | None = None,
) -> ScanResult:
    selected = [w for w in windows if w.pid == pid]
    result = ScanResult(pid=pid, title=selected[0].title if selected else "", windows=selected)
    if not selected:
        result.errors.append(f"No visible titled window for PID {pid}")
        return result

    start = clock()
    next_id = 0
    # Frame: control, parent_id, hwnd, depth
    for window in selected:
        if len(result.nodes) >= limits.max_nodes or clock() - start >= limits.max_seconds:
            result.truncated = True
            break
        try:
            root = roots_by_hwnd[window.hwnd] if roots_by_hwnd and window.hwnd in roots_by_hwnd else adapter.from_handle(window.hwnd)
        except Exception as exc:
            result.errors.append(f"HWND {window.hwnd}: cannot inspect root: {type(exc).__name__}: {exc}")
            continue
        stack: list[tuple[Any, int | None, int, int]] = [(root, None, window.hwnd, 0)]
        while stack:
            if len(result.nodes) >= limits.max_nodes or clock() - start >= limits.max_seconds:
                result.truncated = True
                break
            control, parent_id, hwnd, depth = stack.pop()
            next_id += 1
            node = Node(id=next_id, parent_id=parent_id, window_hwnd=hwnd, depth=depth, role="UnknownControl")
            try:
                info = adapter.describe(control)
                for key in (
                    "role", "name", "automation_id", "class_name", "access_key",
                    "accelerator_key", "enabled", "offscreen", "rect",
                    "raw_name", "name_source", "labeled_by", "legacy_action", "help_text",
                    "localized_control_type", "supported_patterns",
                ):
                    if key in info:
                        setattr(node, key, info[key])
                node.action_candidate = node.role in ACTION_ROLES
            except Exception as exc:
                node.error = f"attributes: {type(exc).__name__}: {exc}"
            result.nodes.append(node)
            if depth >= limits.max_depth:
                continue
            try:
                children = adapter.children(control)
            except Exception as exc:
                node.error = (node.error + " | " if node.error else "") + f"children: {type(exc).__name__}: {exc}"
                continue
            if len(children) > limits.max_children:
                node.error = (node.error + " | " if node.error else "") + "children capped"
                children = children[:limits.max_children]
                result.truncated = True
            # Reverse for stable UI order under iterative DFS.
            for child in reversed(children):
                stack.append((child, node.id, hwnd, depth + 1))
    enrich_nodes(result.nodes)
    return result
