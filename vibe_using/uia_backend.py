"""Read-only UI Automation metadata and supported operation patterns.

No operation pattern method (Invoke, SetValue, Select, Expand) is called.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator


@contextmanager
def com_apartment() -> Iterator[None]:
    """Initialize COM on the worker thread that actually uses UI Automation."""
    import comtypes

    comtypes.CoInitialize()
    try:
        yield
    finally:
        comtypes.CoUninitialize()


# UIA pattern getters: retrieving a pattern does NOT execute its operation.
PATTERNS_BY_ROLE: dict[str, tuple[str, ...]] = {
    "ButtonControl": ("Invoke", "Toggle", "ExpandCollapse"),
    "MenuItemControl": ("Invoke", "ExpandCollapse", "SelectionItem", "Toggle"),
    "SplitButtonControl": ("Invoke", "ExpandCollapse"),
    "HyperlinkControl": ("Invoke",),
    "TabItemControl": ("SelectionItem",),
    "CheckBoxControl": ("Toggle",),
    "RadioButtonControl": ("SelectionItem",),
    "ComboBoxControl": ("ExpandCollapse", "Value"),
    "ListItemControl": ("SelectionItem", "ScrollItem"),
    "TreeItemControl": ("ExpandCollapse", "SelectionItem", "ScrollItem"),
    "EditControl": ("Value",),
    "SpinnerControl": ("RangeValue", "Value"),
    "SliderControl": ("RangeValue",),
    # Chromium / custom desktop apps sometimes expose actionable GroupControl.
    "GroupControl": ("Invoke", "ExpandCollapse"),
}


class UiaAdapter:
    def __init__(self, *, include_text: bool = False):
        import uiautomation as auto

        self.auto = auto
        self.include_text = include_text

    def from_handle(self, hwnd: int) -> Any:
        return self.auto.ControlFromHandle(hwnd)

    @staticmethod
    def _get(control: Any, attr: str, default: Any = "") -> Any:
        try:
            value = getattr(control, attr)
            return default if value is None else value
        except Exception:
            return default

    @staticmethod
    def _label(control: Any) -> str:
        """Resolve UIA LabeledBy element without depending on its COM wrapper type."""
        try:
            label = getattr(control, "LabeledBy", None)
            if label is not None:
                name = getattr(label, "Name", "")
                if isinstance(name, str):
                    return name[:256]
        except Exception:
            pass
        return ""

    @staticmethod
    def _patterns(control: Any, role: str) -> list[str]:
        """Get supported pattern objects *only*; never perform their actions."""
        found: list[str] = []
        for name in PATTERNS_BY_ROLE.get(role, ()):
            try:
                getter = getattr(control, f"Get{name}Pattern", None)
                if callable(getter) and getter() is not None:
                    found.append(name)
            except Exception:
                continue
        return found

    @staticmethod
    def _legacy_name_action(control: Any) -> tuple[str, str]:
        """Optional UIA LegacyIAccessible metadata, never DoDefaultAction."""
        try:
            getter = getattr(control, "GetLegacyIAccessiblePattern", None)
            pattern = getter() if callable(getter) else None
            if pattern is None:
                return "", ""
            name = str(getattr(pattern, "Name", "") or "")[:256]
            action = str(getattr(pattern, "DefaultAction", "") or "")[:128]
            return name, action
        except Exception:
            return "", ""

    def describe(self, control: Any) -> dict[str, Any]:
        role = str(self._get(control, "ControlTypeName", "UnknownControl"))
        is_password = bool(self._get(control, "IsPassword", False))
        # TextControl is very often a label: capture its Name. Avoid document / edit
        # contents by default. Password metadata never enters the report.
        sensitive_content = role in {"DocumentControl", "EditControl"} and not self.include_text
        redact_name = is_password or sensitive_content
        rect = self._get(control, "BoundingRectangle", None)
        try:
            bounds = [int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)]
        except (AttributeError, TypeError, ValueError):
            bounds = None
        raw_name = "" if redact_name else str(self._get(control, "Name"))[:512]
        labeled_by = "" if is_password else self._label(control)
        legacy_name, legacy_action = ("", "")
        if not is_password and not sensitive_content and role in PATTERNS_BY_ROLE and role != "GroupControl":
            if not raw_name and not labeled_by:
                legacy_name, legacy_action = self._legacy_name_action(control)
        # HelpText may contain project/user data. Never harvest from password elements.
        help_text = "" if is_password else str(self._get(control, "HelpText"))[:512]
        return {
            "role": role,
            "raw_name": raw_name,
            "name": raw_name or labeled_by or legacy_name,
            "name_source": ("uia_name" if raw_name else "labeled_by" if labeled_by else "legacy_accessible" if legacy_name else ""),
            "labeled_by": labeled_by,
            "legacy_action": legacy_action,
            "help_text": help_text,
            "localized_control_type": str(self._get(control, "LocalizedControlType"))[:128],
            "automation_id": str(self._get(control, "AutomationId"))[:256],
            "class_name": str(self._get(control, "ClassName"))[:256],
            "access_key": str(self._get(control, "AccessKey"))[:120],
            "accelerator_key": str(self._get(control, "AcceleratorKey"))[:120],
            "enabled": bool(self._get(control, "IsEnabled", False)),
            "offscreen": bool(self._get(control, "IsOffscreen", False)),
            "rect": bounds,
            "supported_patterns": [] if is_password or (role == "GroupControl" and not (raw_name or labeled_by or legacy_name)) else self._patterns(control, role),
        }

    def children(self, control: Any) -> list[Any]:
        return list(control.GetChildren())
