# Vibe Using — Windows UI 界面发现器（MVP）

第一阶段实验：通过 **Windows UI Automation (UIA)** 对正在运行的软件进行**只读**控件与功能入口采集，建立本地可搜索的名称—位置—作用线索—操作接口知识库，为以后“软件功能知识 → 操作 SOP → 自动执行”提供数据基础。

> 当前版本是 **界面发现器**，不是自动操作 Agent，也不是“全部软件功能已经发现”。它不会点击按钮、打开菜单、模拟键盘、执行软件命令，也不会调用云端 AI。

## 已实现

- 枚举 Windows 当前**可见且有标题**的顶层窗口，按 PID 选定软件。
- 扫描同一 PID 的已枚举顶层窗口及 UIA 子控件；采集层级、角色/类型、UIA Name、AutomationId、ClassName、快捷键、启用状态、边界框。
- **加强控件名称采集**：优先 UIA `Name`，空名称时尝试 `LabeledBy` 和 `LegacyIAccessible.Name`；对只有一个直接文本子节点的按钮/容器尝试合并标签，明确标记名称来源。获取不到的保留“未获取”，不编造。
- **采集功能线索**：记录 UIA `HelpText`、LocalizedControlType 与可能支持的 Invoke / ExpandCollapse / SelectionItem / Toggle / Value 等模式；只检查模式是否存在，不实际调用操作。
- **记录在哪里**：为每个控件生成界面层级路径，保留当前屏幕矩形和 AutomationId；界面变化后路径与坐标均需重新确认。
- **记录作用及操作方式**：优先展示 UIA HelpText 和被报告的接口；针对常见名称提供有限的“可能用途”提示，全部明确标记为**推测或未验证**。
- 限制最大深度、节点数和扫描时间；记录不可访问/读取失败，明确标记截断；注意某一次 UIA API 调用可能超时阻塞，时间限制不是强制杀进程。
- 保存每次扫描到本机 **SQLite**；GUI 树形浏览、属性检查、搜索，保留历史记录；**扫描后自动生成并打开 TXT 文本报告，报告开头优先列出**有名称的交互控件及常见菜单入口**（名称、位置、作用线索、操作方式），完整原始控件树放在后半部分**，也可另存 TXT/导出 JSON。
- 命令行列出窗口、指定 PID 扫描、历史搜索和 TXT/JSON 导出；扫描会**直接在终端打印完整控件树**。
- 根据控件类型标出 **action_candidate（候选交互控件）**；这是启发式分类，**不是已经验证的业务功能或操作 SOP**。
- 默认保存 `TextControl.Name`（软件菜单标签常在这里）；默认**不保存 Edit/Document 的原始 Name**，但保留其 `LabeledBy` 标签；不会读取 ValuePattern 值或 Document 正文。密码控件 Name/帮助文字/标签始终不收集。
- **注意隐私变化**：TextControl 的 Name 有时会包含文件名、聊天记录或业务数据；此版本不会上传网络，但 TXT/SQLite 文件可能包含这些信息，分享前请核实。

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
5. **扫描结束后自动生成并打开 `.txt` 文件**。先阅读“可识别的功能与菜单入口”，每项包含“在哪里、叫什么、可能有什么用、怎样操作”；后面再看完整控件树。左侧还有“打开 TXT”和“另存 TXT”按钮，**无需打开 SQLite**。

默认 TXT 保存位置：**运行命令的目录下 `scans` 文件夹**。例如从 `E:\learn\vibe-using` 运行，就保存在 `E:\learn\vibe-using\scans\scan-扫描编号-pid-进程号.txt`。使用 UTF-8 BOM，中文记事本可直接打开。

### 命令行 / 无 GUI

```powershell
# 枚举当前窗口（包含 PID、HWND）
python -m vibe_using --list-windows

# 把 PID 替换成真实进程 ID；仅扫描，不点击
# 将控件树直接打印在 PowerShell，同时自动生成 scans\scan-N-pid-1234.txt
python -m vibe_using --scan-pid 1234 --max-depth 10 --max-nodes 5000

# 仍支持可选的 JSON 导出
python -m vibe_using --scan-pid 1234 --output scan-notepad.json

# 在已采集的快照中搜索；可按扫描号过滤
python -m vibe_using --search "Button"
python -m vibe_using --search "保存" --scan-id 1

# 将历史扫描重新导出为 TXT（可选自定义位置）
python -m vibe_using --export-txt 1 --output scan-1.txt

# 如需要机器处理数据，也能导出 JSON
python -m vibe_using --export-scan 1 --output exports/scan-1.json

# 特别需要 Edit/Document 的原始 Name 时显式开启（可能含敏感数据）
python -m vibe_using --scan-pid 1234 --include-text
```

默认数据库：`%USERPROFILE%\.vibe-using\inventory.sqlite3`。可用 `--db path\to\inventory.sqlite3` 自定义。

## 项目结构

```text
vibe_using/
  win32.py          # Win32 顶层窗口枚举
  uia_backend.py    # UIA 属性读取，不进行 Invoke/Click/SetValue
  scanner.py        # 有界控件树遍历，可注入模拟后端
  knowledge.py      # 命名来源、界面路径、功能与操作线索（无执行）
  models.py         # 结构化扫描契约
  database.py       # SQLite 持久化、检索、TXT/JSON 导出
  text_report.py    # 人类可读的树形 TXT 报告
  gui.py            # Tkinter 树形浏览界面
  cli.py            # 命令行入口
  service.py        # UIA 扫描启动和 COM 生命周期
 tests/             # 不依赖真实 Windows 目标程序的测试
```

## Chromium / Electron：只有 PaneControl 的恢复尝试（v0.6）

此前扫描曾有 1733 个控件，后续却只有几个没有名称的 `PaneControl`，
这属于 **Chromium 内容树未采集到**，不能据此认定软件没有功能。

新版采用有限的三级只读恢复路径：

1. 常规 UIA RawViewWalker 控件树扫描；
2. 如果判定是 Chromium 空外壳，对旧式 `Chrome_RenderWidgetHostHWND` 子窗口以及
   `Chrome_WidgetWin_1` **顶层窗口**发送带超时的 WM_GETOBJECT 请求，再扫描；
   现代 Chromium 可能根本没有独立的渲染子 HWND；
3. 如果仍未恢复，使用 UIA `ElementFromPoint` 在**该应用实际位于前台、没有遮挡**的
   窗口区域只读查询少数 UIA 元素，沿父节点定位文档/功能子树，再有限度扫描。

注意：**第 3 种方式只能得到部分区域子树，不保证全部功能。** 报告会标明来源。

GUI 扫描时会**暂时隐藏 Vibe Using 自己的窗口**，避免挡住被扫描的应用，
扫描结束或报错会恢复 GUI。目标软件本身不会被点击、激活、改写或重启。
若目标软件被第三方窗口覆盖，屏幕点查询会跳过该位置并在 TXT 显示遮挡数。

恢复失败时：TXT 明确标记“扫描不完整”，不会将空白内容当作软件功能清单。
诊断区会显示有没有独立渲染 HWND、顶层请求次数、屏幕点查询/遮挡情况。
这些是**诊断信息**，不能证明软件不支持 UIA 或某种版本参数。

**推荐复测：** 保持嘉立创 EDA 打开并最大化、当前桌面无遮挡，再从 Vibe Using
选择其窗口扫描。若继续失败，提供 TXT 的前 30 行和文末“扫描诊断 / 异常”。
不要未经确认地给正在编辑的生产软件添加启动参数或重新启动应用。

本地离线单元测试验证恢复调度、窗口目标限制及误判保护；由于这里无法运行真实
Windows 嘉立创 EDA，**没有承诺已解决该软件在你电脑上的 UIA 暴露问题**。

## 数据的含义与局限

- **UIA 不等于软件功能全集。** 只能读取当时暴露的窗口/控件，不会枚举尚未打开的菜单、隐藏弹窗、状态限定功能、部分自绘画布或插件功能。
- **本版本不主动探索。** 为安全起见不会自动展开菜单或修改目标状态；后续可增加独立的、需授权的沙箱探索 Agent。
- **进程并非软件边界。** 多进程 Electron/浏览器应用可能需要分别扫描不同 PID；具有系统级权限差异的窗口可能返回部分节点或访问失败。
- **GUI 名称不是语义真相。** 作用字段是界面 HelpText 或名称关键词产生的线索，绝不是专业功能验证。`InvokePattern` 存在也不能保证该操作能成功。
- **“每个控件有名称”并不保证。** UIA 信息是否存在取决于软件如何实现；没有可读名称、标签或子文本时保持未知。Canvas 自绘区域内的工具命令尤其可能缺失。
- **历史扫描不会自动补充新字段。** 更新后请重新扫描软件；历史快照仍可打开，但位置、作用、操作方式等可能显示待重新扫描。
- **扫描不保证完全无个人信息。** 窗口标题、菜单/按钮名称、AutomationId 仍可能包含文件名、账号或组织信息。SQLite/TXT/JSON 都只存本地，发送给第三方前请人工检查。
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

## 重新扫描嘉立创 EDA 的建议

先打开嘉立创 EDA 专业版，在有原理图/PCB 的情况下进行一次只读扫描；然后打开“文件”菜单再扫一次。**程序不会替你打开菜单**，否则可能误触发真实操作。比较两份 TXT 开头的入口目录，观察哪些名称和模式新增。

预计仍会出现一些 `GroupControl` 只有菜单名、但无 `InvokePattern` 的情况。这表示软件未通过 UIA 暴露对应可执行接口；不能据此推断软件不支持该功能。


### 为什么会出现很多 `CheckBoxControl` 和 `(0,0,0,0)`？（v0.4）

一些 Chromium/Electron 应用（包括部分编辑器）会在 UIA 树中暴露**尚未显示的属性字段**、
隐藏的 HTML 表单元素或虚拟控件；它们可能有名称、`IsEnabled=True`、`TogglePattern`，但没有有效的屏幕矩形。
这些控件不等同于屏幕上可点的按钮。`(0,0,0,0)` 不表示左上角，而表示缺失有效可点击尺寸。

新版 GUI 默认勾选“**隐藏无效矩形/屏幕外控件**”，显示有有效矩形的控件及其父节点；取消勾选可查看全部。
TXT 报告优先列出**有有效屏幕矩形的功能入口**，将属性面板单独分类，未定位的候选只显示摘要（前 30 条）。
**原始树依然完整保留**，以便后续探索或比对，无需重新扫描已有快照即可重新导出新的 TXT。

注意“有效矩形”只是 UIA 给出了非零区域，不保证视觉上可见、未被遮挡或操作一定有效。
`HelpText` 未提供时，软件功能仍然未知；不能将 `TogglePattern` 解释为具体验证过的业务操作。
