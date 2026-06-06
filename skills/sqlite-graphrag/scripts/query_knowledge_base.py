#!/usr/bin/env python3
"""交互式查询 sqlite-graphrag 知识库。

支持语义检索、混合检索、图谱查询、精确读取。

用法:
    python query_knowledge_base.py                          # 交互模式
    python query_knowledge_base.py recall "关键词" --k 5    # 直接查询
    python query_knowledge_base.py hybrid "关键词" --k 5
    python query_knowledge_base.py graph
    python query_knowledge_base.py stats
"""

import argparse
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


def cmd_recall(binary: str, args: argparse.Namespace):
    cmd = ["recall", args.query, "--k", str(args.k), "--json"]
    if args.max_hops:
        cmd.extend(["--max-hops", str(args.max_hops)])
    if args.mtype:
        cmd.extend(["--type", args.mtype])
    data = run(binary, cmd)
    if isinstance(data, dict) and "results" in data:
        print(f"查询: \"{data['query']}\"")
        print(f"结果: {len(data['results'])} 条 (耗时 {data.get('elapsed_ms', '?')}ms)\n")
        for i, r in enumerate(data["results"], 1):
            print(f"  [{i}] {r['name']} (score={r['score']:.4f})")
            print(f"      类型: {r.get('type', '?')}")
            print(f"      描述: {r.get('description', '')[:80]}")
            print(f"      片段: {r['snippet'][:100]}...")
            print()
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_hybrid(binary: str, args: argparse.Namespace):
    cmd = ["hybrid-search", args.query, "--k", str(args.k), "--json"]
    data = run(binary, cmd)
    if isinstance(data, dict) and "results" in data:
        print(f"混合检索: \"{data['query']}\"")
        print(f"结果: {len(data['results'])} 条 (耗时 {data.get('elapsed_ms', '?')}ms)\n")
        for i, r in enumerate(data["results"], 1):
            print(f"  [{i}] {r['name']} (score={r.get('normalized_score', r['score']):.4f})")
            print(f"      片段: {r['snippet'][:120]}...")
            print()
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_graph(binary: str, args: argparse.Namespace):
    fmt = args.format or "json"
    cmd = ["graph", "--format", fmt]
    if fmt == "dot" and args.output:
        cmd.extend(["--output", args.output])
    data = run(binary, cmd)
    if isinstance(data, dict):
        nodes = data.get("nodes", data.get("entities", []))
        edges = data.get("edges", [])
        print(f"图谱: {len(nodes)} 节点, {len(edges)} 边")
        if nodes:
            print("\n节点:")
            for n in nodes[:20]:
                print(f"  - {n.get('name', n.get('id', '?'))} ({n.get('entity_type', n.get('type', '?'))})")
        if edges:
            print("\n边:")
            for e in edges[:20]:
                print(f"  - {e.get('source', '?')} --[{e.get('relation', e.get('label', '?'))}]--> {e.get('target', '?')}")
    else:
        print(data)


def cmd_stats(binary: str, args: argparse.Namespace):
    data = run(binary, ["stats", "--json"])
    if isinstance(data, dict):
        print("知识库统计:")
        print(f"  记忆数: {data.get('memories', 0)}")
        print(f"  实体数: {data.get('entities', 0)}")
        print(f"  关系数: {data.get('relationships', 0)}")
        print(f"  数据库大小: {data.get('db_size_bytes', 0) / 1024 / 1024:.1f} MB")
        print(f"  Schema 版本: {data.get('schema_version', '?')}")
    else:
        print(data)


def cmd_read(binary: str, args: argparse.Namespace):
    if args.name:
        cmd = ["read", "--name", args.name, "--json"]
    elif args.id:
        cmd = ["read", "--id", str(args.id), "--json"]
    else:
        print("[ERROR] 请指定 --name 或 --id")
        return
    data = run(binary, cmd)
    if isinstance(data, dict) and "body" in data:
        print(f"名称: {data['name']}")
        print(f"类型: {data.get('type', data.get('memory_type', '?'))}")
        print(f"描述: {data.get('description', '')}")
        print(f"版本: {data.get('version', 1)}")
        print(f"正文:\n{data['body']}")
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))


def interactive(binary: str):
    print("sqlite-graphrag 交互查询工具")
    print("=" * 40)
    print("可用命令:")
    print("  recall <关键词>  -- 语义检索")
    print("  hybrid <关键词>  -- 混合检索")
    print("  graph            -- 查看图谱")
    print("  stats            -- 查看统计")
    print("  read <名称>      -- 读取记忆")
    print("  list             -- 列出记忆")
    print("  help             -- 帮助")
    print("  quit             -- 退出")
    print()

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue
        if line in ("quit", "exit", "q"):
            break
        if line == "help":
            print("可用命令: recall, hybrid, graph, stats, read, list, help, quit")
            continue

        parts = line.split(maxsplit=1)
        cmd = parts[0]
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "recall" and arg:
            data = run(binary, ["recall", arg, "--k", "5", "--json"])
            if isinstance(data, dict) and "results" in data:
                for r in data["results"]:
                    print(f"  [{r['name']}] score={r['score']:.4f}")
                    print(f"    {r['snippet'][:100]}")
                    print()
            else:
                print(json.dumps(data, indent=2, ensure_ascii=False))
        elif cmd == "hybrid" and arg:
            data = run(binary, ["hybrid-search", arg, "--k", "5", "--json"])
            if isinstance(data, dict) and "results" in data:
                for r in data["results"]:
                    print(f"  [{r['name']}] score={r.get('normalized_score', r['score']):.4f}")
                    print(f"    {r['snippet'][:100]}")
                    print()
            else:
                print(json.dumps(data, indent=2, ensure_ascii=False))
        elif cmd == "graph":
            data = run(binary, ["graph", "--format", "json"])
            if isinstance(data, dict):
                nodes = data.get("nodes", data.get("entities", []))
                edges = data.get("edges", [])
                print(f"节点: {len(nodes)}, 边: {len(edges)}")
                for n in nodes[:10]:
                    print(f"  {n.get('name', '?')} ({n.get('entity_type', '?')})")
                for e in edges[:10]:
                    print(f"  {e.get('source', '?')} -> {e.get('target', '?')} [{e.get('relation', '?')}]")
            else:
                print(data)
        elif cmd == "stats":
            cmd_stats(binary, argparse.Namespace())
        elif cmd == "read" and arg:
            data = run(binary, ["read", "--name", arg, "--json"])
            if isinstance(data, dict) and "body" in data:
                print(f"描述: {data.get('description', '')}")
                print(f"正文: {data['body'][:500]}")
            else:
                print(json.dumps(data, indent=2, ensure_ascii=False))
        elif cmd == "list":
            data = run(binary, ["list", "--json"])
            if isinstance(data, dict) and "items" in data:
                for item in data["items"]:
                    print(f"  [{item['memory_id']}] {item['name']} ({item['type']})")
            else:
                print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print("未知命令。输入 help 查看帮助。")


def main():
    parser = argparse.ArgumentParser(description="查询 sqlite-graphrag 知识库")
    sub = parser.add_subparsers(dest="command")

    # recall
    p_recall = sub.add_parser("recall", help="语义检索")
    p_recall.add_argument("query", help="查询关键词")
    p_recall.add_argument("--k", type=int, default=5, help="返回结果数")
    p_recall.add_argument("--max-hops", type=int, help="图谱多跳深度")
    p_recall.add_argument("--type", dest="mtype", help="按类型过滤")

    # hybrid
    p_hybrid = sub.add_parser("hybrid", help="混合检索")
    p_hybrid.add_argument("query", help="查询关键词")
    p_hybrid.add_argument("--k", type=int, default=5, help="返回结果数")

    # graph
    p_graph = sub.add_parser("graph", help="查看图谱")
    p_graph.add_argument("--format", choices=["json", "dot", "mermaid"], default="json")
    p_graph.add_argument("--output", help="输出文件路径（仅 dot 格式）")

    # stats
    sub.add_parser("stats", help="查看统计")

    # read
    p_read = sub.add_parser("read", help="读取记忆")
    p_read.add_argument("--name", help="记忆名称")
    p_read.add_argument("--id", type=int, help="记忆 ID")

    args = parser.parse_args()

    binary = find_binary()
    if not binary:
        print("[ERROR] 未找到 sqlite-graphrag")
        sys.exit(1)

    if args.command == "recall":
        cmd_recall(binary, args)
    elif args.command == "hybrid":
        cmd_hybrid(binary, args)
    elif args.command == "graph":
        cmd_graph(binary, args)
    elif args.command == "stats":
        cmd_stats(binary, args)
    elif args.command == "read":
        cmd_read(binary, args)
    else:
        interactive(binary)


if __name__ == "__main__":
    main()
