# NetConfigLint 项目总索引

本索引供后续开发任务从当前工作区继续使用。更新时间：2026-09-26。先读本文，再按所需版本打开对应文档和本地归档。Git 标签和提交是源码历史的依据；安装包以 SHA-256 核对，不根据文件名推断版本或发布状态。

## 当前基线

- v2.2 开发分支为 `codex/v2.2-gui-portable`，候选改动见 [PR #6](https://github.com/Kokomi-maomeng/NetConfigLint/pull/6)；此前 `main` 的 v2.1 合并提交为 `0c62984`。公开版本以 Git 标签和 Release 实际资产为准，后续任务应重新检查分支、HEAD、CI 与下载状态。
- v2.0 历史发布文件：`release/` 内 Windows 便携 ZIP、Windows 未签名 MSI、Linux amd64 DEB、macOS arm64 未签名 PKG，以及对应的官方 `SHA256SUMS.txt`。这些文件于 2026-09-24 与 [GitHub v2.0.0 Release](https://github.com/Kokomi-maomeng/NetConfigLint/releases/tag/v2.0.0) 资产 SHA-256 逐项核对。`release/` 为本地目录，已被 Git 忽略。
- v2.2 本地验收产物：`release/NetConfigLint-2.2.0-windows-x64-portable.zip` 与同名 `.sha256`。GitHub Release 会独立构建便携 ZIP，其校验值须与实际下载文件核对；证据和限制见 `docs/v2.2-gui-acceptance.md`。
- 源码入口：`netconfiglint/`；自动化和发布：`scripts/`、`.github/workflows/`；测试：`tests/`；许可：`licenses/`、`THIRD_PARTY_NOTICES.md`。
- 不要将本地 `archive/`、`release/`、`build/`、`.venv/` 或实际设备资料加入 Git。历史审计资料可能包含真实配置导出的分析结果，归档仅留本机。

## 历次版本与增量

| 阶段 | 标签 / 工作内容 | 主要产出与记录 |
| --- | --- | --- |
| 初版 | `v1.0.0-beta.1`、`v1.1.0-beta.1` | 离线分析核心、CLI/QML 桌面雏形、基础 Huawei VRP 规则、早期 ZIP 和安装程序；`docs/release-v1.0.0-beta.1.md`、`docs/release-v1.1.0-beta.1.md`。 |
| v1.2 | `v1.2.0` | Huawei 规则与合成用例扩充、便携包和三端 CI；`docs/release-v1.2.0.md`。 |
| v1.3 | `v1.3.0` | QML 交互、布局、编辑器和便携包改进；`docs/release-v1.3.0.md`。 |
| v1.4 | `v1.4.0` | Material 界面、导出流程；完整审计与复现证据在 `docs/v1.4-acceptance.md` 及本地 `archive/evidence/v1.4-audit-full/`。 |
| v1.5 | `v1.5.0` | 根据 v1.4 审计修复 P1/P2/P3，完善 Huawei 配置语义和默认片段模式；`docs/v1.5-audit-repairs.md`、`docs/v1.5-huawei-repairs.md`、`docs/v1.5-acceptance.md`。 |
| v2.0 | `v2.0.0` | H3C Comware 分析与 UNKNOWN 来源映射、真实诊断包导入/导出、界面细节、四平台打包；`docs/h3c-command-support.md`、`docs/v2.0-audit-report.md`、`docs/v2.0-acceptance.md`。 |
| v2.1 | 合并提交 `0c62984` | 四种检查模式、历史恢复、Windows 便携包；`docs/v2.1-change-scope.md`。本地 ZIP 在 `release/`。 |
| v2.2 | `codex/v2.2-gui-portable`、PR #6 | 窗口状态与 GUI 重建、编辑区选区与缩放、Windows 便携 ZIP；`docs/v2.2-gui-acceptance.md`。Debian 13 已完成 X11 冒烟，macOS 以托管 CI 和源码检查为边界。 |
| 标签后 | `13ee32a` 前的三次提交 | 发布工作流及审计修正；以 `git log v2.0.0..main` 查看。 |

每个标签的完整源码快照、相邻版本的 `git diff --binary` 增量补丁及变更文件清单，保存在本地 `archive/source-history/`。旧版完整发布包及既有解压目录在 `archive/versions/<版本>/`。源码提交、分支和标签仍保留在 Git 中；本地另有 `archive/source-history/all-refs.bundle` 离线备份。

## 归档与任务交接

- `archive/README.md`：本地归档结构、文件来源、恢复方法和范围限制。
- `archive/TASKS.md`：先前 Codex 任务标题、任务 ID、内容、产出及归档状态。任务原文仍保留在 Codex 任务历史中，不复制对话原文或凭据到仓库。
- `archive/build-path-map-2026-09-24.csv`：旧 `build/<名称>` 到分类后位置的逐项映射。历史文档提到旧路径时按此表定位。
- `archive/operations-2026-09-24.md`：整理操作记录、验证及回退说明。

后续在当前“NetConfigLint 项目总任务”继续即可；先前任务作为可检索的归档留存。Codex 没有把多个任务原始消息物理合成为单条对话的功能，因此用此索引与任务 ID 汇总内容和证据。

## 回退与验证

查看旧版源码：`git worktree add <独立目录> v1.5.0`。不要直接覆盖当前工作区。若远端不可用，可用 `git bundle verify archive/source-history/all-refs.bundle` 检查本地备份，再按 Git bundle 的标准流程恢复。旧版安装包按 `archive/release-files.sha256` 校验；v2.2 本地便携包按 `release/NetConfigLint-2.2.0-windows-x64-portable.zip.sha256` 校验，公开便携包按 GitHub Release 提供的 `SHA256SUMS.txt` 校验。

历史测试、CI 和审计只证明对应提交、产物与运行环境。H3C 未建模命令以 UNKNOWN 表示；托管 macOS 验收不代表任意用户硬件。当前功能或公开下载状态应在新任务中重新核实。
