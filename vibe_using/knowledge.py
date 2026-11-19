"""Explain discovered UIA controls without inventing verified application semantics.

Only observed metadata, conservative navigation paths, and clearly labelled guesses.
No clicks, state changes, external services, or LLM calls.
"""
from __future__ import annotations

from typing import Iterable
from .models import Node

# Human-readable software-operation *guesses* derived only from generic labels.
# Not a claim that the button actually performs the action.
NAME_HINTS: tuple[tuple[str, str], ...] = (
    ("另存为", "可能将当前内容保存到指定新文件"),
    ("保存", "可能保存当前文档或项目"),
    ("导出", "可能输出文件或数据"),
    ("打印", "可能打开打印相关操作"),
    ("撤销", "可能撤销上次编辑"),
    ("重做", "可能恢复已撤销的编辑"),
    ("复制", "可能复制选中内容"),
    ("粘贴", "可能粘贴剪贴板内容"),
    ("删除", "可能删除选中项目；请勿自动尝试"),
    ("打开", "可能打开文件、文档或对话框"),
    ("新建", "可能新建文档或对象"),
    ("查找", "可能搜索当前内容"),
    ("设置", "可能调整软件选项"),
    ("帮助", "可能打开软件帮助信息"),
)

# Known navigation labels are not necessarily clickable UIA controls.
NAV_LABELS = frozenset({"文件", "编辑", "视图", "放置", "设计", "工具", "窗口", "帮助", "设置", "项目", "菜单"})

PATTERN_DESCRIPTIONS = {
    "Invoke": "UIA Invoke（触发）",
    "ExpandCollapse": "UIA ExpandCollapse（展开/折叠）",
    "Toggle": "UIA Toggle（切换）",
    "SelectionItem": "UIA SelectionItem（选中）",
    "Value": "UIA Value（设置值；只表示接口可用）",
    "RangeValue": "UIA RangeValue（设置数值）",
    "ScrollItem": "UIA ScrollItem（滚动到可见）",
}


def is_navigational_entry(node: Node) -> bool:
    return bool(node.name and node.role in {"GroupControl", "PaneControl", "MenuControl"} and node.name.strip() in NAV_LABELS)


def _segment(node: Node) -> str:
    if node.name:
        return node.name[:80]
    if node.automation_id:
        return f"{node.role}({node.automation_id[:48]})"
    return f"{node.role}#{node.id}"


def enrich_nodes(nodes: Iterable[Node]) -> None:
    """Add names, locations, and operation hints after the hierarchy is known.

    Prefer UIA Name and LabeledBy; ONLY hoist a unique, short TextControl child
    to an unnamed *action-like* container. Never read Edit/Document contents.
    """
    ordered = list(nodes)
    by_id = {node.id: node for node in ordered}
    children: dict[int, list[Node]] = {}
    for node in ordered:
        if node.parent_id is not None:
            children.setdefault(node.parent_id, []).append(node)

    for node in reversed(ordered):
        if not node.name and node.role in {"ButtonControl", "MenuItemControl", "TabItemControl", "GroupControl", "HyperlinkControl", "SplitButtonControl"}:
            labeled = [c.name.strip() for c in children.get(node.id, []) if c.role == "TextControl" and c.name and len(c.name.strip()) <= 80]
            if len(labeled) == 1:
                node.name = labeled[0]
                node.name_source = "child_text"  # Derived: not verified as button caption.
        if node.name and not node.name_source:
            node.name_source = "uia_name"

    def path_for(n: Node) -> str:
        parts: list[str] = []
        seen: set[int] = set()
        cur: Node | None = n
        while cur is not None and cur.id not in seen:
            seen.add(cur.id)
            if cur.name or cur.automation_id or cur.parent_id is None:
                parts.append(_segment(cur))
            cur = by_id.get(cur.parent_id) if cur.parent_id is not None else None
        return " > ".join(reversed(parts))

    for node in ordered:
        node.path = path_for(node)
        if node.help_text:
            node.purpose = node.help_text
            node.purpose_source = "uia_helptext_unverified"
        else:
            for token, guess in NAME_HINTS:
                if token in node.name and node.role not in {"TextControl", "DocumentControl", "EditControl"}:
                    node.purpose = guess
                    node.purpose_source = "name_guess_unverified"
                    break
            if not node.purpose and node.name in NAV_LABELS and is_navigational_entry(node):
                node.purpose = "可能是软件功能菜单或分组入口"
                node.purpose_source = "name_guess_unverified"
        patterns = [PATTERN_DESCRIPTIONS[p] for p in node.supported_patterns if p in PATTERN_DESCRIPTIONS]
        if patterns:
            node.operation = "; ".join(patterns)
            keys = ", ".join(k for k in (node.accelerator_key, node.access_key) if k)
            if keys:
                node.operation += f"; UIA 报告的快捷键/访问键：{keys}（未执行）"
            node.operation_source = "uia_pattern_available_not_executed"
        elif node.legacy_action:
            node.operation = f"UIA LegacyIAccessible 默认操作：{node.legacy_action}（未执行）"
            node.operation_source = "uia_legacy_action_not_executed"
        elif node.accelerator_key or node.access_key:
            key = node.accelerator_key or node.access_key
            node.operation = f"界面报告的快捷键：{key}（尚未执行验证）"
            node.operation_source = "uia_keyboard_metadata"
        elif node.action_candidate or is_navigational_entry(node):
            node.operation = "未发现标准 UIA 操作接口；可能需鼠标/键盘操作，待验证"
            node.operation_source = "unverified_fallback"
        else:
            node.operation = "未知或非可交互元素"
            node.operation_source = "unknown"
