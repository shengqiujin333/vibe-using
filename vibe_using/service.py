"""Windows-only scanning entry; called from a worker to keep Tk responsive."""
from __future__ import annotations

from .models import WindowInfo, ScanResult
from .scanner import Limits, scan_process


def scan_windows(windows: list[WindowInfo], pid: int, limits: Limits, include_text: bool = False) -> ScanResult:
    from .uia_backend import UiaAdapter, com_apartment

    with com_apartment():
        backend = UiaAdapter(include_text=include_text)
        return scan_process(windows, pid, backend, limits)
