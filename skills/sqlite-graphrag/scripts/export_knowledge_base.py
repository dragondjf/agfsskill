#!/usr/bin/env python3
"""导出 sqlite-graphrag 知识库内容。

支持格式: JSON, CSV, Markdown

用法:
    python export_knowledge_base.py --format json --output export.json
    python export_knowledge_base.py --format csv --output memories.csv
    python export_knowledge_base.py --format markdown --output knowledge_base.md
"""

import argparse
import csv
import json
import os
import subprocess
import sys


def find_binary() -> str:
    candidates = [
        "sqlite-graphrag",
        "sqlite-graphrag.exe",
        os.path.expanduser("~/.cargo/bin/sqlite-graphrag"),
        os.path.expanduser("~/.cargo/bin/sqlite-graphrag.exe"),
    ]
    for cmd in candidates:
        try:
            result = subprocess.run(
                [cmd, "--version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return ""


def run(binary: str, args: list[str], timeout: int = 120) -> dict | str:
    result = subprocess.run(
        [binary] + args, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        return {"error": True, "message": result.stderr or result.stdout}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout


def export_json(binary: str, output: str):
    """导出为 JSON 格式。"""
    data = run(binary, ["list", "--json"])
    if not isinstance(data, dict) or "items" not in data:
        print(f"[ERROR] 获取记忆列表失败: {data}")
        return False

    memories = data["items"]
    # 逐条读取完整内容
    full_memories = []
    for m in memories:
        detail = run(binary, ["read", "--name", m["name"], "--json"])
        if isinstance(detail, dict) and "body" in detail:
            full_memories.append(detail)
        else:
            full_memories.append(m)

    # 获取图谱
    graph = run(binary, ["graph", "--format", "json"])
    if not isinstance(graph, dict):
        graph = {"nodes": [], "edges": []}

    # 获取统计
    stats = run(binary, ["stats", "--json"])
    if not isinstance(stats, dict):
        stats = {}

    export = {
        "exported_at": None,
        "stats": stats,
        "memories": full_memories,
        "graph": graph,
    }

    with open(output, "w", encoding="utf-8") as f:
        json.dump(export, f, indent=2, ensure_ascii=False)
    return True


def export_csv(binary: str, output: str):
    """导出为 CSV 格式。"""
    data = run(binary, ["list", "--json"])
    if not isinstance(data, dict) or "items" not in data:
        print(f"[ERROR] 获取记忆列表失败: {data}")
        return False

    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["memory_id", "name", "type", "description", "body", "updated_at"])

        for m in data["items"]:
            detail = run(binary, ["read", "--name", m["name"], "--json"])
            body = detail.get("body", "") if isinstance(detail, dict) else ""
            writer.writerow([
                m.get("memory_id", m.get("id", "")),
                m["name"],
                m.get("type", m.get("memory_type", "")),
                m.get("description", ""),
                body,
                m.get("updated_at_iso", ""),
            ])
    return True


def export_markdown(binary: str, output: str):
    """导出为 Markdown 格式。"""
    data = run(binary, ["list", "--json"])
    if not isinstance(data, dict) or "items" not in data:
        print(f"[ERROR] 获取记忆列表失败: {data}")
        return False

    stats = run(binary, ["stats", "--json"])
    stats_text = ""
    if isinstance(stats, dict):
        stats_text = (
            f"## 知识库统计\n\n"
            f"- 记忆数: {stats.get('memories', 0)}\n"
            f"- 实体数: {stats.get('entities', 0)}\n"
            f"- 关系数: {stats.get('relationships', 0)}\n"
            f"- 数据库大小: {stats.get('db_size_bytes', 0) / 1024 / 1024:.1f} MB\n\n"
        )

    lines = [
        "# sqlite-graphrag 知识库导出\n",
        stats_text,
        "## 记忆列表\n",
    ]

    for m in data["items"]:
        detail = run(binary, ["read", "--name", m["name"], "--json"])
        body = detail.get("body", "") if isinstance(detail, dict) else ""
        lines.append(f"### {m['name']}\n")
        lines.append(f"- **ID**: {m.get('memory_id', m.get('id', ''))}")
        lines.append(f"- **类型**: {m.get('type', m.get('memory_type', ''))}")
        lines.append(f"- **描述**: {m.get('description', '')}")
        lines.append(f"- **更新时间**: {m.get('updated_at_iso', '')}")
        lines.append("")
        lines.append("**正文**:")
        lines.append("")
        lines.append(body)
        lines.append("")
        lines.append("---")
        lines.append("")

    with open(output, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return True


def main():
    parser = argparse.ArgumentParser(description="导出 sqlite-graphrag 知识库")
    parser.add_argument("--format", choices=["json", "csv", "markdown"],
                        default="json", help="导出格式")
    parser.add_argument("--output", "-o", default="knowledge_base_export",
                        help="输出文件路径（不含扩展名）")
    args = parser.parse_args()

    binary = find_binary()
    if not binary:
        print("[ERROR] 未找到 sqlite-graphrag")
        sys.exit(1)

    ext_map = {"json": ".json", "csv": ".csv", "markdown": ".md"}
    output_path = args.output
    if not output_path.endswith(ext_map[args.format]):
        output_path += ext_map[args.format]

    print(f"导出知识库到: {output_path}")

    if args.format == "json":
        ok = export_json(binary, output_path)
    elif args.format == "csv":
        ok = export_csv(binary, output_path)
    elif args.format == "markdown":
        ok = export_markdown(binary, output_path)

    if ok:
        size = os.path.getsize(output_path)
        print(f"导出完成: {size / 1024:.1f} KB")
    else:
        print("[ERROR] 导出失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
