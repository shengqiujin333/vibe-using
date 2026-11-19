"""Tk desktop interface for inspecting Windows UIA functionality evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

from .control_visibility import location_explanation, location_status, tree_visible_ids
from .database import InventoryDB
from .models import WindowInfo
from .scanner import Limits
from .text_report import default_report_path
from .win32 import list_windows


class InventoryApp:
    def __init__(self, root: tk.Tk, db_path: str):
        self.root = root
        root.title("Vibe Using — Windows 控件与功能入口发现器 (只读)")
        root.geometry("1180x780")
        self.db = InventoryDB(db_path)
        self.windows: list[WindowInfo] = []
        self.snapshots: list[dict[str, Any]] = []
        self.active_scan_id: int | None = None
        self.active_report_path: Path | None = None
        self.report_label = tk.StringVar(value="扫描后自动生成 scans 文件夹下的 TXT 报告")
        self.current_nodes: dict[int, dict[str, Any]] = {}
        self.messages: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.busy = False
        self.include_text = tk.BooleanVar(value=False)
        self.only_located = tk.BooleanVar(value=True)
        self.max_depth = tk.StringVar(value="12")
        self.max_nodes = tk.StringVar(value="6000")
        self.status = tk.StringVar(value="准备就绪。扫描不会点击或修改目标软件。")
        self.query = tk.StringVar(value="")
        self.search_matches: list[dict[str, Any]] = []
        self._build()
        self.refresh_windows()
        self.refresh_snapshots()
        self.root.after(120, self._pump)

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)
        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0, 8))
        ttk.Label(controls, text="最大深度").pack(side="left")
        ttk.Entry(controls, textvariable=self.max_depth, width=5).pack(side="left", padx=(4, 10))
        ttk.Label(controls, text="最大控件数").pack(side="left")
        ttk.Entry(controls, textvariable=self.max_nodes, width=8).pack(side="left", padx=(4, 10))
        ttk.Checkbutton(controls, text="额外采集输入框/文档名称（可能含隐私）", variable=self.include_text).pack(side="left")
        ttk.Label(controls, text="扫描限时 30 秒（单次 UIA 调用可能阻塞）", foreground="#777").pack(side="right")

        panes = ttk.Panedwindow(outer, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left = ttk.Frame(panes, width=365)
        right = ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=3)

        ttk.Label(left, text="正在运行的窗口（选中后扫描所属进程）").pack(anchor="w")
        win_frame = ttk.Frame(left)
        win_frame.pack(fill="both", expand=True, pady=(5, 3))
        self.window_list = tk.Listbox(win_frame, exportselection=False)
        self.window_list.pack(side="left", fill="both", expand=True)
        win_scroll = ttk.Scrollbar(win_frame, orient="vertical", command=self.window_list.yview)
        win_scroll.pack(side="right", fill="y")
        self.window_list.configure(yscrollcommand=win_scroll.set)
        row = ttk.Frame(left)
        row.pack(fill="x", pady=(2, 12))
        ttk.Button(row, text="刷新窗口", command=self.refresh_windows).pack(side="left", padx=(0, 6))
        self.scan_button = ttk.Button(row, text="扫描选中软件", command=self.scan_selected)
        self.scan_button.pack(side="left")

        ttk.Label(left, text="历史扫描（双击打开）").pack(anchor="w")
        snapshot_frame = ttk.Frame(left)
        snapshot_frame.pack(fill="both", expand=True, pady=(5, 3))
        self.snapshot_list = tk.Listbox(snapshot_frame, exportselection=False)
        self.snapshot_list.pack(side="left", fill="both", expand=True)
        self.snapshot_list.bind("<Double-Button-1>", self.open_selected_snapshot)
        scroll = ttk.Scrollbar(snapshot_frame, orient="vertical", command=self.snapshot_list.yview)
        scroll.pack(side="right", fill="y")
        self.snapshot_list.config(yscrollcommand=scroll.set)
        row = ttk.Frame(left)
        row.pack(fill="x")
        ttk.Button(row, text="打开扫描", command=self.open_selected_snapshot).pack(side="left", padx=(0, 5))
        ttk.Button(row, text="打开 TXT", command=self.open_text_current).pack(side="left", padx=(0, 5))
        ttk.Button(row, text="另存 TXT", command=self.export_text_current).pack(side="left", padx=(0, 5))
        ttk.Button(row, text="导出 JSON", command=self.export_current).pack(side="left")
        ttk.Label(left, textvariable=self.report_label, wraplength=350, foreground="#155e75").pack(anchor="w", pady=(5, 0))

        search_row = ttk.Frame(right)
        search_row.pack(fill="x")
        ttk.Label(search_row, text="查名称/作用/路径").pack(side="left")
        input_widget = ttk.Entry(search_row, textvariable=self.query)
        input_widget.pack(side="left", fill="x", expand=True, padx=8)
        input_widget.bind("<Return>", lambda _e: self.search())
        ttk.Button(search_row, text="搜索", command=self.search).pack(side="left")

        result_frame = ttk.Frame(right)
        result_frame.pack(fill="x", pady=(4, 6))
        self.results = tk.Listbox(result_frame, height=4, exportselection=False)
        self.results.pack(side="left", fill="x", expand=True)
        self.results.bind("<Double-Button-1>", self.focus_result)
        result_scroll = ttk.Scrollbar(result_frame, orient="vertical", command=self.results.yview)
        result_scroll.pack(side="right", fill="y")
        self.results.configure(yscrollcommand=result_scroll.set)

        filter_row = ttk.Frame(right)
        filter_row.pack(fill="x")
        ttk.Label(filter_row, text="控件与功能入口（位置状态来自 UIA，操作未验证）").pack(side="left")
        ttk.Checkbutton(filter_row, text="隐藏无效矩形/屏幕外控件", variable=self.only_located,
                        command=self.render_tree).pack(side="right")
        tree_frame = ttk.Frame(right)
        tree_frame.pack(fill="both", expand=True, pady=5)
        self.tree = ttk.Treeview(tree_frame, columns=("name", "role", "location", "purpose", "operation", "aid"), show="tree headings")
        self.tree.heading("#0", text="节点 ID")
        self.tree.heading("name", text="控件名称")
        self.tree.heading("role", text="类型")
        self.tree.heading("location", text="屏幕位置")
        self.tree.heading("purpose", text="作用（推测/提示）")
        self.tree.heading("operation", text="怎么操作（接口/待确认）")
        self.tree.heading("aid", text="Automation ID")
        self.tree.column("#0", width=92, stretch=False)
        self.tree.column("name", width=170, stretch=True)
        self.tree.column("role", width=125, stretch=False)
        self.tree.column("location", width=130, stretch=False)
        self.tree.column("purpose", width=190, stretch=True)
        self.tree.column("operation", width=185, stretch=True)
        self.tree.column("aid", width=135, stretch=True)
        tree_scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll_y.pack(side="right", fill="y")
        tree_scroll_x.pack(side="bottom", fill="x")
        self.tree.bind("<<TreeviewSelect>>", self.show_details)

        ttk.Label(right, text="选中控件的采集证据 / 属性（候选操作不是已验证功能）").pack(anchor="w")
        details_frame = ttk.Frame(right)
        details_frame.pack(fill="both", expand=False)
        self.details = tk.Text(details_frame, height=11, wrap="word", state="disabled")
        self.details.pack(fill="both", expand=True)
        ttk.Label(outer, textvariable=self.status, relief="sunken", padding=5).pack(fill="x", pady=(8, 0))

    def refresh_windows(self) -> None:
        try:
            self.windows = list_windows()
        except Exception as exc:
            messagebox.showerror("无法枚举窗口", str(exc))
            return
        self.window_list.delete(0, "end")
        for w in self.windows:
            self.window_list.insert("end", f"{w.title[:58]}   [PID {w.pid}, HWND {w.hwnd}]")
        self.status.set(f"找到 {len(self.windows)} 个可见且有标题的窗口，选择一个后扫描。")

    def refresh_snapshots(self, select_id: int | None = None) -> None:
        self.snapshots = self.db.list_scans()
        self.snapshot_list.delete(0, "end")
        for i, snap in enumerate(self.snapshots):
            self.snapshot_list.insert("end", f"#{snap['id']}  {snap['title'][:30]} ({snap['node_count']} 项)")
            if snap["id"] == select_id:
                self.snapshot_list.selection_clear(0, "end")
                self.snapshot_list.selection_set(i)
                self.snapshot_list.see(i)

    def scan_selected(self) -> None:
        if self.busy:
            return
        index = self.window_list.curselection()
        if not index:
            messagebox.showinfo("请选择窗口", "请选择一个要扫描的软件窗口。")
            return
        try:
            limits = Limits(max_depth=int(self.max_depth.get()), max_nodes=int(self.max_nodes.get()), max_seconds=30.0)
        except ValueError:
            messagebox.showerror("参数错误", "最大深度和最大控件数必须为正整数。")
            return
        selected = self.windows[index[0]]
        selected_windows = [w for w in self.windows if w.pid == selected.pid]
        self.busy = True
        self.scan_button.configure(state="disabled")
        self.status.set(f"扫描 PID {selected.pid}，扫描期间请勿关闭目标软件窗口…")
        thread = threading.Thread(
            target=self._scan_worker,
            args=(selected_windows, selected.pid, limits, self.include_text.get()),
            daemon=True,
        )
        thread.start()

    def _scan_worker(self, windows: list[WindowInfo], pid: int, limits: Limits, include_text: bool) -> None:
        try:
            from .service import scan_windows
            result = scan_windows(windows, pid, limits, include_text)
            scan_id = self.db.save(result)
            report_path = self.db.export_txt(scan_id, default_report_path(scan_id, pid))
            self.messages.put(("complete", (scan_id, len(result.nodes), result.truncated, len(result.errors), str(report_path.resolve()))))
        except Exception as exc:
            self.messages.put(("error", f"{type(exc).__name__}: {exc}"))

    def _pump(self) -> None:
        try:
            while True:
                kind, data = self.messages.get_nowait()
                self.busy = False
                self.scan_button.configure(state="normal")
                if kind == "error":
                    self.status.set(f"扫描失败：{data}")
                    messagebox.showerror("扫描失败", data)
                else:
                    scan_id, count, truncated, error_count, report_path = data
                    self.refresh_snapshots(select_id=scan_id)
                    self.load_snapshot(scan_id)
                    self.active_report_path = Path(report_path)
                    self.report_label.set(f"TXT 报告：{report_path}")
                    self.status.set(f"扫描 #{scan_id} 完成：{count} 个控件，{error_count} 个窗口错误；{'已截断' if truncated else '未截断'}。TXT 已自动生成。")
                    self.open_text_current()
        except queue.Empty:
            pass
        self.root.after(120, self._pump)

    def open_selected_snapshot(self, _event: Any = None) -> None:
        selection = self.snapshot_list.curselection()
        if selection:
            self.load_snapshot(int(self.snapshots[selection[0]]["id"]))

    def load_snapshot(self, scan_id: int) -> None:
        record = self.db.get(scan_id)
        self.active_scan_id = scan_id
        self.active_report_path = default_report_path(scan_id, record["pid"]).resolve()
        self.report_label.set(f"TXT 报告：{self.active_report_path}")
        self.current_nodes = {n["id"]: n for n in record["nodes"]}
        self.render_tree()
        self.results.delete(0, "end")
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("end", f"扫描 #{scan_id}  |  {record['title']}  |  PID {record['pid']}\n"
                            f"控件 {len(record['nodes'])}，其中候选交互控件 {record['summary']['action_candidates']}；"
                            f"截断={record['truncated']}\n注意：只能识别当前可见的窗口与暴露的结构，未验证功能意义。")
        self.details.configure(state="disabled")
        self.status.set(f"已载入扫描 #{scan_id}（{len(record['nodes'])} 个控件）。")

    def render_tree(self) -> None:
        """Show positive-size controls plus ancestors by default; all UIA nodes remain saved."""
        if not hasattr(self, "tree"):
            return
        self.tree.delete(*self.tree.get_children())
        nodes = list(self.current_nodes.values())
        visible_ids = tree_visible_ids(nodes, only_located=self.only_located.get())
        for node in nodes:
            if node["id"] not in visible_ids:
                continue
            parent = str(node["parent_id"]) if node["parent_id"] is not None else ""
            if parent and not self.tree.exists(parent):
                parent = ""
            status = location_status(node)
            label = "可定位" if status == "located" else "屏幕外" if status == "offscreen" else "无有效矩形"
            self.tree.insert(parent, "end", iid=str(node["id"]), text=f"#{node['id']}",
                             values=(node.get("name") or "(未获取)", node["role"], label,
                                     node.get("purpose") or "未知", node.get("operation") or "待重新扫描",
                                     node.get("automation_id") or ""))
        for item in self.tree.get_children():
            self.tree.item(item, open=True)
        if self.active_scan_id is not None:
            self.status.set(f"扫描 #{self.active_scan_id}: 已显示 {len(visible_ids)}/{len(nodes)} 节点；"
                            "隐藏项仍在 TXT 完整树中。取消筛选可查看全部。")

    def show_details(self, _event: Any = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        node = self.current_nodes.get(int(selection[0]))
        if not node:
            return
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("end", f"位置判断: {location_explanation(node)}\n"
                            "注：UIA 操作模式不表示当前一定能够点击或切换。\n\n")
        self.details.insert("end", json.dumps(node, ensure_ascii=False, indent=2))
        self.details.configure(state="disabled")

    def search(self) -> None:
        query = self.query.get().strip()
        if not query:
            self.status.set("请输入要查询的控件名称、作用或位置。")
            return
        self.search_matches = self.db.search(query, self.active_scan_id, limit=200)
        self.results.delete(0, "end")
        for node in self.search_matches:
            self.results.insert("end", f"#{node['id']} [{node['role']}] {node.get('name') or '(未获取)'}  (扫描 {node['scan_id']})")
        self.status.set(f"搜索到 {len(self.search_matches)} 个匹配项（最多展示 200 个）。双击跳转。")

    def focus_result(self, _event: Any = None) -> None:
        selection = self.results.curselection()
        if not selection:
            return
        match = self.search_matches[selection[0]]
        if match["scan_id"] != self.active_scan_id:
            self.load_snapshot(match["scan_id"])
        iid = str(match["id"])
        if not self.tree.exists(iid) and self.only_located.get():
            self.only_located.set(False)
            self.render_tree()
        if self.tree.exists(iid):
            ancestor = self.tree.parent(iid)
            while ancestor:
                self.tree.item(ancestor, open=True)
                ancestor = self.tree.parent(ancestor)
            self.tree.selection_set(iid)
            self.tree.see(iid)
            self.tree.focus(iid)

    def open_text_current(self) -> None:
        if self.active_scan_id is None:
            messagebox.showinfo("没有扫描", "请先选择一个扫描记录。")
            return
        try:
            path = self.active_report_path or default_report_path(self.active_scan_id, self.db.get(self.active_scan_id)["pid"])
            if not path.is_file():
                path = self.db.export_txt(self.active_scan_id, path)
            self.active_report_path = path.resolve()
            self.report_label.set(f"TXT 报告：{self.active_report_path}")
            os.startfile(str(path))
        except Exception as exc:
            messagebox.showerror("打开 TXT 失败", f"{exc}\n可以使用‘另存 TXT’将报告保存到指定位置。")

    def export_text_current(self) -> None:
        if self.active_scan_id is None:
            messagebox.showinfo("没有扫描", "请先选择一个扫描记录。")
            return
        dest = filedialog.asksaveasfilename(
            title="将扫描结果保存为可阅读的 TXT",
            initialfile=f"scan-{self.active_scan_id}.txt",
            defaultextension=".txt", filetypes=[("文本文件", "*.txt")],
        )
        if dest:
            self.db.export_txt(self.active_scan_id, dest)
            self.report_label.set(f"TXT 已另存：{Path(dest).resolve()}")
            self.status.set(f"已导出 TXT：{dest}")

    def export_current(self) -> None:
        if self.active_scan_id is None:
            messagebox.showinfo("没有扫描", "请先打开一个历史扫描。")
            return
        dest = filedialog.asksaveasfilename(
            title="导出扫描 JSON（可能包含窗口标题或用户数据）",
            initialfile=f"scan-{self.active_scan_id}.json",
            defaultextension=".json", filetypes=[("JSON", "*.json")],
        )
        if dest:
            self.db.export_json(self.active_scan_id, dest)
            self.status.set(f"已导出 {dest}")


def run_gui(db_path: str) -> None:
    root = tk.Tk()
    InventoryApp(root, db_path)
    root.mainloop()
