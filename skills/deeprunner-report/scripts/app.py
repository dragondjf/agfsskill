#!/usr/bin/env python3
"""
DeepRunner 6.0 报告生成器 - HTTP 接口层
薄层封装，所有业务逻辑委托给 deeprunner-report skill 的 generate_report.py
"""
import os
import sys
import json
import threading
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_file

# ── 技能脚本（唯一业务逻辑来源） ──
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
from generate_report import (
    auto_scan_and_generate, discover_and_generate, discover_devices_flat,
    _auto_detect,
)

app = Flask(__name__)

# ── 自定义 JSON 编码器（自动将 Path 对象转为字符串） ──
from flask.json.provider import DefaultJSONProvider
class _PathAwareProvider(DefaultJSONProvider):
    def default(self, o):
        if isinstance(o, Path):
            return str(o)
        return super().default(o)
app.json = _PathAwareProvider(app)

app.secret_key = "deeprunner-auto-2026"
app.config['OUTPUT_DIR'] = os.path.join(SKILL_DIR, 'output')
os.makedirs(app.config['OUTPUT_DIR'], exist_ok=True)

_tasks = {}
_file_registry = {}  # filename -> full_path

@app.route('/')
def index():
    _web_ui = os.path.join(SKILL_DIR, 'assets', 'web-ui.html')
    if os.path.isfile(_web_ui):
        with open(_web_ui, 'r', encoding='utf-8') as _f:
            return _f.read(), 200, {'Content-Type': 'text/html; charset=utf-8'}
    return '<html><body><h1>DeepRunner 6.0</h1><p>Web UI 未安装</p></body></html>'

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = '*'
    response.headers['Access-Control-Allow-Methods'] = '*'
    return response

# ── API: 自动扫描 ──
@app.route('/api/auto-scan', methods=['POST'])
def api_auto_scan():
    data = request.get_json() or {}
    base_dir = data.get('path', '')
    if not base_dir or not os.path.isdir(base_dir):
        return jsonify({'ok': False, 'error': '目录不存在或无法访问'})
    try:
        result = _auto_detect(base_dir)
        result['ok'] = True
        return jsonify(result)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

# ── API: 发现模式 ──
@app.route('/api/discover', methods=['POST'])
def api_discover():
    data = request.get_json() or {}
    root_dir = data.get('path', '')
    if not root_dir or not os.path.isdir(root_dir):
        return jsonify({'ok': False, 'error': '目录不存在或无法访问'})
    try:
        devices = discover_devices_flat(root_dir, with_preview=True)
        return jsonify({'ok': True, 'devices': devices})
    except Exception as e:
        import traceback
        return jsonify({'ok': False, 'error': f"{type(e).__name__}: {e}\n{traceback.format_exc()}"})

# ── API: 自动生成报告（异步） ──
@app.route('/api/auto-generate', methods=['POST'])
def api_auto_generate():
    data = request.get_json() or {}
    task_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    _tasks[task_id] = {'status': 'running', 'progress': 0, 'files': []}

    output_dir = data.get('base_dir', '').rstrip('/\\') or app.config['OUTPUT_DIR']
    os.makedirs(output_dir, exist_ok=True)

    def _run():
        try:
            _tasks[task_id]['progress'] = 5
            _tasks[task_id]['message'] = '正在扫描数据...'
            result = auto_scan_and_generate(
                base_dir=data.get('base_dir', ''),
                output_dir=output_dir,
                formats=data.get('formats', ['excel', 'html']),
                per_concurrency=data.get('per_concurrency', False),
                device_name=data.get('device_name'),
                model_name=data.get('model_name'),
                device_a=data.get('device_a'),
                device_b=data.get('device_b'),
                model_a=data.get('model_a'),
                model_b=data.get('model_b'),
                dir_a=data.get('dir_a'),
                dir_b=data.get('dir_b'),
            )
            if result.get('ok'):
                _tasks[task_id]['status'] = 'completed'
                _tasks[task_id]['progress'] = 100
                _tasks[task_id]['files'] = result['files']
                _tasks[task_id]['message'] = result.get('message', '报告生成完成！')
                for f in result['files']:
                    _file_registry[f['name']] = f['path']
            else:
                _tasks[task_id]['status'] = 'failed'
                _tasks[task_id]['error'] = result.get('error', '未知错误')
        except Exception as e:
            import traceback
            _tasks[task_id]['status'] = 'failed'
            _tasks[task_id]['error'] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({'ok': True, 'task_id': task_id})

# ── API: 批量发现并生成（异步） ──
@app.route('/api/discover-generate', methods=['POST'])
def api_discover_generate():
    data = request.get_json() or {}
    task_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    _tasks[task_id] = {'status': 'running', 'progress': 0, 'files': []}

    output_dir = data.get('path', '').rstrip('/\\') or app.config['OUTPUT_DIR']
    os.makedirs(output_dir, exist_ok=True)

    def _run():
        try:
            _tasks[task_id]['progress'] = 5
            result = discover_and_generate(
                root_dir=data.get('path', ''),
                output_dir=output_dir,
                formats=data.get('formats', ['excel', 'html']),
            )
            _tasks[task_id]['status'] = 'completed'
            _tasks[task_id]['progress'] = 100
            _tasks[task_id]['files'] = result.get('files', [])
            _tasks[task_id]['message'] = result.get('message', '完成')
            for f in result.get('files', []):
                _file_registry[f['name']] = f['path']
        except Exception as e:
            import traceback
            _tasks[task_id]['status'] = 'failed'
            _tasks[task_id]['error'] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({'ok': True, 'task_id': task_id})

# ── API: 任务状态 ──
@app.route('/api/task/<task_id>')
def api_task_status(task_id):
    task = _tasks.get(task_id)
    if not task:
        return jsonify({'ok': False, 'error': '任务不存在'})
    return jsonify({
        'ok': True,
        'status': task['status'],
        'progress': task.get('progress', 0),
        'message': task.get('message', ''),
        'files': task.get('files', []),
        'error': task.get('error', ''),
    })

# ── API: 下载/预览 ──
@app.route('/api/download/<path:filename>')
def api_download(filename):
    filepath = _file_registry.get(filename) or os.path.join(app.config['OUTPUT_DIR'], filename)
    if not os.path.exists(filepath):
        return jsonify({'ok': False, 'error': '文件不存在'})
    return send_file(filepath, as_attachment=True)

@app.route('/assets/<path:filename>')
def api_assets(filename):
    filepath = os.path.join(SKILL_DIR, 'assets', filename)
    if not os.path.exists(filepath):
        return '文件不存在', 404
    ext = os.path.splitext(filename)[1].lower()
    mime_map = {'.css': 'text/css', '.js': 'application/javascript', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.svg': 'image/svg+xml', '.png': 'image/png'}
    ct = mime_map.get(ext, 'application/octet-stream')
    with open(filepath, 'rb') as f:
        return f.read(), 200, {'Content-Type': ct}

@app.route('/api/preview/<path:filename>')
def api_preview(filename):
    filepath = _file_registry.get(filename) or os.path.join(app.config['OUTPUT_DIR'], filename)
    if not os.path.exists(filepath):
        return '文件不存在', 404
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
    # 替换相对 assets 路径为绝对路径（通过 /api/preview/ 访问时 assets/ 解析为 /api/preview/assets/ 导致404）
    html = html.replace('src="assets/', 'src="/assets/')
    html = html.replace('href="assets/', 'href="/assets/')
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}

if __name__ == '__main__':
    print(f"* DeepRunner 报告生成器 (HTTP 接口层)")
    print(f"* 技能目录: {SKILL_DIR}")
    print(f"* 输出目录: {app.config['OUTPUT_DIR']}")
    print(f"* 访问地址: http://127.0.0.1:8866")
    app.run(host='127.0.0.1', port=8866, debug=True, threaded=True)
