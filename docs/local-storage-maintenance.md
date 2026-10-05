# 本地文件整理、查找与恢复

本规则由用户在 2026-10-06 明确要求建立，适用于 NetConfigLint 本地项目目录。维护总入口为 [项目索引](../PROJECT_INDEX.md) 和 [项目工作规则](../AGENTS.md)。具体占用、清理清单、验证与限制记录在本机 `archive/maintenance/2026-10-06/REPORT.zh-CN.md`。

## 发布包的保留单位

以 **平台 + 架构 + 包类型** 为一个单位，每个单位保留最新合格的稳定发布包。Windows ZIP、Windows MSI、Linux amd64 DEB、macOS arm64 PKG 分别维护；将来新增架构或包格式时也要独立比较。先核对公开 Release 的实际资产、下载可达性、文件大小和 SHA-256，再清理被替代的包。只发布 Windows ZIP 的新版不会替代旧 Linux、macOS 或 MSI。

```powershell
python scripts/local_storage.py releases
python scripts/local_storage.py scan
```

`releases` 读取当前 GitHub API，按版本号选择每类最新稳定资产；不会下载或删除文件。预发布与草稿不自动替代稳定版。`release/` 的本地文件只保留各类最新正式包和对应校验文件；旧版本的资产 ID、固定下载地址、大小和哈希保存在本地快照与恢复清单中。

## 哈希不同怎么判断

先比较包内文件和用途，不能只比较整包 SHA-256：

1. 仅 ZIP 时间戳、压缩数据或目录布局不同：复用可验证的公共内容，保存必要包装差异。
2. 新增历史、设置、用户导出或临时编辑文件：单独保留数据和原路径，共享程序文件不重复保存。
3. EXE、依赖、资源、补全资料或功能不同：结合源码版本与验收记录判断；必要候选内容保存差异，不能猜成普通使用痕迹。
4. 未发布版本、唯一证据或不能证明可恢复的内容：保留所需内容，再去重和压缩。

2026-10-06 的候选 ZIP 使用原始字节分段保存：共享段指向已核验的正式 ZIP，其他段保存在本地内容库。恢复时拼接字节，并检查完整旧包的大小和 SHA-256。这保留原包，而不是用同名正式包替代本地差异。

## 找旧脚本、命令、记录或包

从项目根目录使用显式 Python 解释器执行，不通过 Windows 的 `.py` 文件关联启动脚本。

```powershell
python scripts/local_storage.py locate "capture_gui"
python scripts/local_storage.py locate "release/NetConfigLint-2.4.0-windows-x64-portable.zip"
python scripts/local_storage.py locate "build/acceptance-ci-35098339987b/native/smoke-result.json"
```

清单记录原路径、大小、SHA-256、保存方式和恢复来源。2026-09-24 迁移过的 `build/<名称>` 路径会先按 `archive/build-path-map-2026-09-24.csv` 映射。一次性改码脚本归档后供查阅；重新运行前先阅读其目标和前提。

主要保存方式如下：

| 清单类型 | 保存/恢复位置 |
| --- | --- |
| `blob` | 本地 `content.zip` 内的唯一内容；多个原路径可共用一个条目 |
| `local` | 修复相对链接前的原文等专门快照；独立本地文件也纳入哈希校验 |
| `release` / `release-member` | 对应正式包或其 ZIP 成员；固定公开 URL、大小和 SHA-256 |
| `package-delta` | 本地差异段与正式 ZIP 的共享段；重建后检查整个原包哈希 |
| `archive-member` | 保留候选包/工具包内的原始 ZIP 成员 |
| `upstream` | 与 PyPI 或官方 Python 发布资产完全一致的下载件 |
| `regenerate` | 可重新生成的工具缓存、字节码或已记录依赖版本的旧环境 |
| `link-record` | 只记录测试别名/合成符号链接及目标，不跟随或自动创建外部链接 |
| `historical-reference` | 本次整理前即缺失的历史路径，附原文档和原任务定位 |

## 恢复和验证

```powershell
python scripts/local_storage.py restore "build/native_max_probe.py"
python scripts/local_storage.py restore "release/NetConfigLint-2.4.0-windows-x64-portable.zip" --download
python scripts/local_storage.py restore "build/v30/source-final-smoke" --tree --download
python scripts/local_storage.py verify
```

恢复默认写入 `build/restored-history/<原路径>`；也可用 `--to build/其他独立目录` 指定项目内独立目标。拒绝覆盖现有文件、越界路径和目录联接/符号链接。缺少正式包或上游依赖时，只有显式 `--download` 才会下载；下载地址受来源约束，下载与最终输出均核验 SHA-256。

`--tree` 恢复目录下已经归档的关联文件，供旧脚本及配套结果一起使用；保留在原位置的可读报告和脚本可以直接打开。缓存、链接指针及缺失原始证据的引用会跳过，已恢复且哈希一致的文件不会重复写入。

`verify` 校验本地归档全部条目的大小、CRC 和 SHA-256，核对路径清单与内容库的成员关系。它不重新下载所有远端资产；网络核验和实际恢复测试记录在对应维护目录。缓存和旧环境需要重建；缺失于整理前的原始证据不会被伪造。

## 以后持续整理

- 保留一个经过验证的当前 `.venv`；旧环境先保存依赖版本、安装元数据和来源，再删除依赖载荷。
- 清理缓存、字节码、临时解压和构建副本；旧脚本/日志/截图/资料先按内容去重。直接可读的审计报告、问题登记及其 Markdown 附件保留原路径。
- 保留源码、测试、许可、厂商资料、Git 引用、未发布改动和用户数据。源码快照、旧增量和离线 bundle 维持校验记录。
- 新清理批次先扫描与规划，再验证恢复资料、执行删除、复查遗漏/引用、更新索引。新的内容库须同步更新查找工具和关联清单；旧批次恢复依赖不能断开。
- 只有已核验、被替代的共享内容可删。不能整目录清空 `archive/`，也不能只把旧构建目录搬进去后永久放任增长。

本地归档和正式包索引不等于异地备份。部分历史恢复依赖固定版本的公开下载；公开资产后来删除或网络不可用时，对应恢复会受影响。重要的独有资料保存在本地内容库；用户数据备份保留原目录。`archive/`、`release/`、`build/` 和 `docs/audits/` 已被 Git 忽略，历史私有资料不随源代码发布。
