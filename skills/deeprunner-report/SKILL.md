---
name: deeprunner-report
description: 从 DeepRunner 6.0 压测工具的原始输出数据（stats.json + 测试脚本）自动生成可视化测评报告和比对报告。支持 Excel（openpyxl）和 HTML（glass-card 深色/浅色双主题 + Chart.js 图表）两种输出格式。当用户要求"生成测评报告""生成比对报告""测试报告转HTML""stats.json生成报告""压测数据可视化""推理性能报告""生成Excel报告"等涉及 DeepRunner / GUIRunner 压测结果报告生成时触发。
---

# DeepRunner 6.0 报告生成技能

## 工作流总览

```
输入数据 → 数据提取 → 分析计算 → 报告生成（Excel / HTML）
```

## 输入数据

必需文件（每个测试组目录）：
- `stats.json` — 核心性能数据（延迟/吞吐/QPS/TTFT/TPOT/Token数）
- `test*.py` — 测试脚本（正则提取并发数）

可选文件：
- `apirunner.json` — 测试配置（API端点、模型名、运行时长）
- 硬件信息 `.md` — 设备详情
- 模型信息 `.md` — 模型参数

数据 schema 详见 [references/data-schema.md](references/data-schema.md)。

## 两种报告模式

### 模式一：单设备测评报告

从一组测试（1~N组）生成单个设备的完整测评报告。

**数据扫描**：扫描包含 `stats.json` 的子目录，按并发数排序。

```python
from scripts.generate_report import scan_test_groups, generate_single_excel
groups = scan_test_groups(r'path/to/HTML报告')
generate_single_excel(groups, device_name='GB10', model_name='Qwen3.6-35B', output_path='output.xlsx')
```

**HTML 报告生成**：

1. 读取模板 `assets/single-report-template.html`
2. 用 `REPORT_DATA_JSON` 变量注入数据（json.dumps）
3. 替换 `{{PLACEHOLDER}}` 占位符
4. 图表使用 Chart.js 初始化（并发-吞吐曲线、延迟曲线）

### 模式二：双设备比对报告

从两组测试（各1~N组）生成对比分析报告。

```python
from scripts.generate_report import scan_test_groups, generate_compare_excel
groups_a = scan_test_groups(r'path/to/公司测试/HTML报告')
groups_b = scan_test_groups(r'path/to/远程测试/HTML报告')
generate_compare_excel(groups_a, groups_b, 'NVIDIA GB10', '昇腾 910B4',
                        model_a='Qwen3.6-35B-A3B-FP8', model_b='qwen3.5-a3b',
                        output_path='output.xlsx')
```

**HTML 比对报告生成**：

1. 读取模板 `assets/compare-report-template.html`
2. 数据通过 `REPORT_DATA_JSON` 注入
3. 包含 6 张 Chart.js 对比图表 + Tab 切换明细表 + 结论卡片

## 报告内容结构

### Excel 报告（7 个 Sheet）

| Sheet | 内容 |
|-------|------|
| 测试概览 | 设备/模型/配置基本信息 |
| 逐组对比明细 | 20行（A10+B10），16列性能指标 |
| 汇总统计 | 核心指标汇总 + 对比结论 |
| 自定义指标明细 | 从 stats.json 提取的所有自定义指标 |
| 测试环境配置 | API端点/模型/并发/数据源 |
| 性能分析结论 | 9条分析结论 |
| 图表分析 | 图表源数据（10行×12列） |

### HTML 报告板块

- 报告元信息 + 设备/模型卡片 + 核心指标卡片 + Chart.js 图表 + 明细表 + 结论 + 签署

## HTML 风格规范

glass-card / glass-panel 深色玻璃态设计，Tailwind CSS + Chart.js，深色/浅色主题切换。

完整风格指南见 [references/html-style-guide.md](references/html-style-guide.md)。

## 关键实现要点

### 并发数提取

从测试脚本正则匹配 `'用户数': N`，不要假设并发数 = 序号：

```python
import re
concurrency = int(re.search(r"'用户数'\s*:\s*(\d+)", script_content).group(1))
```

### stats.json 字段兼容

字段名可能是中文或英文，需同时处理：

```python
avg_latency = row.get('avg_latency') or row.get('平均延迟', 0)
```

### 离线 HTML

所有 CSS/JS 资源放 `assets/` 目录：
- `inter-font.css`（base64 字体）
- `tailwind.min.js`、`chart.umd.min.js`、`marked.min.js`
- `fontawesome.min.css`（base64 图标）

### 图表主题同步

切换主题时必须销毁并重建 Chart.js 实例（颜色更新）：

```javascript
Object.values(charts).forEach(ch => ch.destroy());
charts = {};
// 重新创建...
```

### json.dumps 安全注入

JS 中数据注入使用 `json.dumps(data, ensure_ascii=True)` 避免特殊字符问题。

## 文件命名

- HTML: `deeprunner_<设备名>测评报告.html`
- 比对 HTML: `deeprunner_推理性能比对报告_<A>_vs_<B>.html`
- Excel: `DeepRunner_推理性能比对报告_<A>_vs_<B>.xlsx`
