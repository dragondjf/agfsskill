# sqlite-graphrag 命令参考手册

## 数据库生命周期

| 命令 | 用途 | 关键参数 |
|---|---|---|
| `init` | 初始化数据库 + 下载嵌入模型 | `--namespace <ns>` |
| `daemon` | 管理嵌入守护进程 | `--ping`, `--stop`, `--idle-shutdown-secs` |
| `health --json` | 检查数据库完整性、FTS5、向量索引 | - |
| `stats --json` | 统计记忆/实体/关系数量 | - |
| `migrate` | 应用待处理的 schema 迁移 | - |
| `vacuum` | 回收磁盘空间 | - |
| `optimize` | PRAGMA optimize + 重建 FTS5 索引 | `--skip-fts` |
| `backup --output <path>` | SQLite Online Backup API 备份 | - |
| `sync-safe-copy --dest <path>` | 生成同步安全的快照副本 | - |

## 记忆写入

| 命令 | 用途 | 关键参数 |
|---|---|---|
| `remember` | 写入单条记忆 | `--name`, `--type`, `--description`, `--body`/`--body-file`/`--body-stdin`, `--enable-ner`, `--force-merge`, `--dry-run` |
| `remember-batch` | 从 NDJSON stdin 批量创建 | `--transaction`, `--force-merge`, `--fail-fast` |
| `ingest <DIR>` | 批量导入目录下文件 | `--pattern` (默认 `*.md`), `--recursive`, `--type` (默认 `document`), `--enable-ner`, `--dry-run`, `--max-files` |

## 记忆读取与检索

| 命令 | 用途 | 关键参数 |
|---|---|---|
| `recall <query>` | 语义检索（向量 KNN + 图谱多跳） | `--k`, `--type`, `--max-hops`, `--max-distance`, `--no-graph` |
| `hybrid-search <query>` | 混合检索（向量 + FTS5 全文，RRF 融合） | `--k` |
| `read` | 精确读取 | `--name <name>` 或 `--id <N>`, `--with-graph` |
| `list` | 列出记忆 | `--type`, `--limit`, `--offset`, `--namespace` |
| `related` | 查询关联记忆 | `--name`, `--max-hops` |
| `deep-research <query>` | 深度多跳研究 | `--k` |

## 记忆维护

| 命令 | 用途 | 关键参数 |
|---|---|---|
| `edit` | 编辑记忆 | `--name`, `--body`, `--description` |
| `rename` | 重命名 | `--name <old>`, `--new-name <new>` |
| `forget` | 软删除 | `--name` |
| `purge` | 永久删除（不可恢复） | - |
| `history` | 查看版本历史 | `--name` |
| `restore` | 恢复到历史版本 | `--name`, `--version` |

## 图谱操作

| 命令 | 用途 | 关键参数 |
|---|---|---|
| `graph` | 导出图谱快照 | `--format json/dot/mermaid/ndjson`, `--output` |
| `graph traverse` | BFS 遍历关系 | `--from <entity>`, `--depth` |
| `graph stats` | 图谱统计 | `--format json` |
| `graph entities` | 列出实体 | `--entity-type` |
| `link` | 手动建立关系 | `--from`, `--to`, `--relation`, `--strength` |
| `unlink` | 删除关系 | `--from`, `--to`, `--relation` |
| `merge-entities` | 合并实体 | `--sources`, `--target` |
| `rename-entity` | 重命名实体 | `--name`, `--new-name` |
| `reclassify` | 重新分类实体 | `--name`, `--new-type` |
| `delete-entity` | 删除实体及所有关系 | `--name` |
| `prune-relations` | 批量删除指定类型的关系 | `--relation-type` |
| `prune-ner` | 删除 NER 绑定 | `--entity-name` |
| `cleanup-orphans` | 清理孤立实体 | - |

## 其他

| 命令 | 用途 | 关键参数 |
|---|---|---|
| `export` | 导出为 NDJSON | - |
| `fts` | FTS5 索引管理 | `rebuild`, `check` |
| `cache` | 缓存管理 | `list`, `clear-models --yes` |
| `namespace-detect` | 检测命名空间 | - |
| `enrich` | LLM 增强 | `--mode claude-code/codex` |
| `reclassify-relation` | 批量重分类关系 | - |
