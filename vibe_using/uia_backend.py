"""Only UIA property reads; the scanning path never invokes a control."""
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

    def describe(self, control: Any) -> dict[str, Any]:
        role = str(self._get(control, "ControlTypeName", "UnknownControl"))
        is_password = bool(self._get(control, "IsPassword", False))
        redact_name = is_password or (not self.include_text and role in {
            "TextControl", "DocumentControl", "EditControl",
        })
        rect = self._get(control, "BoundingRectangle", None)
        try:
            bounds = [int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)]
        except (AttributeError, TypeError, ValueError):
            bounds = None
        return {
            "role": role,
            "name": "" if redact_name else str(self._get(control, "Name"))[:512],
            "automation_id": str(self._get(control, "AutomationId"))[:256],
            "class_name": str(self._get(control, "ClassName"))[:256],
            "access_key": str(self._get(control, "AccessKey"))[:120],
            "accelerator_key": str(self._get(control, "AcceleratorKey"))[:120],
            "enabled": bool(self._get(control, "IsEnabled", False)),
            "offscreen": bool(self._get(control, "IsOffscreen", False)),
            "rect": bounds,
        }

    def children(self, control: Any) -> list[Any]:
        return list(control.GetChildren())
