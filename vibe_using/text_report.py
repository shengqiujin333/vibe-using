"""Human-readable reports centered on useful controls, with a raw tree appendix."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .models import ScanResult
from .control_visibility import location_explanation, location_status, is_property_control
from .chromium_recovery import missing_chromium_contents_data


# Windows will display this file beside the terminal working directory.
def default_report_path(scan_id: int, pid: int, reports_dir: str | Path | None = None) -> Path:
    folder = Path(reports_dir).expanduser() if reports_dir is not None else Path.cwd() / "scans"
    return folder / f"scan-{scan_id}-pid-{pid}.txt"


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _location(node: dict[str, Any]) -> str:
    rect = node.get("rect")
    if isinstance(rect, (list, tuple)) and len(rect) == 4:
        return f"UIA 返回矩形 ({', '.join(map(str, rect))})"
    return "屏幕坐标未提供"


def _purpose(node: dict[str, Any]) -> str:
    purpose = _clean(node.get("purpose"))
    source = node.get("purpose_source")
    if not purpose:
        return "未知；不能仅凭控件类型确定功能"
    if source == "uia_helptext_unverified":
        return f"{purpose} [来源:UIA HelpText，未验证]"
    if source == "name_guess_unverified":
        return f"{purpose} [根据名称推测，未验证]"
    return f"{purpose} [尚未验证]"


def _interesting(node: dict[str, Any]) -> bool:
    if not node.get("name"):
        return False
    if node.get("action_candidate"):
        return True
    return node.get("role") in {"GroupControl", "PaneControl", "MenuControl"} and node["name"].strip() in {
        "文件", "编辑", "视图", "放置", "设计", "工具", "窗口", "帮助", "设置", "项目", "菜单",
    }


def format_text_report(record: dict[str, Any] | ScanResult) -> str:
    """Start with searchable named actionable controls; retain full raw hierarchy."""
    data = record.to_dict() if isinstance(record, ScanResult) else record
    windows = data.get("windows", [])
    nodes = data.get("nodes", [])
    candidates = [n for n in nodes if n.get("action_candidate")]
    named = [n for n in nodes if n.get("name")]
    listed = [n for n in nodes if _interesting(n)]
    visible_entries = [n for n in listed if location_status(n) == "located" and not is_property_control(n)]
    property_entries = [n for n in listed if location_status(n) == "located" and is_property_control(n)]
    unlocatable_entries = [n for n in listed if location_status(n) != "located"]
    lines = [
        "Vibe Using - Windows 软件控件与功能入口报告",
        "=" * 65,
        f"软件窗口: {_clean(data.get('title')) or '(无标题)'}",
        f"进程 PID: {data.get('pid', '')}",
    ]
    if data.get("scan_id") is not None:
        lines.append(f"扫描编号: {data['scan_id']}")
    if data.get("created_utc"):
        lines.append(f"扫描时间(UTC): {_clean(data['created_utc'])}")
    if missing_chromium_contents_data(nodes):
        lines.extend([
            "",
            "【警告】此次未获得 Chromium 内部控件树；下面的空清单不是软件没有功能。",
            "当前只看到了窗口外壳。请先检查软件是否最小化，再重新扫描。",
            "如果重新扫描仍无内容，请查看文末扫描诊断与 Chromium 辅助功能提示。",
            "",
        ])
    lines.extend([
        f"窗口: {len(windows)} | UIA 控件: {len(nodes)} | 有名称: {len(named)} | 候选交互: {len(candidates)} | 有名称的功能/菜单入口: {len(listed)}",
        f"可定位的非属性入口: {len(visible_entries)} | 可定位的属性控件: {len(property_entries)} | 无法定位/屏幕外的入口: {len(unlocatable_entries)}",
        f"扫描是否截断: {'是' if data.get('truncated') else '否'}",
        "名称来源: UIA Name / LabeledBy / LegacyIAccessible / 唯一子文本（若可获取）。",
        "位置来源: 控件层级路径、AutomationId 与当时屏幕矩形；窗口移动后坐标可能失效。",
        "重要: (0,0,0,0) 是无效矩形，不是屏幕左上角。可用+Toggle 也不证明控件正显示。",
        "可定位仅指 UIA 提供有效矩形，仍需检查遮挡、命中测试和当前窗口状态。",
        "操作方式: 仅探测接口是否存在；没有调用按钮、展开菜单或修改软件。",
        "作用: UIA HelpText 是界面提供的说明；根据名称生成的解释仅是猜测，未经验证。",
        "注意: 尚未打开的菜单/窗口、自绘 Canvas 内对象可能无法发现；名称和提示可能包含隐私数据。",
        "",
        "一、当前可定位的功能与菜单入口（优先阅读）",
        "-" * 65,
    ])

    def append_entries(entries: list[dict[str, Any]]) -> None:
        if not entries:
            lines.append("(没有符合当前分组的控件)")
        for n in entries:
            lines.extend([
                f"#{n.get('id')} {_clean(n.get('name'))} [{_clean(n.get('role'))}]",
                f"  在哪里: {_clean(n.get('path')) or '(路径未知)'}",
                f"  定位: {_location(n)} | AutomationId={_clean(n.get('automation_id')) or '(空)'}",
                f"  位置判断: {location_explanation(n)}",
                f"  名称依据: {_clean(n.get('name_source')) or '旧版快照 / 未记录'}",
                f"  作用: {_purpose(n)}",
                f"  怎么操作: {_clean(n.get('operation')) or '尚无操作模式数据，需要重新扫描'}",
                f"  可用状态: {'可用' if n.get('enabled') else '禁用' if n.get('enabled') is False else '未知'}",
                "",
            ])

    append_entries(visible_entries)
    lines.extend(["", "二、属性面板控件（当前可定位，非独立功能菜单）", "-" * 65])
    append_entries(property_entries)
    lines.extend(["", "三、位置无效或屏幕外的候选控件（保留名称，但不可当作当前屏幕按钮）", "-" * 65])
    # The full inventory follows below.  Do not bury useful controls beneath
    # hundreds of zero-size Chromium form inputs in the main report.
    sample_limit = 30
    if not unlocatable_entries:
        lines.append("(没有符合当前分组的控件)")
    else:
        lines.append(f"本组共 {len(unlocatable_entries)} 个，以下仅列前 {sample_limit} 项；完整名称、ID、层级见第四节。")
        for n in unlocatable_entries[:sample_limit]:
            lines.append(f"#{n.get('id')} {_clean(n.get('name'))} [{_clean(n.get('role'))}] | {location_explanation(n)}")
        if len(unlocatable_entries) > sample_limit:
            lines.append(f"……另外 {len(unlocatable_entries)-sample_limit} 项详见完整控件树。")
    lines.extend(["", "四、全部控件的层级树（技术明细）", "-" * 65])
    for window in windows:
        hwnd = window.get("hwnd")
        lines.append(f"窗口: {_clean(window.get('title')) or '(无标题)'} [HWND={hwnd}, PID={window.get('pid', '')}]")
        belonging = [n for n in nodes if n.get("window_hwnd") == hwnd]
        if not belonging:
            lines.append("  (没有读取到 UIA 控件)")
        for n in belonging:
            depth = max(0, min(50, int(n.get("depth") or 0)))
            name = _clean(n.get("name")) or "(无名称；UIA 未提供或隐私设置未采集)"
            role = _clean(n.get("role")) or "UnknownControl"
            lines.append(f"{'  ' * (depth + 1)}- #{n.get('id', '?')} [{role}] {name}")
            details = []
            for field, label in (
                ("automation_id", "AutomationId"),
                ("class_name", "Class"),
                ("accelerator_key", "快捷键"),
                ("access_key", "访问键"),
                ("name_source", "名称来源"),
                ("help_text", "HelpText"),
            ):
                value = _clean(n.get(field))
                if value:
                    details.append(f"{label}={value}")
            patterns = n.get("supported_patterns") or []
            if patterns:
                details.append(f"可用UIA模式={','.join(patterns)}")
            if n.get("action_candidate"):
                details.append("候选交互控件")
            if n.get("enabled") is not None:
                details.append("可用" if n["enabled"] else "禁用")
            if n.get("offscreen"):
                details.append("屏幕外")
            elif location_status(n) == "no_geometry":
                details.append("无有效屏幕矩形")
            if n.get("error"):
                details.append(f"读取异常={_clean(n['error'])}")
            if details:
                lines.append(f"{'  ' * (depth + 2)}{' | '.join(details)}")
        lines.append("")
    if not windows:
        lines.extend(["(没有发现可扫描窗口)", ""])
    if data.get("errors"):
        lines.extend(["扫描诊断 / 异常", "-" * 65])
        lines.extend(f"- {_clean(error)}" for error in data["errors"])
    return "\n".join(lines).rstrip() + "\n"


def save_text_report(record: dict[str, Any] | ScanResult, path: str | Path) -> Path:
    dest = Path(path).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(format_text_report(record), encoding="utf-8-sig")
    return dest
