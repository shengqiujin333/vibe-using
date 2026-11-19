"""Plain-data contracts; intentionally independent of Windows and GUI libraries."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    pid: int
    title: str


@dataclass
class Node:
    id: int
    parent_id: int | None
    window_hwnd: int
    depth: int
    role: str
    name: str = ""
    automation_id: str = ""
    class_name: str = ""
    access_key: str = ""
    accelerator_key: str = ""
    enabled: bool | None = None
    offscreen: bool | None = None
    rect: list[int] | None = None
    action_candidate: bool = False
    error: str = ""
    # v0.3 richer, inspectable UIA evidence. Existing JSON snapshots remain readable.
    raw_name: str = ""
    name_source: str = ""
    labeled_by: str = ""
    legacy_action: str = ""
    help_text: str = ""
    localized_control_type: str = ""
    supported_patterns: list[str] = field(default_factory=list)
    operation: str = ""
    operation_source: str = ""
    purpose: str = ""
    purpose_source: str = ""
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanResult:
    pid: int
    title: str
    windows: list[WindowInfo] = field(default_factory=list)
    nodes: list[Node] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "platform": "windows-uia",
            "capture_mode": "read_only",
            "pid": self.pid,
            "title": self.title,
            "windows": [asdict(w) for w in self.windows],
            "nodes": [n.to_dict() for n in self.nodes],
            "errors": self.errors,
            "truncated": self.truncated,
            "summary": {
                "windows": len(self.windows),
                "nodes": len(self.nodes),
                "named": sum(bool(n.name) for n in self.nodes),
                "action_candidates": sum(n.action_candidate for n in self.nodes),
                "named_action_candidates": sum(bool(n.name) and n.action_candidate for n in self.nodes),
            },
            "disclaimer": "Observed UIA evidence and unverified operation hints, not a complete or validated functionality catalog.",
        }
