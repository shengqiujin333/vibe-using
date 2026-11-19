# Vibe Using — Windows UI 界面发现器（MVP）

第一阶段实验：通过 **Windows UI Automation (UIA)** 对正在运行的软件进行**只读**界面普查，建立本地可搜索的控件树知识库，为以后“软件功能知识 → 操作 SOP → 自动执行”提供数据基础。

> 当前版本是 **界面发现器**，不是自动操作 Agent，也不是“全部软件功能已经发现”。它不会点击按钮、打开菜单、模拟键盘、执行软件命令，也不会调用云端 AI。

## 已实现

- 枚举 Windows 当前**可见且有标题**的顶层窗口，按 PID 选定软件。
- 扫描同一 PID 的已枚举顶层窗口及它们可访问的 UIA 子控件；采集层级、角色/类型、名称、AutomationId、ClassName、键盘快捷键属性、启用状态、边界框。
- 限制最大深度、节点数和扫描时间；记录不可访问/读取失败，明确标记截断；注意某一次 UIA API 调用可能超时阻塞，时间限制不是强制杀进程。
- 保存每次扫描到本机 **SQLite**；GUI 树形浏览、属性检查、搜索，保留历史记录，导出 JSON。
- 命令行列出窗口、指定 PID 扫描、历史搜索和 JSON 导出。
- 根据控件类型标出 **action_candidate（候选交互控件）**；这是启发式分类，**不是已经验证的业务功能或操作 SOP**。
- 默认不保存 Text/Edit/Document 类型控件的 Name，也不读取 ValuePattern/输入框值；密码控件的 Name 始终被清除。

## Windows 安装

需 Windows 10/11，Python **3.10+**，推荐 Python 3.11/3.12。当前版本需要在目标软件所在的**本地交互式桌面**运行。

```powershell
# PowerShell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
python -m vibe_using
```

如果 PowerShell 禁止激活虚拟环境，可以直接运行 `.\.venv\Scripts\python.exe -m pip install -e .` 和 `.\.venv\Scripts\python.exe -m vibe_using`。

### 图形界面操作

1. 打开 Windows 记事本、计算器或你想分析的专业软件，保持窗口可见。
2. 运行 `python -m vibe_using`，点击“刷新窗口”。
3. 选择目标软件窗口，点击“扫描选中软件”。同一进程的可见窗口会一起扫描。
4. 在右侧查看 UIA 控件层级，点击节点查看属性，使用搜索框定位控件。
5. 通过“导出 JSON”保存快照，作为下一步功能语义识别和 SOP 设计的输入。

### 命令行 / 无 GUI

```powershell
# 枚举当前窗口（包含 PID、HWND）
python -m vibe_using --list-windows

# 把 PID 替换成真实进程 ID；仅扫描，不点击
python -m vibe_using --scan-pid 1234 --max-depth 10 --max-nodes 5000 --output scan-notepad.json

# 在已采集的快照中搜索；可按扫描号过滤
python -m vibe_using --search "Button"
python -m vibe_using --search "保存" --scan-id 1

# 从数据库导出历史快照
python -m vibe_using --export-scan 1 --output exports/scan-1.json

# 特别需要 Text/Edit/Document 名称时，显式开启（可能含敏感数据）
python -m vibe_using --scan-pid 1234 --include-text
```

默认数据库：`%USERPROFILE%\.vibe-using\inventory.sqlite3`。可用 `--db path\to\inventory.sqlite3` 自定义。

## 项目结构

```text
vibe_using/
  win32.py          # Win32 顶层窗口枚举
  uia_backend.py    # UIA 属性读取，不进行 Invoke/Click/SetValue
  scanner.py        # 有界控件树遍历，可注入模拟后端
  models.py         # 结构化扫描契约
  database.py       # SQLite 持久化、检索、JSON 导出
  gui.py            # Tkinter 树形浏览界面
  cli.py            # 命令行入口
  service.py        # UIA 扫描启动和 COM 生命周期
 tests/             # 不依赖真实 Windows 目标程序的测试
```

## 数据的含义与局限

- **UIA 不等于软件功能全集。** 只能读取当时暴露的窗口/控件，不会枚举尚未打开的菜单、隐藏弹窗、状态限定功能、部分自绘画布或插件功能。
- **本版本不主动探索。** 为安全起见不会自动展开菜单或修改目标状态；后续可增加独立的、需授权的沙箱探索 Agent。
- **进程并非软件边界。** 多进程 Electron/浏览器应用可能需要分别扫描不同 PID；具有系统级权限差异的窗口可能返回部分节点或访问失败。
- **GUI 名称不是语义真相。** “导出”按钮仅为一个发现结果，其业务作用、输入、输出、前置条件和正确性尚未验证。
- **扫描不保证完全无个人信息。** 窗口标题、菜单/按钮名称、AutomationId 仍可能包含文件名、账号或组织信息。SQLite/导出 JSON 仅存本地，发送给第三方前请人工检查。
- **不绕过权限或付费。** 仅在用户授权、正常登录的交互式桌面操作，禁止用作绕过访问控制或网站限制。

## 自动测试

```powershell
python -m unittest discover -s tests -v
```

模拟后端的测试可在 Windows、macOS 或 Linux 上运行；**实际 UIA 枚举必须在 Windows 本地交互式桌面验证**，GitHub CI 无法替代真实专业软件现场测试。

## 下一阶段（尚未实现）

1. 引入文档/软件手册与扫描节点的语义关联，生成带证据和信心等级的“功能知识节点”。
2. 在安全测试工程中允许有限、可回滚的菜单/弹窗探索，建立界面状态跳转图。
3. 对功能产出参数化操作 SOP，并加入自动重放与外部结果独立验收。
4. 复用相同知识模型适配 Web DOM/Accessibility，并接入上层能力流。
