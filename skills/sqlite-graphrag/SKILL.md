---
name: sqlite-graphrag
description: 基于 sqlite-graphrag 单文件 GraphRAG 引擎的本地知识库构建与 AI 记忆管理技能。适用于：(1) 从零搭建本地私有知识库，将文档/笔记导入为结构化记忆；(2) 通过语义检索（向量+全文混合）和知识图谱多跳推理查询记忆；(3) 为 AI Agent 提供持久化记忆存储；(4) 导入导出知识库数据。触发关键词：GraphRAG、知识图谱、本地知识库、sqlite-graphrag、向量检索、RAG 知识库、AI 记忆、私有知识库、单文件知识库。
---

# sqlite-graphrag 技能

基于 Rust 编译的单文件 GraphRAG 引擎，将知识图谱存储 + 文本向量计算全部内嵌到 SQLite 数据库中，无需部署独立的向量数据库或图数据库。

## 快速开始

### 1. 安装 sqlite-graphrag

从 GitHub Releases 下载预编译二进制（Windows/Linux/macOS）：

```bash
# 前往 https://github.com/daniloaguiarbr/sqlite-graphrag/releases
# 下载对应平台的最新版本（如 sqlite-graphrag-v1.0.68-x86_64-pc-windows-msvc.zip）
# 解压后将 sqlite-graphrag(.exe) 放到 PATH 中
```

> **必须**：本技能所有脚本均依赖 `sqlite-graphrag` 命令行工具，请确保安装后 `sqlite-graphrag --version` 能正常输出版本号。

### 2. 前置检查

确认二进制可用：

```bash
sqlite-graphrag --version
```

### 初始化数据库

```bash
sqlite-graphrag init
```

自动创建 `graphrag.sqlite`（当前目录），下载 `multilingual-e5-small` 嵌入模型（约 465MB）。

> **网络问题**：如果 huggingface.co 无法访问，设置环境变量 `HF_ENDPOINT=https://hf-mirror.com` 使用国内镜像。如果模型文件已下载到本地缓存但 daemon 仍报错，检查 `C:\Users\<用户名>\AppData\Local\sqlite-graphrag\cache\models` 下是否有 `.lock` 文件残留，清理后重试。

### 写入第一条记忆

```bash
sqlite-graphrag remember \
  --name my-first-note \
  --type note \
  --description "我的第一条记忆" \
  --body "这是 sqlite-graphrag 知识库的第一条记忆内容"
```

### 语义检索

```bash
sqlite-graphrag recall "记忆内容" --k 5 --json
```

## 核心能力

### 1. 数据库生命周期管理

| 命令 | 用途 | 常用参数 |
|---|---|---|
| `init` | 初始化数据库 + 下载嵌入模型 | `--namespace <ns>` |
| `health --json` | 检查数据库完整性、FTS5、向量索引 | - |
| `stats --json` | 统计记忆/实体/关系数量 | - |
| `vacuum` | 回收磁盘空间 | - |
| `backup --output <path>` | 备份数据库 | - |
| `sync-safe-copy --dest <path>` | 生成同步安全的快照副本 | - |
| `migrate` | 应用待处理的 schema 迁移 | - |

### 2. 记忆写入

**单条写入：**

```bash
# 内联文本（body 最大 500KB）
sqlite-graphrag remember --name my-note --type note \
  --description "描述" --body "正文内容"

# 从文件读取
sqlite-graphrag remember --name my-note --type note \
  --description "描述" --body-file ./document.txt

# 从标准输入
cat document.txt | sqlite-graphrag remember --name my-note \
  --type note --description "描述" --body-stdin
```

**`--type` 可选值（仅 9 种）：**
`user`, `feedback`, `project`, `reference`, `decision`, `incident`, `skill`, `document`, `note`

> 注意：`tool`、`concept`、`person`、`file` 等不是有效值，会报错退出。

**批量导入目录：**

```bash
# 导入目录下所有 .md 文件（默认 pattern）
sqlite-graphrag ingest ./docs

# 导入 .txt 文件，递归子目录
sqlite-graphrag ingest ./docs --pattern "*.txt" --recursive

# 预览文件到名称的映射（不实际导入）
sqlite-graphrag ingest ./docs --dry-run
```

### 3. 记忆读取与检索

**精确读取：**

```bash
# 按名称
sqlite-graphrag read --name my-note --json

# 按 ID
sqlite-graphrag read --id 1 --json

# 附带图谱信息
sqlite-graphrag read --name my-note --with-graph --json
```

**列出记忆：**

```bash
sqlite-graphrag list --json
sqlite-graphrag list --type project --limit 10 --json
```

**语义检索（向量 KNN）：**

```bash
# 基础检索
sqlite-graphrag recall "查询内容" --k 5 --json

# 带图谱多跳（需先启用 NER 提取实体）
sqlite-graphrag recall "查询内容" --k 5 --max-hops 2 --json

# 按类型过滤
sqlite-graphrag recall "查询内容" --type project --k 5 --json
```

**混合检索（向量 + FTS5 全文）：**

```bash
sqlite-graphrag hybrid-search "关键词" --k 5 --json
```

`hybrid-search` 使用 Reciprocal Rank Fusion (RRF) 融合向量排名和全文搜索排名，返回 `combined_score` 和 `normalized_score`。

### 4. 实体关系图谱

**启用 NER 实体提取：**

NER 默认关闭，需显式启用：

```bash
# 写入时启用 NER
sqlite-graphrag remember --name ner-test --type note \
  --description "NER测试" \
  --body "sqlite-graphrag由daniloaguiarbr开发，使用Rust语言编写" \
  --enable-ner --gliner-variant int8

# 或通过环境变量全局启用
set SQLITE_GRAPHRAG_ENABLE_NER=1
```

GLiNER 模型变体选择：

| 变体 | 大小 | 说明 |
|---|---|---|
| `fp32` | 1.1 GB | 最佳质量（默认） |
| `fp16` | 580 MB | 半精度 |
| `int8` | 349 MB | 最快，短文本可能漏实体 |
| `q4` | 894 MB | 4-bit 量化 |
| `q4f16` | 472 MB | 混合量化 |

**图谱操作：**

```bash
# 导出图谱
sqlite-graphrag graph --format json
sqlite-graphrag graph --format mermaid
sqlite-graphrag graph --format dot --output graph.dot

# 图谱统计
sqlite-graphrag graph stats --json

# 遍历关系
sqlite-graphrag graph traverse --from entity-name --depth 2

# 列出实体
sqlite-graphrag graph entities --entity-type person

# 手动建立关系
sqlite-graphrag link --from entity-a --to entity-b --relation depends-on --strength 0.8

# 删除关系
sqlite-graphrag unlink --from entity-a --to entity-b --relation depends-on
```

### 5. 记忆维护

```bash
# 编辑记忆
sqlite-graphrag edit --name my-note --body "新内容"

# 重命名
sqlite-graphrag rename --name old-name --new-name new-name

# 软删除
sqlite-graphrag forget --name my-note

# 永久删除（不可恢复）
sqlite-graphrag purge

# 查看版本历史
sqlite-graphrag history --name my-note

# 恢复到历史版本
sqlite-graphrag restore --name my-note --version 1
```

### 6. 高级功能

**深度多跳研究：**

```bash
sqlite-graphrag deep-research "研究主题" --k 5 --json
```

**关联记忆查询：**

```bash
sqlite-graphrag related --name my-note --json
```

**LLM 增强（需配置外部 LLM）：**

```bash
sqlite-graphrag enrich --name my-note --mode claude-code
```

## 常见问题与陷阱

### 1. `--type` 限制
`remember` 的 `--type` 只接受 9 种值：`user`, `feedback`, `project`, `reference`, `decision`, `incident`, `skill`, `document`, `note`。README 中提到的 `tool`、`concept`、`person` 等 13 种 entity_type 是图谱实体类型，不是记忆类型，两者不同。

### 2. NER 默认关闭
实体关系提取默认不运行。每次调用需传 `--enable-ner`，或设置环境变量 `SQLITE_GRAPHRAG_ENABLE_NER=1`。GLiNER 模型需额外下载（int8 变体 349MB，fp32 变体 1.1GB）。

### 3. 模型下载问题
首次使用需要从 HuggingFace 下载 `multilingual-e5-small` 模型（约 465MB）。国内网络可能需要设置 `HF_ENDPOINT=https://hf-mirror.com`。如果下载中断导致 `.lock` 文件残留，需清理后重试：
```bash
sqlite-graphrag cache clear-models --yes
```

### 4. Daemon 自动管理
`remember` 和 `recall` 等重型命令会自动启动嵌入 daemon（端口 18789），无需手动启动。升级二进制后 daemon 会自动检测版本不匹配并重启。

### 5. 单进程限制
SQLite 单文件架构不支持多用户高并发。多个进程同时写入可能导致锁冲突。

### 6. 图谱为空
如果 `graph --format mermaid` 输出空图，说明未启用 NER 或记忆中没有实体关系。需要先使用 `--enable-ner` 写入带实体的记忆。

## 脚本

### `scripts/init_knowledge_base.py`
一键初始化知识库：检查二进制、下载模型、创建数据库、写入示例记忆。

### `scripts/ingest_documents.py`
批量导入文档目录，基于 markitdown 引擎自动识别并转换 20+ 种格式（PDF/Word/Excel/PPT/HTML/MD/TXT/CSV/JSON/XML/EPUB/Outlook邮件/图片/Audio/IPYNB 等），统一提取文本后通过 `--body-stdin` 导入知识库。

> **依赖安装**：首次使用前需安装 markitdown 及可选依赖：`pip install markitdown[docx,pdf,pptx,xlsx]`。DOCX 转换依赖 `mammoth`，PDF 依赖 `pypdf`，PPTX 依赖 `python-pptx`，XLSX 依赖 `openpyxl`。

### `scripts/query_knowledge_base.py`
交互式查询知识库，支持语义检索、混合检索、图谱查询。

### `scripts/export_knowledge_base.py`
导出知识库内容为 JSON/CSV/Markdown 格式。

## 参考资料

### `references/commands.md`
完整命令参考手册，包含所有子命令、参数说明和示例。

### `references/entity_types.md`
实体类型与关系类型说明，含 `--type` 与 `entity_type` 的区别。

### `references/troubleshooting.md`
常见错误排查指南。
