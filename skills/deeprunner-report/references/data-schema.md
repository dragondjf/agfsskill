# DeepRunner 6.0 报告数据来源说明

## 1. stats.json 结构

每个测试组目录下自动生成，是报告数据的**核心来源**。

### 顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `meta` | object | 元数据（总请求数、失败数、成功率） |
| `stats_requests` | array | 按指标分类的性能数据行 |

### stats_requests[] 单行结构

| 字段 | 含义 | 单位 |
|------|------|------|
| `avg_latency` | 平均延迟 | 秒 |
| `min_latency` | 最小延迟 | 秒 |
| `max_latency` | 最大延迟 | 秒 |
| `throughput_avg` | 平均吞吐 | tok/s |
| `throughput_min` | 最小吞吐 | tok/s |
| `throughput_max` | 最大吞吐 | tok/s |
| `avg_qps` | 平均QPS | req/s |
| `min_qps` | 最小QPS | req/s |
| `max_qps` | 最大QPS | req/s |
| `avg_ttft` | 平均首Token时间 | 秒 |
| `avg_tpot` | 平均每输出Token时间 | 秒 |
| `avg_input_tokens` | 平均输入token数 | 个 |
| `min_output_tokens` | 最小输出token数 | 个 |
| `max_output_tokens` | 最大输出token数 | 个 |

> **注意**: stats.json 中的字段名可能是中文（如"平均延迟"），也可能是英文（如 `avg_latency`），取决于 DeepRunner 版本。提取时应同时兼容两种命名。

## 2. 测试脚本（test*.py）

每个测试组目录下有一个 Python 测试脚本，包含并发数配置。

### 并发数提取（正则模式）

```python
patterns = [
    r"'用户数'\s*:\s*(\d+)",    # GUIRunner 配置格式
    r'"用户数"\s*:\s*(\d+)",
    r'users\s*=\s*(\d+)',
    r'concurrency\s*=\s*(\d+)',
    r"'并发数'\s*:\s*(\d+)",
]
```

## 3. apirunner.json

测试运行配置文件，包含 API 端点、模型名称、运行时长等。

## 4. export_report_meta.json

DeepRunner 自动生成的报告元数据，包含设备信息、模型信息、测试参数等。

## 5. webrunner_stats.csv

CSV 格式的统计数据，可用 pandas 读取做高级分析。

## 6. 硬件/模型信息来源

| 信息 | 来源 | 获取方式 |
|------|------|---------|
| 设备硬件信息 | `collect-device-info.sh` 输出的 `.md` 文件 | 脚本自动采集 |
| 模型信息 | `collect-model-info.sh` 输出的 `.md` 文件 | 脚本自动采集 |
| NPU/GPU 利用率 | `npu-smi info` / `nvidia-smi` 输出 | 脚本自动采集 |

## 7. 测试数据文件

| 文件 | 说明 |
|------|------|
| `test.xlsx` | 测试用例数据集（含 Index、Question 等） |
| 同一份 test.xlsx | 两组对比测试应使用相同数据源 |

## 8. 完整报告所需最小输入集

生成一份完整报告需要以下文件：

**必需**:
1. `stats.json` -- 每组测试一个（性能数据）
2. `test*.py` -- 每组测试一个（提取并发数）

**可选**:
3. `apirunner.json` -- 测试配置详情
4. 硬件信息 `.md` 文件
5. 模型信息 `.md` 文件
6. `test.xlsx` -- 测试数据源

## 9. 目录结构示例

```
测试报告/
├── 公司测试/
│   └── HTML报告/
│       ├── webrunner_qianwen_1_20260607160636/
│       │   ├── stats.json          ← 核心数据
│       │   ├── testGB10.py         ← 并发数
│       │   ├── apirunner.json      ← 配置
│       │   ├── export_report_meta.json
│       │   └── ...
│       ├── webrunner_qianwen_2_...
│       └── ...
├── 远程测试/
│   └── HTML报告/
│       ├── webrunner_test_1_...
│       └── ...
└── test.xlsx                       ← 共用数据源
```
