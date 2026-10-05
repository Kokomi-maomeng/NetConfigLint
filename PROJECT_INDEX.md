# NetConfigLint 项目总索引

更新时间：2026-10-06。当前源码为 v3.0.0，产品基线提交 `7854236c700e1d23a59b35ce71ca01a483de1396`；`v3.0.0` 标签解析到同一提交。GitHub 已公开发布 Windows 便携 ZIP、Windows MSI、Linux amd64 DEB 和 macOS arm64 PKG。

先读本文。空间维护规则见 [本地文件整理、查找与恢复](docs/local-storage-maintenance.md) 与 [项目工作规则](AGENTS.md)。本次完整扫描、删除清单、恢复验证和占用结果在本机 [2026-10-06 清理报告](archive/maintenance/2026-10-06/REPORT.zh-CN.md)。本地私有目录已被 Git 忽略。

## 当前开发与发布资料

- 产品源码：`netconfiglint/`；可复用构建、发布与验证脚本：`scripts/`、`.github/workflows/`；测试：`tests/`；许可：`licenses/`、`THIRD_PARTY_NOTICES.md`。当前可用开发环境 `.venv/` 保留。
- [v3.0 修复记录](docs/v3.0-ux-repairs.md)、[命令支持范围](docs/v3.0-command-support.md) 与 [公开 v3.0.0 Release](https://github.com/Kokomi-maomeng/NetConfigLint/releases/tag/v3.0.0)。本地 `release/` 仅保留各平台/架构/包类型最新合格包和校验文件，旧包按固定下载地址或候选差异恢复。
- 后续验收问题：本机 [Debian/Linux 与 Windows 用户体验报告](docs/audits/v3.0.0-linux-user-2026-10-05/REPORT.zh-CN.md) 和 [问题登记](docs/audits/v3.0.0-linux-user-2026-10-05/问题登记.csv)。L01–L14 与 W-OBS01 保留原记录；文件清理没有修复这些产品问题。
- 历史审计报告、原聊天 ID 和产物关系见 [聊天与任务目录](archive/TASKS.md)。上次整理的状态是 2026-09-24 的历史记录，以新的索引、实际 Git/Release 和恢复清单为准。

## 历次版本与记录

| 阶段 | 主要内容 | 记录 |
| --- | --- | --- |
| 初版 | v1.0/v1.1 Beta，离线核心、CLI/QML 雏形 | `docs/release-v1.0.0-beta.1.md`、`docs/release-v1.1.0-beta.1.md` |
| v1.2 | Huawei 规则与用例、便携包及三端 CI | `docs/release-v1.2.0.md` |
| v1.3 | QML 交互、布局、编辑器和便携包 | `docs/release-v1.3.0.md` |
| v1.4 | Material 界面与导出，完整审计 | `docs/v1.4-acceptance.md`；本机 `archive/evidence/v1.4-audit-full/` |
| v1.5 | 审计修复、Huawei 配置语义与片段模式 | `docs/v1.5-audit-repairs.md`、`docs/v1.5-huawei-repairs.md`、`docs/v1.5-acceptance.md` |
| v2.0 | H3C、UNKNOWN 来源、诊断包与三端安装包 | `docs/h3c-command-support.md`、`docs/v2.0-audit-report.md`、`docs/v2.0-acceptance.md` |
| v2.1 | 检查模式、历史恢复、便携化 | `docs/v2.1-change-scope.md`；没有对应公开 Release，本地必要 ZIP 差异保留 |
| v2.2 | GUI 重建、窗口状态、选区与缩放 | `docs/v2.2-gui-acceptance.md` |
| v2.3 | 窗口四角、设置、查找和卡片布局 | `docs/v2.3-gui-acceptance.md` |
| v2.4 | 通用命令族识别与诊断文案双语 | `docs/v2.4-command-catalog-and-i18n.md` |
| v2.5 | v2.4 审计修复与发布验收 | `docs/v2.5-repairs-and-qualification.md` |
| v2.6 | 厂商独立检测、参数感知补全与完整体验审计 | `docs/v2.6-command-completion.md`；本机 `docs/audits/v2.6.0-user-2026-10-02/` |
| v3.0 | 37 项修复、保存保护、搜索与三端安装程序 | `docs/v3.0-ux-repairs.md`、`docs/v3.0-command-support.md`；新的体验问题见当前报告 |

## 本地归档与旧路径

- [归档说明](archive/README.md)：内容库、源码历史、用户数据、恢复方法和范围。
- `archive/evidence-store/2026-10-06/content.zip` 与 `paths.json.gz`：唯一内容、候选包差异及原路径索引。两者必须配套保留。
- [历史发布入口](archive/versions/README.md)：正式包的原版本页面和候选包定位。
- `archive/build-path-map-2026-09-24.csv`：旧 `build/<名称>` 的第一阶段迁移映射。现在查找工具会继续定位到内容库、公开资产或历史引用。
- `archive/operations-2026-09-24.md`：上次迁移记录，保留当时状态；当前路径以本次清理清单为准。
- `archive/user-data-backups/`：用户数据原备份，保持原目录与字节内容。

```powershell
python scripts/local_storage.py locate "build/native_max_probe.py"
python scripts/local_storage.py restore "build/native_max_probe.py"
python scripts/local_storage.py restore "release/NetConfigLint-2.4.0-windows-x64-portable.zip" --download
```

默认恢复到 `build/restored-history/<原路径>`，不会覆盖当前文件。必要旧候选包按共享段与本地差异精确重建；运行时产生的数据单独保留。缓存/旧环境按记录重建。9 个清理前已缺失的旧引用已登记文档与原聊天位置，不声称其原始输出已经恢复。

## 源码回退与校验

Git 标签、分支和提交仍是源码历史依据。查看旧源码使用 `git worktree add <独立目录> v1.5.0`。本地 `archive/source-history/` 保留原快照、增量及旧 bundle，并新增 `all-refs-2026-10-06.bundle`，覆盖本次维护前的全部本地引用。先运行 `git bundle verify <bundle路径>`，校验和见同目录 `SHA256SUMS.txt`。

历史记录只证明对应提交、包和环境。H3C/Huawei 未建模或未知目标保留 Unknown，托管 macOS 检查不等于所有硬件验收。公开状态在新的发布/清理任务中重新核验。独有资料留在本地内容库；公开恢复依赖可能受后来删除或网络不可用影响，本地归档仍不是异地备份。
