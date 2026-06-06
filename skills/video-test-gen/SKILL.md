---
name: video-test-gen
description: >-
  从操作视频中自动提取关键帧，利用多模态 AI 为每个界面场景生成结构化测试用例，
  并输出标准化 Excel、图文 Word 报告和模板格式的测试记录文档。
  适用于用户提供操作录屏/演示视频并要求生成测试用例、对视频中的 UI 界面进行自动化测试分析。
  触发关键词：视频生成测试用例、操作视频分析、录制视频生成用例、video test case、从视频中提取测试场景。
---

# Video Test Gen

将操作录屏视频自动转化为结构化测试用例，输出格式化 Excel、图文 Word 和模板格式测试记录。

## 流程概览

```
视频 → 关键帧提取 → [二次筛选] → AI分析 → 用例合并 → 步骤补全 → Excel + Word + 测试记录
 步骤1    步骤1.5(可选)  步骤2    步骤2.5   步骤2.6     步骤3 + 步骤4 + 步骤5
```

各步骤独立可运行，pipeline 支持断点续跑和文件占用容错。

## 快速开始

```bash
pip install opencv-python scikit-image pandas xlsxwriter python-docx openai

# 全自动（需要 API Key）
python scripts/pipeline.py <video_path> <output_dir> --api-key sk-xxx \
  --context "后台管理系统" --requirements "覆盖登录和数据查询功能"
```

## 数据结构

AI 返回 Markdown → `parse_markdown_test_cases()` 解析 → 合并 → 步骤补全 → 标准结构：

```json
{
  "id": "TC-001",
  "title": "正向登录测试",
  "description": "验证正确邮箱密码登录",
  "preconditions": "已注册管理员账号",
  "priority": "高",
  "test_type": "功能测试",
  "steps": [
    {"step_number": 1, "description": "输入正确邮箱", "expected_result": "邮箱字段显示输入内容"},
    {"step_number": 2, "description": "输入正确密码", "expected_result": "密码字段显示掩码"},
    {"step_number": 3, "description": "点击登录", "expected_result": "成功跳转到管理后台"}
  ]
}
```

Excel 导出（多步骤合并行组，公共字段仅首行显示）：

| ID | Title | Description | Preconditions | Priority | Step Number | Step Description | Expected Result |
|----|-------|-------------|---------------|----------|-------------|-----------------|----------------|

## 详细步骤

### 步骤 1：关键帧提取

**高效模式（推荐，默认参数）：**

```bash
python scripts/extract_keyframes.py <video_path> <output_dir> --filter-interval 5
```

> 脚本默认参数已优化为高效模式：`threshold=0.90, sample_every=5, resize=320`。
> 4 分钟视频(1912x1076)实测约 1-2 分钟完成，产出约 150 帧，二次筛选后 30-40 帧。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--threshold` | 0.90 | SSIM 阈值，越大越严格（0.98 仅剧烈变化，0.85 保留较多变化） |
| `--sample-every` | 5 | 每隔 N 帧采样比较，仅比较 1/5 的帧，大幅加速 |
| `--resize` | 320 | 计算 SSIM 时缩放宽度（不影响输出分辨率），值越小越快 |
| `--filter-interval` | 0 | 二次筛选间隔（秒），帧过多时按间隔取代表帧 |

**精细模式（需要更多帧时）：**

```bash
python scripts/extract_keyframes.py <video_path> <output_dir> \
  --threshold 0.95 --sample-every 3 --resize 480 --filter-interval 5
```

**两种模式对比：**

| 对比项 | 高效模式（默认） | 精细模式 |
|--------|-----------------|----------|
| `threshold` | 0.90 | 0.95 |
| `sample_every` | 5 | 3 |
| `resize` | 320 | 480 |
| 4min视频耗时 | ~1-2 分钟 | ~2-3 分钟 |
| 产出帧数 | ~150（筛选后 30-40） | ~250（筛选后 35-50） |
| 适用场景 | 一般录制视频 | 界面变化细腻的视频 |

**关键性能参数说明：**

- `sample_every=5`：每 5 帧只取 1 帧比较，计算量降为 1/5。对 30fps 视频相当于 6fps 采样，足以捕获界面级变化
- `resize=320`：SSIM 比较在 320px 宽的小图上进行（vs 原始 1920px），像素数减少约 36 倍。输出的关键帧仍是原始分辨率
- `threshold=0.90`：稍宽松的阈值避免遗漏场景变化，产出帧稍多但通过 `--filter-interval` 控制

**筛选策略建议：**

| 视频时长 | 建议间隔 | 预期帧数 |
|----------|----------|----------|
| < 1 分钟 | 不筛选 (0) | 10-30 |
| 1-5 分钟 | 3-5 秒 | 20-60 |
| 5-15 分钟 | 5-8 秒 | 30-100 |
| > 15 分钟 | 8-10 秒 | 50-150 |

**Agent 内联执行示例：**

```python
import sys
sys.path.insert(0, r"<skill_dir>/scripts")
from extract_keyframes import extract_keyframes, filter_frames_by_interval

frame_info = extract_keyframes(video_path, keyframes_dir)
# threshold=0.90, sample_every=5, resize=320 均为默认值，无需传参

if len(frame_info) > 50:
    frame_info = filter_frames_by_interval(frame_info, interval_seconds=5.0)
```

**输出：** `keyframes/` + `frame_info.json`

### 步骤 2：AI 批量分析

#### 方式 A：外部 API

```bash
python scripts/analyze_frames.py <frame_info.json> <output.json> \
  --model gpt-4o --api-key sk-xxx --base-url https://api.openai.com/v1 \
  --context "管理员后台" --requirements "覆盖登录功能"
```

支持 OpenAI / 阿里云 qwen-vl-max / 其他 OpenAI 兼容 API。

#### 方式 B：内置 view_image 工具（无需 API Key）

1. 从 `frame_info.json` 获取帧列表
2. 对每张图片调用 `view_image`，prompt：

```
你是一个专业的测试用例生成器。请基于这张界面截图生成全面的测试用例。
上下文: <用户信息>
测试需求: <用户需求>

格式要求:
1. 每个测试用例以 ## TC-XXX: 标题 开始
2. 包含字段: **优先级:**, **描述:** , **前置条件:**
3. 测试步骤使用 Markdown 表格: | # | 步骤描述 | 预期结果 |
4. 覆盖正向和负向测试场景
```

3. 收集 Markdown 后调用 `parse_markdown_test_cases()` 解析：

```python
from analyze_frames import parse_markdown_test_cases, merge_test_case_lists, build_analysis_output, save_analysis
all_cases = merge_test_case_lists(list1, list2, ...)
output = build_analysis_output(all_cases, frame_count=len(frame_info))
save_analysis(output, "output/analysis.json")
```

**建议：** 每批 3 帧，批次间保留间隔，实时反馈进度。若图片分辨率过大（>1500px）导致 `view_image` token 超限，先用 PIL 缩小到 1280 宽度再分析。

**图片预处理：** ffmpeg 提取的关键帧可能使用非标准 JPEG 编码，python-docx 的 `add_picture()` 会抛出 `UnrecognizedImageError`。必须在嵌入 Word 前用 PIL 转换为标准 JPEG：

```python
from PIL import Image
img = Image.open(src_path)
if img.mode != 'RGB':
    img = img.convert('RGB')
img.save(std_path, 'JPEG', quality=90)
```

**优先级修复：** `parse_markdown_test_cases()` 使用正则 `\*\*优先级\*\*\s*[:：]?\s*(高|中|低)` 提取优先级。若 Markdown 中优先级格式不匹配（如无星号包裹），解析结果默认为"中"。此时需手动修正：

```python
priority_map = {"TC-001": "高", "TC-002": "中", ...}  # 按AI实际输出修正
for tc in test_cases:
    if tc["id"] in priority_map:
        tc["priority"] = priority_map[tc["id"]]
```

**解析容错：** 中文/英文冒号混用、表格分隔行差异、缺少可选字段、无步骤时自动生成默认步骤。

### 步骤 2.5：用例合并与步骤补全

AI 分析产生的用例通常是单步骤的，此步骤合并为多步骤用例并推断预期结果。

```python
from merge_test_cases import merge_test_cases
merged = merge_test_cases(test_cases, min_group_size=2, max_group_size=8)
```

**合并策略：**
1. 按 `_source_image`（同一帧）分组
2. 组内按测试类型（正向/异常/边界/安全/性能）分类
3. 同类型 >= 2 个用例合并为一个多步骤用例
4. 自动推断预期结果（正向=结果正确，异常=错误提示不崩溃，边界=正确处理边界值）
5. 重新编号，添加 `test_type` 字段

**实测效果：** 260 单步 → 101 多步（平均 2.6 步），分布：2步x50、3步x43、4步x6

```bash
python scripts/merge_test_cases.py <analysis.json> <output.json> --min-group 2 --max-steps 8
```

> **⚠️ 已知问题：合并后步骤描述可能为空。** `merge_test_cases()` 合并时只推断预期结果（正向/异常/边界），不会补全步骤描述。当 `_source_image` 为空或同帧用例不足 `min_group_size` 时，大量用例保持单步默认空描述（`description=''`）。
>
> **实测案例：** 72 个原始用例合并后 57 个，其中 54 个（94.7%）步骤描述为空，仅 3 个有完整步骤。
>
> **必须在步骤 2.5 之后、步骤 3 之前执行步骤 2.6 步骤补全。**

### 步骤 2.6：空步骤用例补全（必执行）

当 `analysis_merged.json` 中存在步骤描述为空的用例时，通过 `view_image` 基于截图和用例标题重新生成明确步骤。

**触发条件：** 合并后检测空步骤用例比例，超过 10% 则需执行此步骤。

```python
# 检测空步骤用例
empty_cases = [
    tc for tc in merged_data["test_cases"]
    if not any(s.get("description", "").strip() for s in tc.get("steps", []))
]
empty_ratio = len(empty_cases) / len(merged_data["test_cases"])
print(f"空步骤用例: {len(empty_cases)}/{len(merged_data['test_cases'])} ({empty_ratio:.1%})")
# 若 > 10%，需执行步骤 2.6
```

**补全流程：**

1. **按帧分组：** 每个用例按 `tc_index % num_frames` 分配关键帧截图
2. **批量分析：** 每批 2 帧（含 2~4 个用例），调用 `view_image` 生成步骤
3. **Prompt 要求严格 JSON 输出：**

```
这是软件界面的截图。请根据界面内容，为以下测试用例补充明确的操作步骤和预期结果。
每个用例需要2-4个具体步骤，必须严格使用以下JSON格式：

[
  {"id": "TC-XXX", "steps": [{"step_number": 1, "description": "具体操作", "expected_result": "具体预期"}]},
  ...
]

用例说明：
- TC-XXX: <测试类型> - <用例标题>
```

4. **解析回写：** 将 AI 返回的 steps 直接替换空步骤用例的 `steps` 字段，重新编号

**批量处理规模参考：**

| 空步骤用例数 | 关键帧数 | 批次数 | 预计耗时 |
|-------------|---------|--------|---------|
| ~50 | 32 | ~16 批 | 10-15 分钟 |
| ~100 | 50 | ~25 批 | 15-25 分钟 |

**回写代码：**

```python
steps_map = {}  # 从 AI 返回结果收集 {"TC-XXX": [steps...]}
for tc in merged_data["test_cases"]:
    tc_id = tc["id"]
    if tc_id in steps_map:
        tc["steps"] = [
            {"step_number": i + 1, "description": s["description"], "expected_result": s["expected_result"]}
            for i, s in enumerate(steps_map[tc_id])
        ]
```

**注意事项：**
- AI 返回的 JSON 格式可能不一致（缺少 `description` 键、`step_number` 为字符串等），需在回写时规范化
- 同一帧可能对应多个用例（正向+异常），AI 分析时应同时传入以提高关联性
- 补全后应验证所有用例步骤非空再进入步骤 3

### 步骤 3 & 4：生成 Excel + Word

```bash
python scripts/generate_reports.py <analysis.json> \
  --excel output/test_cases.xlsx --word output/test_report.docx
```

**Excel：** 绿色背景加粗表头 / 优先级着色（高=红，中=黄，低=绿） / 自动换行+冻结首行 / 多步合并行组

**Word：** 封面+统计 / 每用例独立章节含元信息表格 / 自动嵌入截图 / 步骤表格

### 步骤 5：生成测试记录（YFJZ-R805-05 模板格式）

**参考模板文件：** `references/test_records_template.docx`

> 基于 `references/test_records_template.docx` 的完整 XML 逆向分析，以下所有数值均为精确测量值。
> Agent 执行步骤 5 时，**必须以该模板文件为基础**，保留封面表和修改记录表，仅替换附录3内容。

#### 5.1 文档整体结构

**模板文件：** `references/test_records_template.docx`（7.1 MB，含 100+ 个示例 TC 表格）

**Body 元素序列（从上到下，基于模板实际 XML）：**

```
[0]  封面表（7行 x 2列，无边框）
[1]  空段落（无样式，无间距设置）
[2]  Heading1: "文档修改记录"
[3]  修改记录表（5行 x 5列）
[4]  Heading1: "附录3 测试记录"
[5]  Heading1: "功能测试"              ← 按 test_type 分组
[6]    Heading2: "TC-001"
[7]    16x8 TC 表格
[8]    居中图片段落（宽 5.51 英寸）
[9]    空段落
[10]   空段落
[11]   Heading2: "TC-002"
[12]   16x8 TC 表格
[13]   居中图片段落
[14]   空段落
[15]   空段落
...   （循环每个 TC）
[N]   Heading1: "边界测试"              ← 下一测试类型
...   （同上循环）
```

**分组排列顺序：** 功能测试 → 边界测试 → 安全性测试 → 性能测试（仅输出有数据的分组）。

**关键约束：**
- 每个 TC 的表格与图片必须一一对应，图片紧跟表格之后
- 表格必须紧跟在对应 Heading2 之后（**禁止**先集中所有标题再集中所有表格）
- 图片与下一个 Heading2 之间间隔 2 个空段落
- 每个 TC 之间间隔 2 个空段落（图片后 1 个 + 额外 1 个）

#### 5.2 封面表（7 行 × 2 列）

**表格属性：**

| 属性 | 值 |
|------|-----|
| 表格边框 | 无（无边框定义，或全设为 `nil`） |
| 列宽 | 每列 `w:tcW w:w=4252 w:type=dxa`（约 2.25 英寸） |
| 单元格垂直对齐 | `vAlign=center` |
| 行高 | 默认（无 `trHeight` 设置） |

**逐行内容：**

| 行号 | 左列 | 右列 |
|------|------|------|
| 0 | `标识：` | （空，待填） |
| 1 | `密级：` | （空，待填） |
| 2 | `技术文件` | `技术文件` |
| 3 | `<软件名称>` | `<软件名称>` |
| 4 | `软件测试报告` | `软件测试报告` |
| 5 | `拟制：\n审核：\n会签：\n批准：` | `拟制：\n审核：\n会签：\n批准：` |

> 注意：行 5 中各角色标签之间使用换行符 `\n` 分隔，在同一个段落内用 `<w:br/>` 实现换行。

| 行号 | 左列 | 右列 |
|------|------|------|
| 6 | `<单位名称>\n<年月>` | `<单位名称>\n<年月>` |

**字体样式（全表统一）：**

| 属性 | 值 |
|------|-----|
| 字体 | 宋体（`w:rFonts w:eastAsia=宋体 w:ascii=宋体`） |
| 字号 | `w:sz w:val=24`（12pt） |
| 加粗 | 是（`w:b` + `w:bCs`） |
| 颜色 | 默认（黑色） |
| 段落对齐 | `left` |

**封面表后：** 1 个空段落（无样式、无间距设置），然后是 Heading1 "文档修改记录"。

#### 5.3 文档修改记录表（5 行 × 5 列）

**表格属性：**

| 属性 | 值 |
|------|-----|
| 表格宽度 | `w:tblW w:w=0 w:type=auto` |
| 边框 | 全黑实线 `w:sz=4 w:color=000000`（top/left/bottom/right/insideH/insideV 均为 `single`） |
| gridCol | 5 列，每列 `w:w=1728` |

**逐行内容：**

| 行号 | 内容 | 底纹 |
|------|------|------|
| 0（表头） | `版本号` \| `修改内容描述` \| `修改人` \| `日期` \| `备注` | `#D9E2F3` |
| 1-4 | 全空（待填写） | 无 |

**表头字体：** 宋体 9pt，加粗，蓝色底纹。数据行无底纹。

#### 5.4 页面与排版规范（实测值）

| 属性 | EMU 值 | 换算 |
|------|--------|------|
| 纸张宽度 | `7772400` | 8.50 英寸（Letter） |
| 纸张高度 | `10058400` | 11.00 英寸 |
| 上边距 | `914400` | 1.00 英寸 |
| 下边距 | `914400` | 1.00 英寸 |
| 左边距 | `1143000` | 1.25 英寸 |
| 右边距 | `1143000` | 1.25 英寸 |

**Heading1 样式（正文标题 + 附录标题共用）：**

| 属性 | 值 |
|------|-----|
| 字体 | 黑体（通过 `w:rFonts w:eastAsia=黑体` 设置，`font.name` 为 None） |
| 字号 | `font.size=177800`（14pt） |
| 加粗 | 是 |
| 颜色 | `font.color.rgb=365F91`（深蓝） |
| 段前间距 | `space_before=304800`（24pt） |
| 段后间距 | `space_after=0` |
| 行间距 | 默认 |

**Heading2 样式（用例编号 TC-XXX）：**

| 属性 | 值 |
|------|-----|
| 字体 | 黑体（通过 `w:rFonts w:eastAsia=黑体` 设置，`font.name` 为 None） |
| 字号 | `font.size=165100`（13pt） |
| 加粗 | 是 |
| 颜色 | `font.color.rgb=4F81BD`（蓝色） |
| 段前间距 | `space_before=127000`（10pt） |
| 段后间距 | `space_after=0` |

> **注意：** 实测模板使用 Letter 纸张（8.5×11 英寸），非 A4。Heading1 标题字体为**黑体 14pt**（非 15pt），颜色 `#365F91`。Heading2 为**黑体 13pt**（非 16pt），颜色 `#4F81BD`。这些是模板实际值，与之前估计值不同。

#### 5.5 TC 表格结构（16 行 × 8 列）

**表格 XML 属性：**

```xml
<w:tbl>
  <w:tblPr>
    <w:tblW w:w="0" w:type="auto"/>          <!-- 宽度自适应 -->
    <w:tblBorders>                              <!-- 全黑实线边框 -->
      <w:top w:val="single" w:sz="4" w:color="000000" w:space="0"/>
      <w:left w:val="single" w:sz="4" w:color="000000" w:space="0"/>
      <w:bottom w:val="single" w:sz="4" w:color="000000" w:space="0"/>
      <w:right w:val="single" w:sz="4" w:color="000000" w:space="0"/>
      <w:insideH w:val="single" w:sz="4" w:color="000000" w:space="0"/>
      <w:insideV w:val="single" w:sz="4" w:color="000000" w:space="0"/>
    </w:tblBorders>
  </w:tblPr>
  <w:tblGrid>
    <w:gridCol w:w="1080"/>  <!-- ×8 列 -->
  </w:tblGrid>
</w:tbl>
```

**逐行定义：**

| 行号 | 实际 `tc` 数量 | gridSpan 布局 | 内容 | 底纹 |
|------|---------------|---------------|------|------|
| 0 | 2 | 4 + 4 | `测试用例名称：{title}` \| `测试用例标识：{id}` | `#D9E2F3` |
| 1 | 1 | 8 | `测试用例描述：{description}` | `#D9E2F3` |
| 2 | 1 | 8 | `测试用例输入：优先级：{priority}。{description}` | `#D9E2F3` |
| 3 | 1 | 8 | `测试类型：{test_type}` | `#D9E2F3` |
| 4 | 1 | 8 | `前提和约束：视频第 {frame_num} 帧 ({timestamp}s)` | `#D9E2F3` |
| 5 | 1 | 8 | `测试终止条件：正常终止：该测试项的所有测试用例都正常终止。异常终止：测试过程中出现异常情况，需记录异常原因并终止测试。` | `#D9E2F3` |
| 6 | 1 | 8 | `测试过程` | `#D9E2F3` |
| 7 | 5 | 1 + 2 + 2 + 2 + 1 | `序号` \| `输入及操作步骤` \| `期望测试结果` \| `评估准则` \| `实际测试结果` | `#D9E2F3` |
| 8-13 | 5 | 1 + 2 + 2 + 2 + 1 | 步骤数据行（最多 6 行；超出实际步骤数的行不添加单元格，保持真空行） | 无 |
| 14 | 1 | 8 | `测试结论`（留空待填） | `#D9E2F3` |
| 15 | 2 | 4 + 4 | `测试人员` \| `测试日期` | `#D9E2F3` |

**单元格 XML 样式（标签行 Row 0-7, 14-15）：**

```xml
<w:tc>
  <w:tcPr>
    <w:gridSpan w:val="4"/>        <!-- 按实际列数设置 -->
    <w:vAlign w:val="center"/>
    <w:shd w:val="clear" w:color="auto" w:fill="D9E2F3"/>
  </w:tcPr>
  <w:p>
    <w:pPr>
      <w:jc w:val="left"/>         <!-- 水平左对齐 -->
      <w:spacing w:before="0" w:after="0" w:line="280" w:lineRule="auto"/>
    </w:pPr>
    <w:r>
      <w:rPr>
        <w:b/><w:bCs/>              <!-- 加粗 -->
        <w:sz w:val="18"/>          <!-- 9pt -->
        <w:szCs w:val="18"/>
        <w:rFonts w:ascii="宋体" w:hAnsi="宋体" w:eastAsia="宋体"/>
      </w:rPr>
      <w:t xml:space="preserve">...</w:t>
    </w:r>
  </w:p>
</w:tc>
```

**单元格 XML 样式（数据行 Row 8-13）：** 与标签行结构相同，但**不加粗**（无 `w:b`/`w:bCs`）且**无底纹**（无 `w:shd`）。

**评估准则列：** 有实际步骤的行填 `与预期结果一致`；超出实际步骤数的空行不添加单元格（真空行，禁止填“与预期结果一致”）。

**实际测试结果列：** 步骤数据行中留空（空 `w:t` 元素，`xml:space="preserve"`）。

#### 5.6 图片段落规范

**XML 结构：**

```xml
<w:p>
  <w:pPr>
    <w:jc w:val="center"/>         <!-- 居中对齐 -->
  </w:pPr>
  <w:r>
    <w:drawing>
      <wp:inline distT="0" distB="0" distL="0" distR="0">
        <wp:extent cx="5029200" cy="2824920"/>    <!-- 5.51 × 3.10 英寸 -->
        ...
      </wp:inline>
    </w:drawing>
  </w:r>
</w:p>
```

| 属性 | 值 |
|------|-----|
| 宽度 | 5.51 英寸（`cx="5029200"` EMU） |
| 高度 | 按比例缩放（1912×1076 → 约 3.10 英寸） |
| 段落对齐 | `center` |
| 图片间距 | `distT=0, distB=0, distL=0, distR=0` |

**python-docx 实现：**

```python
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

img_para = doc.add_paragraph()
img_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = img_para.add_run()
run.add_picture(source_img, width=Inches(5.51))
```

**图片插入位置控制（关键）：**

由于必须保证 TABLE → IMAGE → P(empty) → P(empty) 的精确顺序，不能使用 `doc.add_paragraph()` 然后 append（会添加到末尾）。正确做法：

```python
# 先用 add_paragraph 创建（添加到 body 末尾）
img_para = doc.add_paragraph()
img_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = img_para.add_run()
run.add_picture(img_path, width=Inches(5.51))

# 从 body 末尾移除，插入到表格之后
p_img = img_para._element
body.remove(p_img)
tbl_idx = list(body).index(tbl_elem)
body.insert(tbl_idx + 1, p_img)

# 空段落同理：先 add_paragraph，再 remove + insert
prev_idx = list(body).index(p_img)
for k in range(2):
    ep = doc.add_paragraph()._element
    body.remove(ep)
    prev_idx += 1
    body.insert(prev_idx, ep)
```

#### 5.7 技术实现要点（Agent 开发必读）

**python-docx 合并单元格陷阱：**

python-docx 的 `cell.merge()` 会物理删除被合并的 `tc` 元素，导致后续 `table.cell(r, c)` 索引错位。`_set_cell_content()` 等函数依赖 python-docx 的 cell 缓存也会写入错误的单元格。

**解决方案 — 纯 XML 构建：**

直接用 `OxmlElement` 构建只含必要 `tc` 元素的表格，彻底绕过 `add_table` + `cell.merge()` 机制。核心模式：

```python
def mk_cell(text, grid_span=1, shading=None, bold=False, font="宋体", fsize="18"):
    """构建单个单元格 XML 元素
    
    注意：text 必须为字符串，传入整数会报 Argument must be bytes or unicode 错误。
    step_number 等数值需先 str() 转换。
    """
    tc = OxmlElement('w:tc')
    tcPr = OxmlElement('w:tcPr')
    if grid_span > 1:
        gs = OxmlElement('w:gridSpan')
        gs.set(qn('w:val'), str(grid_span))
        tcPr.append(gs)
    va = OxmlElement('w:vAlign')
    va.set(qn('w:val'), 'center')
    tcPr.append(va)
    if shading:
        sh = OxmlElement('w:shd')
        sh.set(qn('w:val'), 'clear')
        sh.set(qn('w:color'), 'auto')
        sh.set(qn('w:fill'), shading)
        tcPr.append(sh)
    tc.append(tcPr)
    # ... 添加段落和run（含字体、加粗、行间距设置）
    return tc
```

**基于模板复用的推荐方式：**

直接打开模板 docx 文件，保留封面表和修改记录表，只替换附录3内容：

```python
from docx import Document

template_path = os.path.join(skill_dir, "references", "test_records_template.docx")
doc = Document(template_path)  # 打开模板
body = doc.element.body

# 1. 删除"附录3 测试记录"段落及之后的所有元素
to_remove = []
found = False
for elem in body:
    tag = elem.tag.split('}')[-1]  # 或 tag.rsplit('}', 1)[-1]
    if tag == 'p':
        text = ''.join(t.text or '' for t in elem.iter(qn('w:t')))
        if '附录3 测试记录' in text:
            found = True
            to_remove.append(elem)
            continue
    if found:
        to_remove.append(elem)
for e in to_remove:
    body.remove(e)

# 2. 添加新的附录3内容
doc.add_heading('附录3 测试记录', level=1)
# ... 按分组添加测试类型和TC（详见 5.1 结构）

doc.save(output_path)
```

> **优势：** 封面表、修改记录表、页面设置、样式定义全部从模板继承，无需手动重建。Agent 只需关注附录3内容的生成。

**独立脚本方式（推荐）：**

已将完整实现封装为 `scripts/generate_test_records.py`，支持命令行调用和 Agent 内联调用：

```bash
# 基本用法（自动使用 skill 内置模板）
python scripts/generate_test_records.py analysis_merged.json -o test_records.docx

# 指定关键帧目录（嵌入截图）
python scripts/generate_test_records.py analysis_merged.json -o test_records.docx \
    --keyframes-dir ./keyframes_std

# 指定自定义模板
python scripts/generate_test_records.py analysis_merged.json -o test_records.docx \
    --template ./references/test_records_template.docx
```

Agent 内联调用（步骤 3+4+5 一体化）：

```python
import sys
sys.path.insert(0, "<skill_dir>/scripts")
from generate_test_records import generate_test_records

generate_test_records(
    test_cases=test_cases,
    output_path="output/test_records.docx",
    keyframes_dir="output/keyframes_std",
)
# 模板路径默认指向 skill_dir/references/test_records_template.docx，无需指定
```

> **实测数据：** 57 个 TC，32 帧，产出 12,009 KB（57 个 16x8 表格 + 57 张截图）。脚本已内置文件占用容错（自动切换 `_v2` 后缀）。

**ffmpeg 图片兼容性：**

ffmpeg 提取的 JPEG 可能使用 python-docx 不支持的编码。**必须在 `add_picture()` 前用 PIL 标准化：**

```python
from PIL import Image
img = Image.open(src_path)
if img.mode != 'RGB':
    img = img.convert('RGB')
img.save(std_path, 'JPEG', quality=90)
```

**图片尺寸过大导致 view_image 失败：**

若 `view_image` 返回 `prompt token exceed limit`，需先用 PIL 缩小关键帧到 1280px 宽再分析：

```python
from PIL import Image
img = Image.open(frame_path)
if img.width > 1280:
    ratio = 1280 / img.width
    img = img.resize((1280, int(img.height * ratio)), Image.LANCZOS)
    img.save(resized_path, quality=85)
```

**`elem.tag.split('}')[-1]` IndexError 陷阱：**

当 XML 命名空间包含多个 `}` 时（如 lxml 默认 nsmap 包含 Python 命名空间），`tag.split('}')` 会产生多个元素，`[-1]` 可能取到错误值。**安全做法：**

```python
tag = elem.tag.rsplit('}', 1)[-1] if '}' in elem.tag else elem.tag
```

**`mk_cell` text 参数类型错误：**

`OxmlElement('w:t').text` 只接受 `str` 或 `bytes`，传入 `int` 会报 `Argument must be bytes or unicode`。**所有数值必须先 `str()` 转换：**

```python
# 错误
mk_cell(step["step_number"], ...)  # 若 step_number 为 int

# 正确
mk_cell(str(step["step_number"]), ...)
```

### 一键运行与断点续跑

```bash
# 全自动
python scripts/pipeline.py <video_path> <output_dir> --api-key sk-xxx

# 跳过步骤1（关键帧已提取）
python scripts/pipeline.py <video_path> <output_dir> --skip-extract --api-key sk-xxx

# 跳过步骤2+2.5（分析已完成），仅重新生成报告
python scripts/pipeline.py <video_path> <output_dir> --skip-extract --skip-analyze
```

**文件占用容错：** 输出文件被 WPS 占用时自动切换 `_v2` 后缀路径。

## 脚本清单

| 脚本 | 功能 | 独立运行 |
|------|------|----------|
| `scripts/extract_keyframes.py` | SSIM 关键帧提取 + 二次筛选（高效模式默认参数） | 是 |
| `scripts/analyze_frames.py` | AI 分析 + Markdown 解析 + 工具函数 | 是 |
| `scripts/merge_test_cases.py` | 单步用例合并为多步骤 + 预期结果推断 | 是 |
| `scripts/generate_reports.py` | Excel(xlsxwriter) + Word(docx) | 是 |
| `scripts/generate_test_records.py` | 模板格式测试记录（YFJZ-R805-05），纯 XML 构建 16x8 表格，支持 CLI 和 Agent 内联调用 | 是 |
| `scripts/pipeline.py` | 串联全部步骤 + 错误处理 + 容错 | 是 |

## 中间数据格式

```json
// frame_info.json（步骤1）
[["path/to/key_00000_0.0s.jpg", 0.0]]

// analysis.json（步骤2）
{
  "test_cases": [{ "id": "TC-001", ... }],
  "raw_markdowns": [{ "frame_idx": 1, "content": "## TC-001: ..." }],
  "summary": { "total_frames": 35, "total_test_cases": 260, "by_priority": {...} }
}

// analysis_merged.json（步骤2.5 + 步骤2.6）
{
  "test_cases": [{ "id": "TC-001", "test_type": "功能测试", "steps": [...] }],
  "summary": { "total_test_cases": 57, "original_count": 72, "by_type": {...} }
}
```

## 常见问题

**Q: 长视频关键帧提取太慢或超时？**
A: 默认参数已是高效模式（sample_every=5, resize=320, threshold=0.90），4 分钟视频约 1-2 分钟。如仍不够快，可增大 sample_every 到 8 或减小 resize 到 240。

**Q: 关键帧数量太多？**
A: 使用 `--filter-interval 5` 二次筛选，30-50 帧即可覆盖主要场景。

**Q: 场景变化遗漏（帧太少）？**
A: 改用精细模式：`--threshold 0.95 --sample-every 3 --resize 480`，会捕获更细微的界面变化。

**Q: 没有 API Key？**
A: 使用方式 B（内置 view_image 工具），Agent 逐帧分析后调用 `parse_markdown_test_cases()` 解析。

**Q: 输出文件被占用？**
A: pipeline 自动切换 `_v2` 后缀路径，也可手动关闭 WPS 后重试。

**Q: AI 返回的 Markdown 解析失败？**
A: `parse_markdown_test_cases()` 已适配多种变体（中文冒号、分隔行差异等），检查内容是否包含 `## TC-XXX` 标题。

**Q: 测试用例只有 1 步？**
A: 正常现象——AI 通常为每个操作生成独立用例。运行 `merge_test_cases.py` 合并为多步骤用例。

**Q: 合并后大量用例步骤描述为空？**
A: 这是 `merge_test_cases()` 的已知问题（见步骤 2.6）。当 `_source_image` 为空或同帧用例不足 `min_group_size` 时，合并仅推断预期结果但不补全步骤描述。**必须执行步骤 2.6**，通过 `view_image` 基于截图和标题重新生成步骤。实测 72→57 合并后有 94.7%（54/57）用例步骤为空。

**Q: view_image 提示 prompt token exceed limit？**
A: 原始关键帧分辨率过大（如 1912×1076），用 PIL 缩小到 1280px 宽度后再提交分析。

**Q: add_picture() 抛出 UnrecognizedImageError？**
A: ffmpeg 提取的 JPEG 编码不兼容 python-docx，必须先用 PIL 转换为标准 JPEG（`Image.open().convert('RGB').save()`）。

**Q: 优先级全部解析为"中"？**
A: 检查 AI 返回的 Markdown 中 `**优先级**` 的格式是否匹配正则。若格式不一致，需手动构建 `priority_map` 修正。

**Q: `elem.tag.split('}')[-1]` 报 IndexError？**
A: lxml 的命名空间可能包含多个 `}`。使用 `elem.tag.rsplit('}', 1)[-1]` 替代，或先检查 `'}' in elem.tag`。

**Q: `OxmlElement('w:t').text = 1` 报类型错误？**
A: `text` 属性只接受 `str` 或 `bytes`，数值需先 `str()` 转换。

**Q: Word 表格中有多余的空行显示“与预期结果一致”？**
A: TC 表格固定 16 行，步骤区 Row 8-13 最多 6 行。当用例只有 2~4 步时，多余行不得添加任何单元格（保持真空行）。错误做法是给空行也填上序号和“与预期结果一致”。正确实现：仅在 `i < len(steps)` 时创建单元格，否则只创建空的 `w:tr`。
