#!/usr/bin/env python3
"""
DeepRunner 6.0 报告生成器

用法:
    # 单设备报告（1组测试）
    python generate_report.py --mode single --stats-dir <报告目录> --output-dir <输出目录>

    # 比对报告（2组测试对比）
    python generate_report.py --mode compare --stats-dir-a <报告目录A> --stats-dir-b <报告目录B> --output-dir <输出目录>

    # 批量单设备报告（扫描目录下所有测试组）
    python generate_report.py --mode batch --base-dir <基础目录> --output-dir <输出目录>

必需依赖: openpyxl (pip install openpyxl)
可选依赖: 无（HTML报告为纯字符串生成，不依赖Jinja/markdown等）
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ── Excel 依赖检查 ──
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.chart import LineChart, BarChart, Reference
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


# ============================================================
#  数据提取层
# ============================================================

def _find_entry(entries, keyword):
    """在 stats.json 条目列表中按 name 关键词查找"""
    for e in entries:
        if keyword.lower() in e.get('name', '').lower():
            return e
    return None


def extract_from_stats_json(stats_path):
    """从 stats.json 提取核心性能指标
    
    stats.json 实际结构: JSON 数组，每个元素是一个命名指标条目:
    [ {"name": "http://...", "num_requests": 12, "min_response_time": ..., "max_response_time": ...},
      {"name": "Time taken for tests (s)...", ...},
      {"name": "Throughput(average tokens/s)...", ...}, ... ]
    
    关键条目 name 匹配:
    - 'v1/chat/completions' → 主请求（延迟、请求数、QPS）
    - 'Throughput(average tokens/s)' → 吞吐量
    - 'Average QPS' → QPS
    - 'TTFT (s)' / 'Time to First Token' → 首Token时延
    - 'TPOT (s)' / 'Time Per Output Token' → 每输出Token时延
    - 'Average input tokens' / 'Input tokens' → 输入token
    - 'Average output tokens' / 'Output tokens' → 输出token
    - 'Average latency (s)' → 平均延迟（备用）
    """
    with open(stats_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 兼容：可能是列表或 {stats_requests: [...]} 格式
    if isinstance(data, dict):
        entries = data.get('stats_requests', data.get('data', []))
    elif isinstance(data, list):
        entries = data
    else:
        entries = []
    
    metrics = {}
    total_req = 0
    failed = 0
    
    # 1. 主请求条目（包含延迟和请求数）
    main_req = _find_entry(entries, 'chat/completions')
    if main_req:
        total_req = main_req.get('num_requests', 0)
        failed = main_req.get('num_failures', 0)
        n = total_req if total_req > 0 else 1
        total_rt = main_req.get('total_response_time', 0)
        metrics['avg_latency'] = total_rt / n / 1000  # ms→s
        metrics['min_latency'] = main_req.get('min_response_time', 0) / 1000
        metrics['max_latency'] = main_req.get('max_response_time', 0) / 1000
        # QPS: 从 num_reqs_per_sec 计算峰值
        rps = main_req.get('num_reqs_per_sec', {})
        metrics['max_qps'] = max(rps.values()) if rps else 0
        metrics['min_qps'] = min(rps.values()) if rps else 0
        metrics['avg_qps'] = len(rps) / max(main_req.get('last_request_timestamp', 0) - main_req.get('start_time', 1), 0.001)
    
    # 2. 平均延迟（备用，有些报告直接提供）
    avg_lat_entry = _find_entry(entries, 'Average latency')
    if avg_lat_entry and 'Average latency' in avg_lat_entry.get('name', ''):
        metrics['avg_latency'] = avg_lat_entry.get('min_response_time', metrics.get('avg_latency', 0))
    
    # 3. 吞吐量
    thr_entry = _find_entry(entries, 'Throughput(average tokens/s)')
    if not thr_entry:
        thr_entry = _find_entry(entries, 'Throughput')
    if thr_entry:
        metrics['throughput_avg'] = thr_entry.get('min_response_time', 0)
        metrics['throughput_min'] = thr_entry.get('min_response_time', 0)
        metrics['throughput_max'] = thr_entry.get('max_response_time', 0)
    
    # 4. QPS
    qps_entry = _find_entry(entries, 'Average QPS')
    if qps_entry:
        metrics['avg_qps'] = qps_entry.get('min_response_time', metrics.get('avg_qps', 0))
    
    # 5. TTFT
    ttft_entry = _find_entry(entries, 'TTFT')
    if ttft_entry:
        metrics['avg_ttft'] = ttft_entry.get('min_response_time', 0)
    
    # 6. TPOT
    tpot_entry = _find_entry(entries, 'TPOT')
    if tpot_entry:
        metrics['avg_tpot'] = tpot_entry.get('min_response_time', 0)
    
    # 7. 输入 tokens
    in_tok = _find_entry(entries, 'Input tokens')
    if in_tok:
        metrics['avg_input_tokens'] = in_tok.get('min_response_time', 0)
    
    # 8. 输出 tokens
    out_tok = _find_entry(entries, 'Output tokens')
    if out_tok:
        metrics['min_output_tokens'] = out_tok.get('min_response_time', 0)
        metrics['max_output_tokens'] = out_tok.get('max_response_time', 0)
    
    return {
        'metrics': metrics,
        'total_requests': total_req,
        'failed_requests': failed,
        'success_rate': (total_req - failed) / total_req if total_req > 0 else 1.0,
        'raw': entries,  # 保留原始条目列表
    }


def extract_concurrency_from_script(script_path):
    """从测试脚本提取并发数（正则匹配 '用户数': N 或 users=N）"""
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # 常见模式
        patterns = [
            r"'用户数'\s*:\s*(\d+)",
            r'"用户数"\s*:\s*(\d+)',
            r'users\s*=\s*(\d+)',
            r'concurrency\s*=\s*(\d+)',
            r"'并发数'\s*:\s*(\d+)",
        ]
        for pat in patterns:
            m = re.search(pat, content)
            if m:
                return int(m.group(1))
    except (FileNotFoundError, IOError):
        pass
    return None


def extract_test_config(apirunner_path):
    """从 apirunner.json 提取测试配置"""
    try:
        with open(apirunner_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def scan_test_groups(base_dir):
    """扫描目录下所有测试组，返回有序列表
    
    每个元素: {
        'dir': Path,
        'name': str,
        'stats': {...},        # extract_from_stats_json 结果
        'concurrency': int,    # 从脚本提取
        'config': {...},       # apirunner.json
    }
    按并发数升序排列
    """
    groups = []
    for item in sorted(Path(base_dir).iterdir()):
        if not item.is_dir():
            continue
        stats_file = item / 'stats.json'
        if not stats_file.exists():
            continue
        
        # 查找测试脚本
        script_files = list(item.glob('test*.py')) + list(item.glob('*test*.py'))
        concurrency = None
        for sf in script_files:
            concurrency = extract_concurrency_from_script(sf)
            if concurrency is not None:
                break
        
        # 提取性能数据
        stats = extract_from_stats_json(stats_file)
        
        # 提取测试配置
        config = extract_test_config(item / 'apirunner.json')
        
        groups.append({
            'dir': item,
            'name': item.name,
            'stats': stats,
            'concurrency': concurrency or 0,
            'config': config,
        })
    
    # 按并发数排序
    groups.sort(key=lambda g: g['concurrency'])
    return groups


# ============================================================
#  Excel 生成层
# ============================================================

def _write_excel_header(ws, title, subtitle):
    """写入 Excel 标题行"""
    ws.merge_cells('A1:Q1')
    ws['A1'] = title
    ws['A1'].font = Font(name='微软雅黑', size=16, bold=True)
    ws['A1'].alignment = Alignment(horizontal='center')
    
    ws.merge_cells('A2:Q2')
    ws['A2'] = subtitle
    ws['A2'].font = Font(name='微软雅黑', size=10, color='666666')
    ws['A2'].alignment = Alignment(horizontal='center')
    
    # 样式常量
    header_font = Font(name='微软雅黑', size=10, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='3B82F6', end_color='3B82F6', fill_type='solid')
    border = Border(
        left=Side(style='thin', color='D1D5DB'),
        right=Side(style='thin', color='D1D5DB'),
        top=Side(style='thin', color='D1D5DB'),
        bottom=Side(style='thin', color='D1D5DB'),
    )
    return header_font, header_fill, border


def generate_single_excel(groups, device_name, model_name, output_path):
    """生成单设备测试 Excel 报告
    
    Args:
        groups: scan_test_groups 返回的列表
        device_name: 设备名称
        model_name: 模型名称
        output_path: 输出文件路径
    """
    if not HAS_OPENPYXL:
        print("ERROR: 需要 openpyxl。执行 pip install openpyxl 后重试。")
        sys.exit(1)
    
    wb = openpyxl.Workbook()
    # Sheet 1: 逐组明细
    ws = wb.active
    ws.title = '逐组测试明细'
    
    title = f'DeepRunner 6.0 推理性能测试报告 - {device_name}'
    subtitle = f'模型: {model_name} | DeepRunner 6.0'
    hf, hfill, border = _write_excel_header(ws, title, subtitle)
    
    headers = ['序号', '并发数', '请求数', '失败数', '最小延迟(s)', '最大延迟(s)', '平均延迟(s)',
               '吞吐min(tok/s)', '吞吐max(tok/s)', 'QPS min', 'QPS max', 'TTFT(s)', 'TPOT(s)',
               '输入tok', '输出tok min', '输出tok max']
    
    row = 4
    for ci, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=ci, value=h)
        cell.font = hf
        cell.fill = hfill
        cell.alignment = Alignment(horizontal='center')
        cell.border = border
    
    for gi, g in enumerate(groups):
        m = g['stats']['metrics']
        row = 5 + gi
        values = [
            gi + 1, g['concurrency'],
            g['stats']['total_requests'], g['stats']['failed_requests'],
            round(m.get('min_latency', 0), 3),
            round(m.get('max_latency', 0), 3),
            round(m.get('avg_latency', 0), 3),
            round(m.get('throughput_min', 0), 2),
            round(m.get('throughput_max', 0), 2),
            round(m.get('min_qps', 0), 3),
            round(m.get('max_qps', 0), 3),
            round(m.get('avg_ttft', 0), 3),
            round(m.get('avg_tpot', 0), 4),
            round(m.get('avg_input_tokens', 0)),
            round(m.get('min_output_tokens', 0)),
            round(m.get('max_output_tokens', 0)),
        ]
        for ci, v in enumerate(values, 1):
            cell = ws.cell(row=row, column=ci, value=v)
            cell.border = border
            cell.alignment = Alignment(horizontal='center')
    
    # 列宽
    col_widths = [6, 8, 8, 8, 12, 12, 12, 14, 14, 10, 10, 10, 10, 10, 12, 12]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    
    wb.save(output_path)
    print(f"[OK] Excel 报告已生成: {output_path}")


def generate_compare_excel(groups_a, groups_b, name_a, name_b, model_a, model_b, output_path):
    """生成比对测试 Excel 报告
    
    Args:
        groups_a: 设备A的测试组列表
        groups_b: 设备B的测试组列表
        name_a, name_b: 设备名称
        model_a, model_b: 模型名称
        output_path: 输出路径
    """
    if not HAS_OPENPYXL:
        print("ERROR: 需要 openpyxl。执行 pip install openpyxl 后重试。")
        sys.exit(1)
    
    wb = openpyxl.Workbook()
    green_font = Font(name='微软雅黑', size=10, bold=True, color='10B981')
    border = Border(
        left=Side(style='thin', color='D1D5DB'),
        right=Side(style='thin', color='D1D5DB'),
        top=Side(style='thin', color='D1D5DB'),
        bottom=Side(style='thin', color='D1D5DB'),
    )
    
    # ── Sheet 1: 测试概览 ──
    ws1 = wb.active
    ws1.title = '测试概览'
    ws1.merge_cells('A1:D1')
    ws1['A1'] = f'DeepRunner 6.0 推理性能比对报告'
    ws1['A1'].font = Font(name='微软雅黑', size=16, bold=True)
    
    overview = [
        ('项目', f'{name_a}', f'{name_b}', '说明'),
        ('被测模型', model_a, model_b, ''),
        ('总请求数', sum(g['stats']['total_requests'] for g in groups_a),
         sum(g['stats']['total_requests'] for g in groups_b), ''),
        ('失败数', sum(g['stats']['failed_requests'] for g in groups_a),
         sum(g['stats']['failed_requests'] for g in groups_b), ''),
        ('测试组数', len(groups_a), len(groups_b), ''),
        ('并发范围', f"{groups_a[0]['concurrency']}~{groups_a[-1]['concurrency']}",
         f"{groups_b[0]['concurrency']}~{groups_b[-1]['concurrency']}", ''),
    ]
    for ri, row_data in enumerate(overview):
        for ci, val in enumerate(row_data, 1):
            cell = ws1.cell(row=3+ri, column=ci, value=val)
            cell.border = border
            if ri == 0:
                cell.font = Font(name='微软雅黑', size=10, bold=True)
    ws1.column_dimensions['A'].width = 16
    ws1.column_dimensions['B'].width = 40
    ws1.column_dimensions['C'].width = 40
    ws1.column_dimensions['D'].width = 30
    
    # ── Sheet 2: 逐组对比明细 ──
    ws2 = wb.create_sheet('逐组对比明细')
    ws2.merge_cells('A1:Q1')
    ws2['A1'] = '逐组测试数据对比明细'
    ws2['A1'].font = Font(name='微软雅黑', size=14, bold=True)
    
    hf = Font(name='微软雅黑', size=10, bold=True, color='FFFFFF')
    hfill = PatternFill(start_color='3B82F6', end_color='3B82F6', fill_type='solid')
    
    headers = ['序号', '并发数', '类别', '请求数', '失败数', '最小延迟(s)', '最大延迟(s)', '平均延迟(s)',
               '吞吐min(tok/s)', '吞吐max(tok/s)', 'QPS min', 'QPS max', 'TTFT(s)', 'TPOT(s)',
               '输入tok', '输出tok min', '输出tok max']
    for ci, h in enumerate(headers, 1):
        cell = ws2.cell(row=3, column=ci, value=h)
        cell.font = hf; cell.fill = hfill; cell.border = border
        cell.alignment = Alignment(horizontal='center')
    
    row = 4
    for gi, (ga, gb) in enumerate(zip(groups_a, groups_b)):
        for g, label in [(ga, name_a.split()[0]), (gb, name_b.split()[0])]:
            m = g['stats']['metrics']
            values = [gi+1, g['concurrency'], label,
                      g['stats']['total_requests'], g['stats']['failed_requests'],
                      round(m.get('min_latency', 0), 3), round(m.get('max_latency', 0), 3),
                      round(m.get('avg_latency', 0), 3),
                      round(m.get('throughput_min', 0), 2), round(m.get('throughput_max', 0), 2),
                      round(m.get('min_qps', 0), 3), round(m.get('max_qps', 0), 3),
                      round(m.get('avg_ttft', 0), 3), round(m.get('avg_tpot', 0), 4),
                      round(m.get('avg_input_tokens', 0)),
                      round(m.get('min_output_tokens', 0)), round(m.get('max_output_tokens', 0))]
            for ci, v in enumerate(values, 1):
                cell = ws2.cell(row=row, column=ci, value=v)
                cell.border = border
            row += 1
    
    # ── Sheet 3: 图表数据 ──
    ws3 = wb.create_sheet('图表数据')
    ws3['A1'] = '性能对比图表'
    ws3['A1'].font = Font(name='微软雅黑', size=14, bold=True)
    
    chart_headers = ['组号', '并发数', f'{name_a.split()[0]}-延迟(s)', f'{name_b.split()[0]}-延迟(s)',
                     f'{name_a.split()[0]}-吞吐(tok/s)', f'{name_b.split()[0]}-吞吐(tok/s)',
                     f'{name_a.split()[0]}-TTFT(s)', f'{name_b.split()[0]}-TTFT(s)',
                     f'{name_a.split()[0]}-QPS', f'{name_b.split()[0]}-QPS',
                     f'{name_a.split()[0]}-输出tok', f'{name_b.split()[0]}-输出tok']
    for ci, h in enumerate(chart_headers, 1):
        cell = ws3.cell(row=3, column=ci, value=h)
        cell.font = hf; cell.fill = hfill; cell.border = border
    
    for gi, (ga, gb) in enumerate(zip(groups_a, groups_b)):
        ma, mb = ga['stats']['metrics'], gb['stats']['metrics']
        vals = [gi+1, ga['concurrency'],
                round(ma.get('avg_latency', 0), 3), round(mb.get('avg_latency', 0), 3),
                round(ma.get('throughput_max', 0), 2), round(mb.get('throughput_max', 0), 2),
                round(ma.get('avg_ttft', 0), 3), round(mb.get('avg_ttft', 0), 3),
                round(ma.get('max_qps', 0), 3), round(mb.get('max_qps', 0), 3),
                round(ma.get('min_output_tokens', 0)), round(mb.get('min_output_tokens', 0))]
        for ci, v in enumerate(vals, 1):
            ws3.cell(row=4+gi, column=ci, value=v).border = border
    
    wb.save(output_path)
    print(f"[OK] 比对 Excel 报告已生成: {output_path}")


# ============================================================
#  CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='DeepRunner 6.0 报告生成器')
    parser.add_argument('--mode', required=True, choices=['single', 'compare', 'batch'],
                        help='single=单设备, compare=比对, batch=批量')
    parser.add_argument('--stats-dir', help='单设备: 测试报告目录（含stats.json的子目录）')
    parser.add_argument('--base-dir', help='批量: 扫描的基础目录')
    parser.add_argument('--stats-dir-a', help='比对: 设备A的测试报告目录')
    parser.add_argument('--stats-dir-b', help='比对: 设备B的测试报告目录')
    parser.add_argument('--output-dir', required=True, help='输出目录')
    parser.add_argument('--name-a', default='设备A', help='设备A名称')
    parser.add_argument('--name-b', default='设备B', help='设备B名称')
    parser.add_argument('--model-a', default='未知模型', help='设备A模型名称')
    parser.add_argument('--model-b', default='未知模型', help='设备B模型名称')
    parser.add_argument('--device-a', default='设备A', help='设备A显示名称')
    parser.add_argument('--device-b', default='设备B', help='设备B显示名称')
    parser.add_argument('--format', default='excel', choices=['excel', 'html', 'both'],
                        help='输出格式 (默认excel)')
    
    args = parser.parse_args()
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    if args.mode == 'single':
        groups = scan_test_groups(args.stats_dir)
        print(f"发现 {len(groups)} 组测试数据")
        if args.format in ('excel', 'both'):
            out = os.path.join(args.output_dir, f'debug_performance_{args.device_a}.xlsx')
            generate_single_excel(groups, args.device_a, args.model_a, out)
    
    elif args.mode == 'compare':
        groups_a = scan_test_groups(args.stats_dir_a)
        groups_b = scan_test_groups(args.stats_dir_b)
        print(f"设备A: {len(groups_a)} 组 | 设备B: {len(groups_b)} 组")
        if args.format in ('excel', 'both'):
            out = os.path.join(args.output_dir, f'DeepRunner_推理性能比对报告_{args.device_a}_vs_{args.device_b}.xlsx')
            generate_compare_excel(groups_a, groups_b, args.name_a, args.name_b,
                                   args.model_a, args.model_b, out)
    
    elif args.mode == 'batch':
        groups = scan_test_groups(args.base_dir)
        print(f"发现 {len(groups)} 组测试数据")
        if args.format in ('excel', 'both'):
            out = os.path.join(args.output_dir, f'debug_performance_batch.xlsx')
            generate_single_excel(groups, '批量测试', '未知模型', out)


if __name__ == '__main__':
    main()
