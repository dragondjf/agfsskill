#!/usr/bin/env python3
"""
AI 关键帧分析脚本 - 逐张图片调用多模态模型生成结构化测试用例

两种使用方式:
  A. 外部 API: 通过 OpenAI 兼容 API 调用多模态模型
  B. 内置工具: Agent 直接调用 view_image 工具逐帧分析，再调用 parse_markdown_test_cases() 解析

输出数据结构（与 excel_service / ai_service 兼容）:
[
  {
    "id": "TC-001",
    "title": "正向登录测试",
    "description": "...",
    "preconditions": "...",
    "priority": "高/中/低",
    "steps": [
      {"step_number": 1, "description": "...", "expected_result": "..."}
    ]
  }
]

依赖: pip install openai
"""

import json
import os
import sys
import argparse
import base64
import time
import re


# ==================== Prompt 模板 ====================

SYSTEM_PROMPT = """你是一个专业的测试用例生成器，擅长基于界面截图生成全面的测试用例。

**关键要求**：
1. 必须严格按照指定的 Markdown 格式生成测试用例
2. 每个测试用例必须以 ## TC-XXX: 标题 格式开始
3. 必须包含 **优先级:**、**描述:**、**前置条件:** 等加粗字段
4. 测试步骤必须使用标准的 Markdown 表格格式，包含表头和分隔行
5. 表格必须有三列：#、步骤描述、预期结果
6. 确保格式完全符合要求，以便系统能够正确解析

请严格遵循格式要求，这对于系统解析测试用例非常重要。"""


def build_user_prompt(context: str = "", requirements: str = "") -> str:
    """构建用户提示词（与 ai_service 对齐）"""
    context_part = f"\n上下文信息: {context}" if context else ""
    req_part = f"\n需求: {requirements}" if requirements else ""

    return f"""请基于上传的界面截图生成全面的测试用例。{context_part}{req_part}

**重要格式要求**：
请严格按照以下格式生成测试用例，这对于系统解析非常重要：

1. 每个测试用例必须以二级标题开始：## TC-001: 测试标题
2. 每个测试用例必须包含以下字段（使用加粗格式）：
   - **优先级:** 高/中/低
   - **描述:** 测试用例的详细描述
   - **前置条件:** 执行测试前的条件（如果有）

3. 测试步骤必须使用标准 Markdown 表格格式：

### 测试步骤

| # | 步骤描述 | 预期结果 |
| --- | --- | --- |
| 1 | 具体的操作步骤 | 期望看到的结果 |
| 2 | 下一个操作步骤 | 对应的期望结果 |

请严格遵循此格式，确保每个测试用例都包含完整的信息和正确的表格格式。
请确保测试用例覆盖全面，包含正向和负向测试场景。"""


def build_view_image_prompt(context: str = "", requirements: str = "") -> str:
    """
    构建 view_image 工具使用的 prompt（方式 B）

    view_image 的 question 参数需要简洁的问题描述，
    同时通过 system_prompt 和 context 信息引导 AI 按正确格式返回。
    """
    context_part = f"\n上下文: {context}" if context else ""
    req_part = f"\n测试需求: {requirements}" if requirements else ""

    return (
        f"你是一个专业的测试用例生成器。请基于这张界面截图生成全面的测试用例。"
        f"{context_part}{req_part}\n\n"
        f"格式要求:\n"
        f"1. 每个测试用例以 ## TC-XXX: 标题 开始\n"
        f"2. 包含字段: **优先级:**, **描述:**, **前置条件:**\n"
        f"3. 测试步骤使用 Markdown 表格: | # | 步骤描述 | 预期结果 |\n"
        f"4. 覆盖正向和负向测试场景"
    )


# ==================== Markdown 解析 ====================

def parse_markdown_test_cases(markdown_text: str) -> list:
    """
    解析 AI 返回的 Markdown 格式测试用例

    支持多种格式变体:
    - ## TC-001: 标题  或  ## TC-001：标题（中文冒号）
    - **优先级:** 高  或  **优先级**：高
    - 表格分隔行: | --- | --- | --- |  或  |---|---|---|

    Returns:
        测试用例列表，每个用例为 dict，包含 id/title/description/preconditions/priority/steps
    """
    test_cases = []

    # 标准化：统一中文冒号为英文冒号，统一多余空格
    text = markdown_text.replace('\uff1a', ':')  # ：→ :
    text = re.sub(r'\*\*\s*', '**', text)  # ** xxx → **xxx

    # 按 ## TC-XXX 分割
    blocks = re.split(r'\n(?=## TC-\d+)', text)

    for block in blocks:
        block = block.strip()
        if not block.startswith("## TC-"):
            continue

        tc = {"steps": []}

        # 解析标题行: ## TC-001: 标题
        title_match = re.match(r'##\s+(TC-\d+)\s*[:：]\s*(.+)', block)
        if title_match:
            tc["id"] = title_match.group(1)
            tc["title"] = title_match.group(2).strip()

        # 解析优先级（支持多种写法）
        priority_match = re.search(
            r'\*\*优先级\*\*\s*[:：]?\s*(高|中|低|high|medium|low)',
            block, re.IGNORECASE
        )
        if priority_match:
            tc["priority"] = priority_match.group(1).strip()
            # 英文转中文
            pmap = {"high": "高", "medium": "中", "low": "低"}
            tc["priority"] = pmap.get(tc["priority"].lower(), tc["priority"])

        # 解析描述
        desc_match = re.search(r'\*\*描述\*\*\s*[:：]?\s*(.+)', block)
        if desc_match:
            tc["description"] = desc_match.group(1).strip()

        # 解析前置条件
        pre_match = re.search(r'\*\*前置条件\*\*\s*[:：]?\s*(.+)', block)
        if pre_match:
            tc["preconditions"] = pre_match.group(1).strip()

        # 解析步骤表格
        step_pattern = re.finditer(
            r'\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|',
            block
        )
        for m in step_pattern:
            num = int(m.group(1))
            desc = m.group(2).strip()
            expected = m.group(3).strip()
            # 跳过表头行（多种可能的写法）
            if desc in ("步骤描述", "步骤", "Step", "Step Description", "操作步骤"):
                continue
            if expected in ("预期结果", "预期", "Expected", "Expected Result", "期望结果"):
                continue
            if num == 0 and desc == "#":
                continue
            tc["steps"].append({
                "step_number": num,
                "description": desc,
                "expected_result": expected,
            })

        # 必须至少有标题才添加
        if tc.get("id") and tc.get("title"):
            tc.setdefault("priority", "中")
            tc.setdefault("description", "")
            tc.setdefault("preconditions", "")
            # 如果没有步骤，基于 description 生成一个默认步骤
            if not tc["steps"]:
                tc["steps"].append({
                    "step_number": 1,
                    "description": tc["description"] or tc["title"],
                    "expected_result": "操作成功执行，系统响应正常",
                })
            test_cases.append(tc)

    return test_cases


# ==================== API 调用 ====================

def analyze_frame(client, image_path, model="gpt-4o",
                  context: str = "", requirements: str = ""):
    """
    分析单张界面截图（方式 A: 外部 API）

    Returns:
        (test_cases_list, raw_markdown_string)
    """
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    user_message = build_user_prompt(context, requirements)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": user_message},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{img_b64}"
                }}
            ]}
        ],
        max_tokens=2000,
        temperature=0.2,
    )

    content = resp.choices[0].message.content.strip()
    test_cases = parse_markdown_test_cases(content)

    return test_cases, content


def analyze_all_frames(client, frame_info, model="gpt-4o",
                       context: str = "", requirements: str = "",
                       delay=0.3):
    """
    批量分析所有帧（方式 A: 外部 API）

    Args:
        client:       OpenAI client 实例
        frame_info:   [[图片路径, 时间戳], ...] 列表
        model:        模型名称
        context:      测试上下文
        requirements: 测试需求
        delay:        请求间隔秒数

    Returns:
        (all_test_cases, raw_markdowns)
    """
    all_test_cases = []
    raw_markdowns = []
    total = len(frame_info)

    for idx, (img_path, ts) in enumerate(frame_info, 1):
        if not os.path.exists(img_path):
            print(f"  [跳过] 第 {idx}/{total} 帧, 图片不存在: {img_path}")
            continue

        print(f"  分析第 {idx}/{total} 帧 ({ts:.1f}s)...")
        try:
            cases, raw_md = analyze_frame(
                client, img_path, model=model,
                context=context, requirements=requirements
            )
            for c in cases:
                c["_source_image"] = img_path
                c["_source_timestamp"] = round(ts, 2)
            all_test_cases.extend(cases)
            raw_markdowns.append({
                "frame_idx": idx,
                "timestamp": round(ts, 2),
                "image_path": img_path,
                "content": raw_md,
                "case_count": len(cases),
            })
            print(f"    -> 生成 {len(cases)} 个测试用例")
        except Exception as e:
            print(f"  [错误] 第 {idx} 帧分析失败: {e}")
            raw_markdowns.append({
                "frame_idx": idx,
                "timestamp": round(ts, 2),
                "image_path": img_path,
                "content": f"[错误: {e}]",
                "case_count": 0,
            })

        if idx < total:
            time.sleep(delay)

    return all_test_cases, raw_markdowns


# ==================== 工具函数 ====================

def merge_test_case_lists(*case_lists):
    """
    合并多个测试用例列表，自动重新编号

    Args:
        *case_lists: 多个 test_cases 列表

    Returns:
        合并后重新编号的列表
    """
    all_cases = []
    for cases in case_lists:
        all_cases.extend(cases)

    # 重新编号
    for i, tc in enumerate(all_cases, 1):
        tc["id"] = f"TC-{i:03d}"

    return all_cases


def build_analysis_output(test_cases, raw_markdowns=None, frame_count=0):
    """构建标准的 analysis.json 输出结构"""
    output = {
        "test_cases": test_cases,
        "summary": {
            "total_frames": frame_count,
            "total_test_cases": len(test_cases),
            "by_priority": {},
        },
    }

    # 按优先级统计
    from collections import Counter
    priorities = Counter(tc.get("priority", "未知") for tc in test_cases)
    output["summary"]["by_priority"] = dict(priorities)

    # 可选: 附加原始 Markdown
    if raw_markdowns:
        output["raw_markdowns"] = raw_markdowns

    return output


def save_analysis(output, output_path):
    """保存分析结果为 JSON"""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"分析结果已保存至: {output_path}")


# ==================== CLI ====================

def main():
    parser = argparse.ArgumentParser(description="AI 分析视频关键帧，生成测试用例")
    parser.add_argument("frame_info_json", help="关键帧信息 JSON 文件路径")
    parser.add_argument("output_json", help="分析结果输出 JSON 路径")
    parser.add_argument("--model", default="gpt-4o", help="模型名称")
    parser.add_argument("--api-key", default=None, help="API Key")
    parser.add_argument("--base-url", default="https://api.openai.com/v1", help="API Base URL")
    parser.add_argument("--delay", type=float, default=0.3, help="请求间隔秒数")
    parser.add_argument("--context", default="", help="测试上下文信息")
    parser.add_argument("--requirements", default="", help="测试需求描述")
    args = parser.parse_args()

    from openai import OpenAI

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("[错误] 请通过 --api-key 参数或 OPENAI_API_KEY 环境变量提供 API Key")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=args.base_url)

    with open(args.frame_info_json, "r", encoding="utf-8") as f:
        frame_info = json.load(f)

    print(f"加载了 {len(frame_info)} 个关键帧")
    test_cases, raw_mds = analyze_all_frames(
        client, frame_info, model=args.model,
        context=args.context, requirements=args.requirements,
        delay=args.delay,
    )

    output = build_analysis_output(test_cases, raw_mds, len(frame_info))
    save_analysis(output, args.output_json)

    print(f"\n完成: 共生成 {len(test_cases)} 个测试用例")
    summary = output["summary"]
    print(f"优先级分布: {summary['by_priority']}")


if __name__ == "__main__":
    main()
