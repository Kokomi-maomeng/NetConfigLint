# NetConfigLint v1.4.0

## 中文

本次更新重做桌面界面、编辑器交互与导出流程，保留 Python Core / CLI / QML 架构和
50 条保守的 Huawei 配置检查规则。

- 采用 CastoriceUI 的 Material 3 字体、配色、圆角、侧栏和过渡节奏，随程序提供
  Roboto 与 Noto Sans SC。侧栏可收缩，设置从左下角弹窗打开，关于保持独立。
- 常规设置支持语言与自定义面板标题；主题支持跟随系统、浅色、深色及十组配色。
- 三个工作卡片可显示或隐藏、拖动排序及调整宽度，文本与缩放状态不会因这些操作丢失。
  界面偏好、卡片显示与排列顺序会保存。
- 操作卡片合并打开、导出、当前模式、当前厂商和显示选项，分析按钮位于右侧。
  移除粘贴、清空按钮、底部状态条和指定的冗余文字、空块。
- 两个编辑器支持 Ctrl+滚轮缩放、动态右对齐行号以及中英文 Material 右键菜单；
  缩放后菜单末尾出现恢复默认大小。修复跨区域文本选择残留、查找快捷键冲突。
- 仅在筛选时显示筛选状态。分析状态移入诊断卡片；空白配置不会启动分析。
  修改配置、模式或厂商后会清除过期结果，后台旧任务不会覆盖新输入。
- 导出前可选择完整内容、仅配置或仅诊断，以及 JSON、Markdown、TXT。
  默认完整报告为完整配置在上、诊断在下；勾选后为诊断在上、带诊断类型数目的代码在下。
  取消、点击弹窗外部或取消系统保存流程均不会生成导出文件。
- 诊断自然语言补齐中文翻译，保留命令、规则 ID、地址和对象名原文。
  厂商选项来自插件注册表；GUI、CLI 和模型中的操作系统识别字段已移除。
- 关于页面中的外部链接改为卡片。

Windows 便携版：下载 `NetConfigLint-1.4.0-windows-x64-portable.zip`，完整解压后运行
其中的 `NetConfigLint.exe`，无需安装 Python。

## English

This release rebuilds the desktop around CastoriceUI's Material 3 design tokens and bundled
Roboto/Noto Sans SC fonts. It adds modal appearance settings, a collapsible sidebar, persistent
panel visibility/order, drag reordering, editor zoom and localized context menus.

Exports now support explicit source/diagnostic scope and JSON, Markdown or text, with either
complete source first or diagnostics first followed by severity-annotated code. Confirmation
opens the system save flow. Diagnostics require a matching current analysis; edits invalidate
stale results and outdated background completions are discarded.

The OS field is removed from `VendorDetection`, plugin metadata, CLI text and GUI output.
API users constructing `VendorDetection` positionally must remove the old second OS argument.
Existing rule severity, confidence and conservative analysis boundaries remain unchanged.

See [acceptance evidence](v1.4-acceptance.md) for the verification scope.
