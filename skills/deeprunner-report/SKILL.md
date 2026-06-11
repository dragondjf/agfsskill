---
name: deeprunner-report
description: 从 DeepRunner 6.0 压测结果（stats.json + 测试脚本）自动生成单设备/比对测评报告，支持 HTML 和 Excel 双格式。逐并发报告 + 汇总报告 + 设备信息自动检测。
---

# DeepRunner 6.0 报告生成技能

## 目录结构

```

### 一站式 API（自动检测 + 生成）

```python
from scripts.generate_report import auto_scan_and_generate, discover_and_generate

# 一站式自动检测场景 + 生成报告（自动判断单设备/比对）
result = auto_scan_and_generate(
    base_dir=r'D:\测试报告\公司测试',
    output_dir=r'D:\输出',
    formats=['excel', 'html'],       # 可选：['excel'], ['html']
    per_concurrency=True,             # 可选：生成逐并发报告
    device_name='NVIDIA GB10',      # 可选：覆盖自动检测的设备名
    model_name='Qwen3.6-35B',        # 可选：覆盖自动检测的模型名
)
# result = {'ok': True, 'type': 'single', 'files': [...], 'message': '...'}

# 比对模式（覆盖自动检测的目录）
result = auto_scan_and_generate(
    base_dir=r'D:\测试报告',
    output_dir=r'D:\输出',
    device_a='GB10', device_b='910B4',
    model_a='Qwen3.6', model_b='qwen3.5',
    dir_a=r'D:\测试报告\公司测试\HTML报告',
    dir_b=r'D:\测试报告\远程测试\HTML报告',
)

# 批量发现 + 生成（扫描根目录下所有一级子目录）
result = discover_and_generate(
    root_dir=r'D:\测试报告',
    output_dir=r'D:\输出',
    formats=['excel', 'html'],
)
# result = {'ok': True, 'devices': [...], 'files': [...], 'message': '...'}
```
deeprunner-report/
├── SKILL.md                       ← 本文件
├── scripts/
│   ├── generate_report.py         ← 业务逻辑（2500+行）
│   └── app.py                     ← HTTP 接口层（Flask，委托 generate_report.py）
├── start.bat                      ← Windows 一键启动
├── start.sh                       ← Linux/Mac 一键启动
├── requirements.txt               ← Python 依赖
├── assets/                        ← HTML 静态资源
│   ├── single-report-template.html   单设备 HTML 模板
│   ├── compare-report-template.html  比对 HTML 模板
│   ├── web-ui.html                  Web UI 前端（完整 SPA，支持浅色/深色主题）
│   ├── tailwind.min.js
│   ├── chart.umd.min.js
│   ├── marked.min.js
│   ├── inter-font.css
│   ├── fontawesome.min.css
│   └── webfonts/
└── references/
    ├── data-schema.md
    └── html-style-guide.md
```

---

## 输入数据规范

### 测试报告目录结构（必需）

```
测试报告/
├── device-info-*.md               ← [可选] 设备信息文件（自动检测）
├── 公司测试/                      ← 设备A
│   └── HTML报告/
│       ├── webrunner_xxx_1/       ← 每组并发一个目录
│       │   ├── stats.json         ★ 必需：核心压测数据
│       │   └── test_xxx.py        ★ 必需：测试脚本（含 '用户数': N）
│       ├── webrunner_xxx_2/
│       └── ...
└── 远程测试/                      ← 设备B
    └── HTML报告/
        ├── webrunner_yyy_1/
        └── ...
```

### stats.json 格式

JSON 数组，每个元素是一个命名指标条目：

```json
[
  {
    "name": "Throughput (tokens/s)[吞吐量]",
    "num_requests": 12,
    "num_failures": 0,
    "min_response_time": 7.86,
    "max_response_time": 54.63,
    "total_response_time": 335.9
  },
  {
    "name": "TTFT (s)[Time to First Token]",
    "min_response_time": 0.074,
    "max_response_time": 0.127
  },
  ...
]
```

字段名支持中文/英文双匹配（如 `'平均延迟'` 和 `'Average latency'`）。

### device-*.md 格式（可选，用于自动检测）

```markdown
# 设备信息采集报告
> 主机名: thinkstationpgx-321e

## 一、系统概览
| 项目 | 值 |
| :--- | :--- |
| 厂商/SoC | NVIDIA GB10 |
| 架构 | aarch64 |

## CPU
型号名称： Cortex-X925
CPU 大小核拓扑表...

## NPU / GPU
npu-smi / nvidia-smi 输出...

## 内存
Mem: 119Gi total, 104Gi used...

## 推理服务 — vLLM
Docker 容器 + 启动参数 + /v1/models
```

支持自动提取9个字段：设备名、模型名、加速器、CPU、内存、量化方式、推理框架、API端点、网络模式。

---

## 安装依赖

```bash
pip install openpyxl
```

---

## CLI 用法

### 单设备报告（逐并发 + 汇总）

默认生成 10份逐并发 + 1份汇总：

```bash
# HTML + Excel 一起生成
python generate_report.py --mode single --stats-dir <目录> --output-dir <输出目录>

# 仅 HTML
python generate_report.py --mode single-html --stats-dir <目录> --output-dir <输出目录>
```

设备/模型名自动检测（从 `device-*.md`），也可手动指定：

```bash
python generate_report.py --mode single-html --stats-dir <目录> --output-dir <输出目录>\\
    --device "NVIDIA GB10" --model "Qwen3.6-35B-A3B-FP8"
```

仅汇总报告（关闭逐并发）：

```bash
python generate_report.py --mode single-html --stats-dir <目录> --output-dir <输出目录> --no-per-concurrency
```

### 双设备比对报告

```bash
# HTML + Excel 同时生成
python generate_report.py --mode compare \\
    --stats-dir-a <设备A目录> --stats-dir-b <设备B目录> --output-dir <输出目录>

# 仅 HTML
python generate_report.py --mode compare-html \\
    --stats-dir-a <设备A目录> --stats-dir-b <设备B目录> --output-dir <输出目录>
```

手动指定名称（覆盖自动检测）：

```bash
python generate_report.py --mode compare-html \\
    --stats-dir-a "公司测试/HTML报告" --stats-dir-b "远程测试/HTML报告" \\
    --output-dir "输出目录" \\
    --device-a "NVIDIA_GB10" --device-b "Ascend_910B4" \\
    --name-a "NVIDIA GB10" --name-b "昇腾 910B4" \\
    --model-a "Qwen3.6-35B-A3B-FP8" --model-b "qwen3.5-a3b"
```

### 完整参数列表

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `--mode` | 必选 | — | `single` / `single-html` / `compare` / `compare-html` / `batch` / **`discover`** |
| `--root-dir` | 路径 | — | **discover 模式**：根目录，自动扫描发现所有设备并生成全部报告 |
| `--stats-dir` | 路径 | — | 单设备模式：测试数据目录 |
| `--stats-dir-a` | 路径 | — | 比对模式：设备A目录 |
| `--stats-dir-b` | 路径 | — | 比对模式：设备B目录 |
| `--output-dir` | 路径 | 必选 | 输出目录 |
| `--device` | 字符串 | 自动检测 | 单设备：设备名 |
| `--device-a` | 字符串 | 自动检测 | 比对：设备A名（用于文件名） |
| `--device-b` | 字符串 | 自动检测 | 比对：设备B名（用于文件名） |
| `--name-a` | 字符串 | 自动检测 | 比对：设备A显示名 |
| `--name-b` | 字符串 | 自动检测 | 比对：设备B显示名 |
| `--model` | 字符串 | 自动检测 | 单设备：模型名 |
| `--model-a` | 字符串 | 自动检测 | 比对：模型A名 |
| `--model-b` | 字符串 | 自动检测 | 比对：模型B名 |
| `--per-concurrency` | 开关 | True | 开启逐并发生成 |
| `--no-per-concurrency` | 开关 | False | 关闭逐并发生成，仅汇总 |

---

## 输出文件结构

以 `--output-dir ./output/` 为例：

```
output/
├── assets/                       ← HTML 静态资源（自动复制）
│
├── deeprunner_NVIDIA_GB10_并发1.html   ← 逐并发单设备HTML
├── deeprunner_NVIDIA_GB10_并发2.html
├── ...
├── deeprunner_NVIDIA_GB10_并发10.html
├── DeepRunner_NVIDIA_GB10_并发1.xlsx   ← 逐并发单设备Excel
├── ...
├── DeepRunner_NVIDIA_GB10_并发10.xlsx
├── deeprunner_NVIDIA_GB10测评报告.html  ← 汇总HTML（折线图）
├── DeepRunner_推理性能测试报告_NVIDIA_GB10.xlsx  ← 汇总Excel（7 Sheets）
│
├── deeprunner_Ascend_910B4_并发1.html
├── ...
├── deeprunner_Ascend_910B4测评报告.html
├── DeepRunner_推理性能测试报告_Ascend_910B4.xlsx
│
├── deeprunner_比对_NVIDIA_GB10_vs_Ascend_910B4_并发1.html  ← 逐并发比对HTML
├── ...
├── deeprunner_比对_NVIDIA_GB10_vs_Ascend_910B4_并发10.html
├── DeepRunner_比对_NVIDIA_GB10_vs_Ascend_910B4_并发1.xlsx
├── ...
├── DeepRunner_比对_NVIDIA_GB10_vs_Ascend_910B4_并发10.xlsx
├── deeprunner_推理性能比对报告_NVIDIA_GB10_vs_Ascend_910B4.html  ← 汇总比对HTML
└── DeepRunner_推理性能比对报告_NVIDIA_GB10_vs_Ascend_910B4.xlsx  ← 汇总比对Excel
```

---

## 报告内容

### 单设备 Excel（7 Sheets）

| Sheet | 内容 |
|---|---|
| 测试概览 | 设备信息 + 并发/请求/失败统计 |
| 逐组测试明细 | 16列性能指标（延迟/吞吐/QPS/TTFT/TPOT/Token） |
| 汇总统计 | 10行核心指标聚合 |
| 自定义指标明细 | stats.json 所有原始指标 |
| 测试环境配置 | API端点/模型/并发/负载机IP/数据源 |
| 性能分析结论 | 7条自动生成结论（基于实际数据） |
| 图表分析 | 图表源数据 |

### 单设备 HTML（7区块）

1. **报告元信息** — 设备名、模型、日期、组数、稳态时长
2. **设备档案** — 加速器/CPU/内存/框架/API/网络模式（从 device-*.md 自动检测）
3. **被测模型** — 模型名/量化方式/框架/部署方式
4. **核心性能指标** — TTFT/TPOT/吞吐/E2E 卡片（渐变字体）
5. **稳定性 & SLA** — 成功率/失败数/SLA通过状态
6. **可视化曲线** — 2张 Chart.js 图表（单点=柱状图，多点=折线图）
7. **逐组明细表 + 性能分析结论**

### 比对 Excel（7 Sheets + 6 Charts）

| Sheet | 内容 |
|---|---|
| 测试概览 | A/B 设备 + 模型并列对比 |
| 逐组对比明细 | A(10行)+B(10行) 各16列，合并+分Tab |
| 汇总统计 | 10行对比指标 + 倍数结论 |
| 自定义指标明细 | A/B 各自所有指标 |
| 测试环境配置 | A/B 配置双列对比 |
| 性能分析结论 | 9条对比结论（基于数据差异） |
| 图表分析 | 图表源数据 |

### 比对 HTML（6张图表 + Tab表 + 结论）

- 6 张 Chart.js 图表：延迟/吞吐/TTFT/QPS/输出Tok/请求数
- Tab切换：合并对比 / 设备A / 设备B
- 8 条对比结论卡片（数据驱动）
- 核心指标 4 卡片（含比值结论）

### 图表规则

| 场景 | 图表类型 |
|---|---|
| 逐并发报告（1个数据点） | **柱状图** `type: 'bar'` |
| 汇总报告（≥2个数据点） | **折线图** `type: 'line'` |
| 比对报告 bar 类（输出Tok/请求数） | 始终柱状图 |

---

## 设备信息自动检测

从 `device-*.md` 文件自动提取9个字段，支持多级目录搜索（从 stats_dir 向上查找父目录）：

| 字段 | 提取来源 |
|---|---|
| `device` | 厂商/SoC → NPU型号 → GPU Product Name → 主机名+架构 |
| `model` | vLLM `/v1/models` id → Docker 启动参数 → root 路径 → 容器名 |
| `accelerator` | NPU统计（910B4×4卡）/ GPU（GB10 Blackwell 1卡） |
| `cpu_info` | 大小核拓扑解析（X925@3.9G + A725@2.8G / 鲲鹏920:64核） |
| `memory` | `free -h` / `free -k` 格式 |
| `quantization` | 模型名后缀（FP8/BF16/INT4）→ 环境推断 |
| `framework` | vLLM 版本号 |
| `api_endpoint` | Docker 端口映射 → `--port` 启动参数 → 监听端口 |
| `network_mode` | 容器 port mapping → host 网络 |

当 CLi 未传 `--device`/`--model`/`--name-a`/`--name-b` 时，自动调用 `detect_device_info()` 检测，日志输出 `[检测] 设备: ... | 模型: ...`。

---

## Python API

### 核心 API

```python
from scripts.generate_report import (
    scan_test_groups,
    detect_device_info,
    generate_single_excel,
    generate_single_html,
    generate_compare_excel,
    generate_compare_html,
)

# 扫描测试数据
groups = scan_test_groups(r'path/to/HTML报告')

# 检测设备信息
info = detect_device_info(r'path/to/测试报告')
# info[0] = {'device': 'NVIDIA GB10', 'accelerator': '...', 'cpu_info': '...', ...}

# 生成单设备报告
generate_single_excel(groups, 'NVIDIA GB10', 'Qwen3.6-35B', 'output.xlsx', device_info=info[0])
generate_single_html(groups, 'NVIDIA GB10', 'Qwen3.6-35B', 'output.html', device_info=info[0])

# 生成比对报告
generate_compare_excel(groups_a, groups_b, 'GB10', '910B4', 'Qwen', 'qwen3.5', 'output.xlsx')
generate_compare_html(groups_a, groups_b, 'GB10', '910B4', 'Qwen', 'qwen3.5', 'output.html',
                       device_info_a=info_a[0], device_info_b=info_b[0])
```

---

## Web UI 模式

启动 Web UI（需安装 Flask），提供完整的可视化操作界面：

```bash
# Windows
start.bat

# Linux/Mac
bash start.sh

# 或手动安装依赖后启动
pip install -r requirements.txt -q
python scripts/app.py
# 浏览器访问 http://127.0.0.1:8866
```

Web UI 功能：
- **单设备/比对模式**：输入测试数据目录 → 自动扫描 → 自动识别场景 → 一键生成
- **批量发现模式**：输入根目录 → 自动发现所有设备 → 批量生成
- **实时进度**：异步任务 + 轮询进度条
- **报告下载/预览**：Excel 下载 + HTML 在线预览
- **浅色/深色主题**切换
- **设备档案自动展示**（从 device-*.md 检测）

RESTful API 端点：

| 端点 | 方法 | 说明 |
|---|---|---|
| `/` | GET | Web UI SPA 页面 |
| `/api/auto-scan` | POST | 自动扫描目录，识别单设备/比对场景 |
| `/api/discover` | POST | 批量发现设备（扫描一级子目录） |
| `/api/auto-generate` | POST | 自动生成报告（异步，返回 task_id） |
| `/api/discover-generate` | POST | 批量发现并生成（异步，返回 task_id） |
| `/api/task/<id>` | GET | 查询异步任务状态/进度 |
| `/api/download/<file>` | GET | 下载生成的报告文件 |
| `/api/preview/<file>` | GET | 预览 HTML 报告 |

### 自动检测逻辑（_auto_detect）

`auto_scan_and_generate` 和 `/api/auto-scan` 内部调用 `_auto_detect(base_dir)` 进行三级自动检测：

1. **直接扫描**：`base_dir` 下直接包含 webrunner_* 子目录（含 stats.json + test*.py）→ 单设备场景
2. **递归查找**：`base_dir` 下仅一个一级子目录包含 stats.json → 递归向上查找扫描入口 → 单设备场景
3. **多目录分组**：`base_dir` 下多个一级子目录各含 stats.json → 取前两个作为设备A/B → 比对场景

当自动检测不满足需求时，可通过 `dir_a`/`dir_b`/`device_a`/`device_b` 参数手动覆盖。

---

## 自定义模板

模板文件位于 `assets/` 目录：

- `single-report-template.html` — 单设备 HTML 模板
- `compare-report-template.html` — 比对 HTML 模板

模板使用 `{{PLACEHOLDER}}` 占位符 + `{{REPORT_DATA_JSON}}` 数据注入。所有 CSS/JS 资源在生成时自动复制到输出目录。

图片和字体资源：FontAwesome 图标使用 `<i class="fas fa-..."></i>`，Inter 字体通过 base64 内联。
