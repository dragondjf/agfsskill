# 实体类型与关系类型参考

## 重要：`--type` 与 `entity_type` 的区别

sqlite-graphrag 中有两套完全不同的类型系统，容易混淆：

### 1. 记忆类型 (`--type`)

用于 `remember` / `ingest` 命令的 `--type` 参数，表示**记忆的分类**。

**仅 9 种有效值：**
`user`, `feedback`, `project`, `reference`, `decision`, `incident`, `skill`, `document`, `note`

> 传入其他值（如 `tool`, `concept`, `person`）会报错退出。

### 2. 图谱实体类型 (`entity_type`)

用于 `--entities-file` 或 NER 提取的实体分类，表示**知识图谱中节点的类型**。

**13 种有效值：**
`project`, `tool`, `person`, `file`, `concept`, `incident`, `decision`, `memory`, `dashboard`, `issue_tracker`, `organization`, `location`, `date`

> 注意：`--type` 的 `user` 不在 entity_type 中；`entity_type` 的 `tool`, `concept`, `person` 等也不在 `--type` 中。

## 关系类型 (`relation`)

用于 `link` 命令或 `--relationships-file`。

### 12 种标准值：
`applies-to`, `uses`, `depends-on`, `causes`, `fixes`, `contradicts`, `supports`, `follows`, `related`, `mentions`, `replaces`, `tracked-in`

### 自定义值
其他 kebab-case 或 snake_case 字符串也被接受（会输出 `tracing::warn!` 警告），例如：
`implements`, `tested-by`, `blocks`, `developed-by`, `written-in`, `hosted-on`

### 强度 (`strength`)
浮点数 `[0.0, 1.0]`，表示边的权重。输出时映射为 `weight` 字段。

## 快速对照表

| 场景 | 参数名 | 有效值 |
|---|---|---|
| `remember --type` | 记忆类型 | `user`, `feedback`, `project`, `reference`, `decision`, `incident`, `skill`, `document`, `note` |
| `--entities-file` 中的 `entity_type` | 实体类型 | `project`, `tool`, `person`, `file`, `concept`, `incident`, `decision`, `memory`, `dashboard`, `issue_tracker`, `organization`, `location`, `date` |
| `link --relation` | 关系类型 | 12 标准值 + 自定义 kebab-case |
