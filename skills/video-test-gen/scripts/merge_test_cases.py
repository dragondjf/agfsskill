#!/usr/bin/env python3
"""
测试用例合并与步骤补全 - 将同一场景下的多个单步用例合并为多步骤用例

问题: AI 分析时每帧生成多个单步用例（每个只有1个步骤），导致测试记录中每个用例只有1步。
解决: 将同一界面场景下的相关用例按测试类型（正向/负向/边界）分组，每组合并为一个多步骤用例。

合并策略:
  1. 按 _source_image（同一帧截图）分组
  2. 每组内按测试类型（正向/异常/边界/安全/性能）分类
  3. 同类型的用例合并为一个，原用例的描述作为操作步骤
  4. 根据用例描述自动推断预期结果
  5. 重新编号

用法:
    python merge_test_cases.py <analysis_new.json> <output_merged.json>

依赖: 无额外依赖
"""

import json
import os
import sys
import re
import argparse
from collections import OrderedDict, Counter


def classify_test_type(tc):
    """
    根据用例标题和描述推断测试类型

    Returns:
        (category, sub_type) 如 ("正向测试", "功能测试")
    """
    title = tc.get("title", "").lower()
    desc = tc.get("description", "").lower()

    # 正向 vs 负向
    if any(kw in title or kw in desc for kw in ["异常", "错误", "非法", "无效", "不合法", "负向", "负面", "删除关键", "不正确", "错误提示"]):
        category = "异常测试"
    elif any(kw in title or kw in desc for kw in ["边界", "极限", "最大值", "最小值", "为0", "为空", "超长", "超出"]):
        category = "边界测试"
    elif any(kw in title or kw in desc for kw in ["安全", "权限", "越权", "注入", "攻击"]):
        category = "安全性测试"
    elif any(kw in title or kw in desc for kw in ["性能", "响应时间", "并发", "压力", "负载", "吞吐"]):
        category = "性能测试"
    else:
        category = "正向测试"

    # 测试子类型
    if "安全" in category:
        sub_type = "安全性测试"
    elif "性能" in category:
        sub_type = "性能测试"
    elif "边界" in category:
        sub_type = "边界测试"
    else:
        sub_type = "功能测试"

    return category, sub_type


def infer_expected_result(desc, category):
    """
    根据操作描述和测试类型推断预期结果

    策略:
    - 正向测试: 操作成功，结果符合预期
    - 异常测试: 系统给出正确错误提示，不崩溃
    - 边界测试: 根据边界值类型推断
    - 包含"验证"/"检查"/"查看"等词: 提取验证目标
    """
    desc_lower = desc.lower()

    # 异常测试
    if "异常" in category:
        # 包含具体验证目标的
        if "验证" in desc or "检查" in desc or "查看" in desc:
            # 提取"验证/检查/查看"后面的内容
            match = re.search(r'(?:验证|检查|查看|确认)\s*(.+)', desc)
            if match:
                target = match.group(1).strip()
                return f"{target}，系统给出正确的错误提示或异常处理"
        # 包含"是否有"的
        if "是否有" in desc or "是否" in desc:
            match = re.search(r'是否\s*(.+)', desc)
            if match:
                return f"{match.group(1).strip()}"
        return "系统给出正确的错误提示或异常信息，不崩溃"

    # 边界测试
    if "边界" in category:
        if "设置为0" in desc or "为0" in desc:
            return "系统能够正确处理零值边界情况，给出预期响应"
        if "最大" in desc or "65535" in desc or "上限" in desc:
            return "系统在上限边界值下正常工作，功能不受影响"
        if "最小" in desc or "小于" in desc or "为1" in desc:
            return "系统正确处理最小边界值，给出相应提示"
        if "超长" in desc or "超出" in desc:
            return "系统对超限输入做出正确限制或截断处理"
        if "为空" in desc or "空值" in desc:
            return "系统正确处理空值情况，给出提示或不影响功能"
        return "系统在边界条件下正确处理，行为符合预期"

    # 正向测试
    if "验证" in desc or "检查" in desc or "查看" in desc or "确认" in desc:
        match = re.search(r'(?:验证|检查|查看|确认)\s*(.+)', desc)
        if match:
            target = match.group(1).strip()
            # 去掉开头的"是否"
            target = re.sub(r'^是否', '', target)
            return f"{target}，结果正确"
        return "操作成功执行，系统响应正常"

    if "运行" in desc:
        return "程序正常运行，输出结果符合预期"
    if "切换" in desc or "打开" in desc:
        return "成功切换/打开，界面显示正确"
    if "点击" in desc:
        match = re.search(r'点击(.+?)[，。]', desc)
        if match:
            btn = match.group(1).strip()
            return f"{btn}操作成功，界面响应正确"
        return "点击操作成功，界面响应正确"
    if "输入" in desc or "修改" in desc or "编辑" in desc:
        return "输入/修改成功，数据正确保存和显示"
    if "导入" in desc or "导出" in desc:
        return "导入/导出操作成功完成，数据完整"
    if "保存" in desc:
        return "保存成功，数据持久化正确"
    if "复制" in desc or "粘贴" in desc:
        return "操作成功，内容正确复制/粘贴"
    if "删除" in desc:
        return "删除成功，数据已移除"
    if "搜索" in desc or "查询" in desc or "筛选" in desc:
        return "搜索/查询结果正确，显示匹配项"

    return "操作成功执行，系统响应正常"


def extract_operation(desc):
    """
    从用例描述中提取简洁的操作步骤描述

    策略: 保留原始描述作为操作步骤（已经是简洁的操作描述）
    """
    return desc.strip()


def merge_test_cases(test_cases, min_group_size=2, max_group_size=8):
    """
    将单步用例合并为多步骤用例

    Args:
        test_cases:      原始测试用例列表（多为单步）
        min_group_size:  最少合并几个用例为一组（少于此数的保持独立）
        max_group_size:  每组最多包含几个步骤

    Returns:
        合并后的测试用例列表
    """
    # 按来源图片分组
    scenes = OrderedDict()
    for tc in test_cases:
        scene = tc.get("_source_image", "__none__")
        if scene not in scenes:
            scenes[scene] = []
        scenes[scene].append(tc)

    merged = []
    case_counter = 0

    for scene, cases in scenes.items():
        # 按测试类型分组
        type_groups = OrderedDict()
        for tc in cases:
            category, sub_type = classify_test_type(tc)
            key = (category, sub_type)
            if key not in type_groups:
                type_groups[key] = []
            type_groups[key].append(tc)

        for (category, sub_type), group_cases in type_groups.items():
            # 如果该组用例太少，保持独立（但仍补全步骤）
            if len(group_cases) < min_group_size:
                for tc in group_cases:
                    case_counter += 1
                    desc = tc.get("description", "")
                    steps = tc.get("steps", [])
                    merged_tc = {
                        "id": f"TC-{case_counter:03d}",
                        "title": f"{category} - {tc.get('title', '').split(' - ', 1)[-1] if ' - ' in tc.get('title', '') else tc.get('title', '未命名')}",
                        "description": desc,
                        "preconditions": tc.get("preconditions", ""),
                        "priority": tc.get("priority", "中"),
                        "test_type": sub_type,
                        "_source_image": tc.get("_source_image", ""),
                        "_source_timestamp": tc.get("_source_timestamp", 0),
                    }
                    if steps:
                        merged_tc["steps"] = []
                        for s in steps:
                            new_expected = infer_expected_result(
                                s.get("description", desc), category
                            )
                            merged_tc["steps"].append({
                                "step_number": s.get("step_number", 1),
                                "description": s.get("description", desc),
                                "expected_result": new_expected,
                            })
                    else:
                        merged_tc["steps"] = [{
                            "step_number": 1,
                            "description": desc,
                            "expected_result": infer_expected_result(desc, category),
                        }]
                    merged.append(merged_tc)
            else:
                # 合并为一个多步骤用例
                case_counter += 1
                steps = []
                # 截取到 max_group_size
                selected = group_cases[:max_group_size]

                for step_idx, tc in enumerate(selected, 1):
                    desc = tc.get("description", "")
                    if not desc:
                        old_steps = tc.get("steps", [])
                        if old_steps:
                            desc = old_steps[0].get("description", "")

                    expected = infer_expected_result(desc, category)

                    steps.append({
                        "step_number": step_idx,
                        "description": desc or f"执行{category}步骤 {step_idx}",
                        "expected_result": expected,
                    })

                # 用例标题：取第一个用例的场景描述
                first_title = selected[0].get("title", "")
                # 提取场景描述（去掉"正向测试 - "等前缀）
                scene_desc = first_title.split(" - ", 1)[-1] if " - " in first_title else first_title

                merged_tc = {
                    "id": f"TC-{case_counter:03d}",
                    "title": f"{category} - {scene_desc}",
                    "description": f"对{scene_desc.split('，')[0]}进行{category}，共{len(steps)}个操作步骤",
                    "preconditions": selected[0].get("preconditions", ""),
                    "priority": selected[0].get("priority", "中"),
                    "test_type": sub_type,
                    "steps": steps,
                    "_source_image": selected[0].get("_source_image", ""),
                    "_source_timestamp": selected[0].get("_source_timestamp", 0),
                }
                merged.append(merged_tc)

                # 超出的用例单独保留
                for tc in group_cases[max_group_size:]:
                    case_counter += 1
                    desc = tc.get("description", "")
                    merged.append({
                        "id": f"TC-{case_counter:03d}",
                        "title": f"{category} - {tc.get('title', '').split(' - ', 1)[-1] if ' - ' in tc.get('title', '') else tc.get('title', '未命名')}",
                        "description": desc,
                        "preconditions": tc.get("preconditions", ""),
                        "priority": tc.get("priority", "中"),
                        "test_type": sub_type,
                        "steps": [{
                            "step_number": 1,
                            "description": desc,
                            "expected_result": infer_expected_result(desc, category),
                        }],
                        "_source_image": tc.get("_source_image", ""),
                        "_source_timestamp": tc.get("_source_timestamp", 0),
                    })

    return merged


def main():
    parser = argparse.ArgumentParser(description="合并单步测试用例为多步骤用例")
    parser.add_argument("input_json", help="输入 JSON（旧格式 analysis_new.json）")
    parser.add_argument("output_json", help="输出 JSON（合并后）")
    parser.add_argument("--min-group", type=int, default=2, help="最少合并 N 个用例为一组")
    parser.add_argument("--max-steps", type=int, default=8, help="每个用例最多 N 个步骤")
    args = parser.parse_args()

    with open(args.input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        test_cases = data.get("test_cases", [])
    else:
        test_cases = data

    print(f"输入: {len(test_cases)} 个用例")

    merged = merge_test_cases(test_cases, min_group_size=args.min_group, max_group_size=args.max_group)

    # 统计
    step_counts = Counter(len(tc["steps"]) for tc in merged)
    type_counts = Counter(tc.get("test_type", "未知") for tc in merged)
    cat_counts = Counter(tc["title"].split(" - ")[0] for tc in merged)

    print(f"输出: {len(merged)} 个用例")
    print(f"步骤数分布: {dict(sorted(step_counts.items()))}")
    print(f"测试类型分布: {dict(type_counts)}")
    print(f"测试分类分布: {dict(cat_counts)}")

    # 构建输出
    output = {
        "test_cases": merged,
        "summary": {
            "total_test_cases": len(merged),
            "original_count": len(test_cases),
            "by_type": dict(type_counts),
            "by_category": dict(cat_counts),
            "by_step_count": dict(sorted(step_counts.items())),
            "avg_steps": sum(len(tc["steps"]) for tc in merged) / len(merged),
        },
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.output_json)), exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n已保存至: {args.output_json}")

    # 展示几个多步骤用例示例
    multi_step = [tc for tc in merged if len(tc["steps"]) > 1]
    print(f"\n多步骤用例示例（共 {len(multi_step)} 个）:")
    for tc in multi_step[:3]:
        print(f"\n  {tc['id']} [{tc.get('test_type', '?')}] {tc['title'][:60]}")
        for s in tc["steps"]:
            print(f"    步骤{s['step_number']}: {s['description'][:50]}")
            print(f"            => {s['expected_result'][:50]}")


if __name__ == "__main__":
    main()
