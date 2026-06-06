#!/usr/bin/env python3
"""
主流程 - 串联关键帧提取、AI 分析、用例合并、报告生成的完整流水线

输出结构:
  output_dir/
  ├── keyframes/            步骤1: 关键帧图片
  ├── frame_info.json       步骤1: 帧信息
  ├── analysis.json         步骤2: AI 分析结果 + 原始 Markdown
  ├── analysis_merged.json  步骤2.5: 合并后的多步用例
  ├── test_cases.xlsx       步骤3: 格式化 Excel
  ├── test_report.docx      步骤4: 图文 Word 报告
  └── test_records.docx     步骤5: 模板格式测试记录

用法:
    # 方式 A: 使用外部 API 全自动运行
    python pipeline.py <video_path> <output_dir> --api-key sk-xxx

    # 断点续跑
    python pipeline.py <video_path> <output_dir> --skip-extract --skip-analyze

    # 自定义参数
    python pipeline.py <video_path> <output_dir> --api-key sk-xxx \
        --threshold 0.92 --sample-every 3 --filter-interval 5 \
        --context "管理员后台" --requirements "覆盖登录功能"

注意:
    如果用户未提供 API Key，Agent 应使用方式 B（内置 view_image 工具）完成步骤 2，
    具体操作见 SKILL.md 的「方式 B: 内置工具分析」章节。
"""

import json
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extract_keyframes import extract_keyframes, filter_frames_by_interval
from analyze_frames import (
    analyze_all_frames, parse_markdown_test_cases,
    merge_test_case_lists, build_analysis_output, save_analysis,
)
from generate_reports import save_to_excel, save_to_word
from generate_test_records import generate_test_records
from merge_test_cases import merge_test_cases


def run_pipeline(video_path, output_dir,
                 similarity_threshold=0.92,
                 sample_every=3, resize_width=480,
                 filter_interval=0,
                 model="gpt-4o", api_key=None,
                 base_url="https://api.openai.com/v1",
                 context="", requirements="",
                 skip_extract=False, skip_analyze=False,
                 delay=0.3,
                 min_group_size=2, max_steps=8,
                 software_name="某某系统", doc_id="YF-STR-XX"):
    """
    执行完整流水线

    Args:
        video_path:            视频文件路径
        output_dir:            输出目录
        similarity_threshold:  SSIM 阈值
        sample_every:          降采样间隔
        resize_width:          SSIM 计算缩放宽度
        filter_interval:       二次筛选间隔（秒），0=不筛选
        model:                 AI 模型名称
        api_key:               API Key
        base_url:              API Base URL
        context:               测试上下文
        requirements:          测试需求
        skip_extract:          跳过关键帧提取
        skip_analyze:          跳过 AI 分析（含合并）
        delay:                 API 请求间隔
        min_group_size:        合并时每组最少用例数
        max_steps:             合并后每个用例最多步骤数
        software_name:         软件名称（用于测试记录封面）
        doc_id:                文档标识号

    Returns:
        test_cases: 合并后的测试用例列表
    """

    keyframes_dir = os.path.join(output_dir, "keyframes")
    frame_info_path = os.path.join(output_dir, "frame_info.json")
    analysis_path = os.path.join(output_dir, "analysis.json")
    merged_path = os.path.join(output_dir, "analysis_merged.json")
    excel_path = os.path.join(output_dir, "test_cases.xlsx")
    word_path = os.path.join(output_dir, "test_report.docx")
    test_records_path = os.path.join(output_dir, "test_records.docx")

    total_steps = 5

    # ========== 步骤1：关键帧提取 ==========
    if skip_extract and os.path.exists(frame_info_path):
        with open(frame_info_path, "r", encoding="utf-8") as f:
            frame_info = json.load(f)
        print(f"[跳过] 步骤1: 已有关键帧信息 ({len(frame_info)} 帧)")
    else:
        print("\n" + "=" * 50)
        print(f"步骤 1/{total_steps}: 关键帧提取")
        print("=" * 50)

        frame_info = extract_keyframes(
            video_path, keyframes_dir,
            similarity_threshold=similarity_threshold,
            sample_every=sample_every,
            resize_width=resize_width,
        )

        if filter_interval > 0 and len(frame_info) > 0:
            before_count = len(frame_info)
            frame_info = filter_frames_by_interval(frame_info, filter_interval)
            print(f"二次筛选: {before_count} -> {len(frame_info)} 帧 (间隔 {filter_interval}s)")

        os.makedirs(output_dir, exist_ok=True)
        with open(frame_info_path, "w", encoding="utf-8") as f:
            json.dump(frame_info, f, ensure_ascii=False, indent=2)
        print(f"帧信息已保存至: {frame_info_path}")

    if not frame_info:
        print("[错误] 未提取到任何关键帧，请检查视频或调整阈值")
        sys.exit(1)

    # ========== 步骤2：AI 分析 ==========
    if skip_analyze and os.path.exists(merged_path):
        with open(merged_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        test_cases = data.get("test_cases", [])
        print(f"\n[跳过] 步骤2+2.5: 已有合并结果 ({len(test_cases)} 个用例)")
    else:
        if skip_analyze and os.path.exists(analysis_path):
            with open(analysis_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            test_cases = data.get("test_cases", [])
            print(f"\n[跳过] 步骤2: 已有分析结果 ({len(test_cases)} 个用例)")
        else:
            print("\n" + "=" * 50)
            print(f"步骤 2/{total_steps}: AI 批量分析")
            print("=" * 50)

            from openai import OpenAI

            key = api_key or os.environ.get("OPENAI_API_KEY")
            if not key:
                print("[错误] 请提供 API Key (--api-key 或 OPENAI_API_KEY 环境变量)")
                print("提示: 如果没有 API Key，请使用方式 B（内置 view_image 工具），详见 SKILL.md")
                sys.exit(1)

            client = OpenAI(api_key=key, base_url=base_url)
            test_cases, raw_mds = analyze_all_frames(
                client, frame_info, model=model,
                context=context, requirements=requirements,
                delay=delay,
            )

            output = build_analysis_output(test_cases, raw_mds, len(frame_info))
            save_analysis(output, analysis_path)

            original_count = len(test_cases)
            summary = output["summary"]
            print(f"分析完成: 共 {original_count} 个用例")
            print(f"优先级分布: {summary['by_priority']}")

        # ========== 步骤2.5：用例合并与步骤补全 ==========
        print("\n" + "=" * 50)
        print(f"步骤 2.5/{total_steps}: 用例合并与步骤补全")
        print("=" * 50)

        original_count = len(test_cases)
        test_cases = merge_test_cases(test_cases, min_group_size=min_group_size, max_group_size=max_steps)
        print(f"合并: {original_count} 个单步用例 -> {len(test_cases)} 个多步用例")

        merged_output = build_analysis_output(test_cases, frame_count=original_count)
        merged_output["summary"]["original_count"] = original_count
        with open(merged_path, "w", encoding="utf-8") as f:
            json.dump(merged_output, f, ensure_ascii=False, indent=2)

    # ========== 步骤3：生成 Excel ==========
    print("\n" + "=" * 50)
    print(f"步骤 3/{total_steps}: 生成 Excel")
    print("=" * 50)

    try:
        save_to_excel(test_cases, excel_path)
    except PermissionError:
        alt_path = excel_path.replace(".xlsx", "_v2.xlsx")
        print(f"[警告] {excel_path} 被占用，使用备选路径: {alt_path}")
        save_to_excel(test_cases, alt_path)
        excel_path = alt_path

    # ========== 步骤4：生成 Word ==========
    print("\n" + "=" * 50)
    print(f"步骤 4/{total_steps}: 生成 Word 报告")
    print("=" * 50)

    try:
        save_to_word(test_cases, word_path)
    except PermissionError:
        alt_path = word_path.replace(".docx", "_v2.docx")
        print(f"[警告] {word_path} 被占用，使用备选路径: {alt_path}")
        save_to_word(test_cases, alt_path)
        word_path = alt_path

    # ========== 步骤5：生成测试记录 ==========
    print("\n" + "=" * 50)
    print(f"步骤 5/{total_steps}: 生成测试记录（模板格式）")
    print("=" * 50)

    try:
        generate_test_records(test_cases, "", test_records_path,
                              software_name=software_name, doc_id=doc_id)
    except PermissionError:
        alt_path = test_records_path.replace(".docx", "_v2.docx")
        print(f"[警告] {test_records_path} 被占用，使用备选路径: {alt_path}")
        generate_test_records(test_cases, "", alt_path,
                              software_name=software_name, doc_id=doc_id)
        test_records_path = alt_path

    # ========== 完成 ==========
    print("\n" + "=" * 50)
    print("全部完成")
    print("=" * 50)
    print(f"  关键帧:   {keyframes_dir}/ ({len(frame_info)} 帧)")
    print(f"  分析结果: {analysis_path}")
    print(f"  合并结果: {merged_path}")
    print(f"  Excel:    {excel_path}")
    print(f"  Word:     {word_path}")
    print(f"  测试记录: {test_records_path}")

    return test_cases


def main():
    parser = argparse.ArgumentParser(description="视频测试用例生成 - 完整流水线")
    parser.add_argument("video_path", help="操作视频文件路径")
    parser.add_argument("output_dir", help="输出目录")

    # 步骤1 参数
    parser.add_argument("--threshold", type=float, default=0.92,
                        help="SSIM 阈值 (0~1)，默认 0.92")
    parser.add_argument("--sample-every", type=int, default=3,
                        help="每隔 N 帧采样一次，默认 3")
    parser.add_argument("--resize", type=int, default=480,
                        help="SSIM 计算缩放宽度，0=不缩放，默认 480")
    parser.add_argument("--filter-interval", type=float, default=0,
                        help="二次筛选间隔（秒），0=不筛选，默认 0")

    # 步骤2 参数
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--base-url", default="https://api.openai.com/v1")
    parser.add_argument("--delay", type=float, default=0.3)
    parser.add_argument("--context", default="", help="测试上下文")
    parser.add_argument("--requirements", default="", help="测试需求")

    # 步骤2.5 参数
    parser.add_argument("--min-group", type=int, default=2,
                        help="合并时每组最少用例数，默认 2")
    parser.add_argument("--max-steps", type=int, default=8,
                        help="合并后每个用例最多步骤数，默认 8")

    # 步骤5 参数
    parser.add_argument("--software-name", default="某某系统", help="软件名称")
    parser.add_argument("--doc-id", default="YF-STR-XX", help="文档标识号")

    # 断点续跑
    parser.add_argument("--skip-extract", action="store_true",
                        help="跳过步骤1（使用已有 frame_info.json）")
    parser.add_argument("--skip-analyze", action="store_true",
                        help="跳过步骤2+2.5（使用已有 analysis_merged.json）")

    args = parser.parse_args()

    run_pipeline(
        video_path=args.video_path,
        output_dir=args.output_dir,
        similarity_threshold=args.threshold,
        sample_every=args.sample_every,
        resize_width=args.resize,
        filter_interval=args.filter_interval,
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
        context=args.context,
        requirements=args.requirements,
        skip_extract=args.skip_extract,
        skip_analyze=args.skip_analyze,
        delay=args.delay,
        min_group_size=args.min_group,
        max_steps=args.max_steps,
        software_name=args.software_name,
        doc_id=args.doc_id,
    )


if __name__ == "__main__":
    main()
