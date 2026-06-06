#!/usr/bin/env python3
"""一键初始化 sqlite-graphrag 知识库。

用法:
    python init_knowledge_base.py [--db-dir <目录>] [--hf-mirror]

自动完成：
  1. 检查 sqlite-graphrag 二进制是否可用
  2. 初始化数据库（init）
  3. 检查数据库健康状态
  4. 写入一条示例记忆
  5. 验证语义检索
"""

import argparse
import json
import os
import subprocess
import sys


def find_binary() -> str:
    """查找 sqlite-graphrag 可执行文件路径。"""
    # 常见位置
    candidates = [
        "sqlite-graphrag",
        "sqlite-graphrag.exe",
        os.path.expanduser("~/.cargo/bin/sqlite-graphrag"),
        os.path.expanduser("~/.cargo/bin/sqlite-graphrag.exe"),
    ]
    # 当前目录及父目录
    for d in [".", ".."]:
        for f in ["sqlite-graphrag", "sqlite-graphrag.exe"]:
            candidates.append(os.path.join(d, f))

    for cmd in candidates:
        try:
            result = subprocess.run(
                [cmd, "--version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # 尝试用 where/which 查找
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["where", "sqlite-graphrag"], capture_output=True, text=True, timeout=10
            )
        else:
            result = subprocess.run(
                ["which", "sqlite-graphrag"], capture_output=True, text=True, timeout=10
            )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
    except FileNotFoundError:
        pass

    return ""


def run_sqlite_graphrag(binary: str, args: list[str], timeout: int = 120,
                        env: dict | None = None) -> subprocess.CompletedProcess:
    """运行 sqlite-graphrag 命令。"""
    return subprocess.run(
        [binary] + args, capture_output=True, text=True, timeout=timeout, env=env
    )


def main():
    parser = argparse.ArgumentParser(description="一键初始化 sqlite-graphrag 知识库")
    parser.add_argument("--db-dir", default=".",
                        help="数据库存放目录（默认当前目录）")
    parser.add_argument("--hf-mirror", action="store_true",
                        help="使用 HuggingFace 国内镜像 (hf-mirror.com)")
    args = parser.parse_args()

    db_dir = os.path.abspath(args.db_dir)
    os.makedirs(db_dir, exist_ok=True)
    os.chdir(db_dir)

    # 环境变量
    env = os.environ.copy()
    if args.hf_mirror:
        env["HF_ENDPOINT"] = "https://hf-mirror.com"
        print("[INFO] 使用 HF 镜像: https://hf-mirror.com")

    # 1. 检查二进制
    print("\n[1/5] 检查 sqlite-graphrag 二进制...")
    binary = find_binary()
    if not binary:
        print("[ERROR] 未找到 sqlite-graphrag。请确保已安装并在 PATH 中。")
        print("  安装方式: cargo install sqlite-graphrag --locked --force")
        print("  或下载预编译二进制: https://github.com/daniloaguiarbr/sqlite-graphrag/releases")
        sys.exit(1)
    result = run_sqlite_graphrag(binary, ["--version"])
    print(f"  找到: {binary}")
    print(f"  版本: {result.stdout.strip()}")

    # 2. 初始化
    print("\n[2/5] 初始化数据库...")
    result = run_sqlite_graphrag(binary, ["init"], timeout=600, env=env)
    if result.returncode != 0:
        print(f"[ERROR] 初始化失败: {result.stderr}")
        print("  提示: 如果网络问题，尝试添加 --hf-mirror 参数")
        sys.exit(1)
    data = json.loads(result.stdout)
    print(f"  数据库: {data['db_path']}")
    print(f"  Schema 版本: {data['schema_version']}")
    print(f"  嵌入模型: {data['model']} ({data['dim']}维)")

    # 3. 健康检查
    print("\n[3/5] 健康检查...")
    result = run_sqlite_graphrag(binary, ["health", "--json"])
    data = json.loads(result.stdout)
    checks_ok = all(c["ok"] for c in data.get("checks", []))
    print(f"  完整性: {'OK' if data.get('integrity_ok') else 'FAILED'}")
    print(f"  FTS5: {'OK' if data.get('fts_ok') else 'FAILED'}")
    print(f"  向量索引: {'OK' if data.get('vec_memories_ok') else 'FAILED'}")
    if not checks_ok:
        print("[WARN] 部分检查未通过，详见 health 输出")

    # 4. 写入示例记忆
    print("\n[4/5] 写入示例记忆...")
    result = run_sqlite_graphrag(binary, [
        "remember", "--name", "welcome-message", "--type", "note",
        "--description", "欢迎使用 sqlite-graphrag 知识库",
        "--body", (
            "sqlite-graphrag 是一个基于 Rust 的单文件 GraphRAG 引擎。"
            "它将知识图谱存储和文本向量计算全部内嵌到 SQLite 数据库中。"
            "支持语义检索、混合搜索（向量+全文）和多跳图谱推理。"
            "适用于构建本地私有 AI 知识库。"
        ),
    ], env=env)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        print(f"  记忆 ID: {data['memory_id']}")
        print(f"  名称: {data['name']}")
        print(f"  耗时: {data['elapsed_ms']}ms")
    else:
        print(f"[WARN] 写入示例记忆失败: {result.stderr}")

    # 5. 验证检索
    print("\n[5/5] 验证语义检索...")
    result = run_sqlite_graphrag(binary, [
        "recall", "GraphRAG", "--k", "3", "--json",
    ], env=env)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        count = len(data.get("results", []))
        print(f"  检索到 {count} 条结果")
        for r in data.get("results", []):
            print(f"    - [{r['name']}] score={r['score']:.4f}: {r['snippet'][:60]}...")
    else:
        print(f"[WARN] 检索验证失败: {result.stderr}")

    # 统计
    result = run_sqlite_graphrag(binary, ["stats", "--json"])
    data = json.loads(result.stdout)
    db_path = os.path.join(db_dir, "graphrag.sqlite")
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    print(f"\n{'='*50}")
    print("初始化完成！")
    print(f"{'='*50}")
    print(f"  数据库: {db_path}")
    print(f"  大小: {db_size / 1024 / 1024:.1f} MB")
    print(f"  记忆数: {data.get('memories', 0)}")
    print(f"  实体数: {data.get('entities', 0)}")
    print(f"  关系数: {data.get('relationships', 0)}")
    print(f"\n常用命令:")
    print(f"  sqlite-graphrag recall \"关键词\" --k 5 --json")
    print(f"  sqlite-graphrag list --json")
    print(f"  sqlite-graphrag stats --json")


if __name__ == "__main__":
    main()
