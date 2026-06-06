#!/usr/bin/env python3
"""批量导入文档到 sqlite-graphrag 知识库（集成 markitdown 多格式支持）。

支持的格式（通过 markitdown 自动转换）：
  - 文本类: .txt, .md, .json, .xml, .html, .csv
  - Office: .docx, .xlsx, .xls, .pptx
  - 文档: .pdf, .epub, .msg (Outlook)
  - 笔记: .ipynb (Jupyter Notebook)
  - 媒体: .jpg/.png/.bmp (图片OCR), .mp3/.wav (音频转文字)
  - 压缩: .zip (自动解压处理)

用法:
    # 基本用法（自动识别格式）
    python ingest_documents.py ./docs

    # 指定文件模式
    python ingest_documents.py ./docs --pattern "*.pdf" --recursive

    # 批量导入 Office 文档
    python ingest_documents.py ./reports --pattern "*.docx" --type reference

    # 启用 NER 实体提取
    python ingest_documents.py ./docs --enable-ner --gliner-variant int8

    # 预览（不实际导入）
    python ingest_documents.py ./docs --dry-run
"""

import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
import traceback


def find_binary() -> str:
    """查找 sqlite-graphrag 可执行文件路径。"""
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


def slugify(name: str) -> str:
    """将文件名转为 kebab-case 的记忆名称。"""
    import re
    name = os.path.splitext(name)[0]
    name = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff\s]', '-', name)
    name = re.sub(r'[\s-]+', '-', name)
    name = name.strip('-')
    name = name.lower()
    return name or "untitled"


def get_markitdown():
    """延迟导入 markitdown，避免未安装时报错。"""
    try:
        import markitdown
        return markitdown.MarkItDown()
    except ImportError:
        return None


def convert_with_markitdown(filepath: str) -> str | None:
    """使用 markitdown 将文件转换为 Markdown 文本。

    支持格式: txt, md, json, xml, html, csv, docx, xlsx, xls, pptx,
              pdf, epub, msg, ipynb, 图片(OCR), 音频(转文字), zip
    """
    md = get_markitdown()
    if md is None:
        return None
    try:
        result = md.convert_local(filepath)
        text = result.text_content
        if text and text.strip():
            return text
        return None
    except Exception as e:
        # 记录转换失败但不中断流程
        print(f"    [WARN] markitdown 转换失败: {e}")
        return None


def get_file_extension_patterns() -> dict:
    """返回文件扩展名到描述和是否需 markitdown 转换的映射。"""
    return {
        # 纯文本类（可直接 --body-file）
        ".txt":  {"need_markitdown": False, "desc": "纯文本"},
        ".md":   {"need_markitdown": False, "desc": "Markdown"},
        ".json": {"need_markitdown": False, "desc": "JSON"},
        ".xml":  {"need_markitdown": False, "desc": "XML"},
        # 需 markitdown 转换
        ".html":  {"need_markitdown": True, "desc": "HTML"},
        ".htm":   {"need_markitdown": True, "desc": "HTML"},
        ".csv":   {"need_markitdown": True, "desc": "CSV 表格"},
        ".docx":  {"need_markitdown": True, "desc": "Word 文档"},
        ".xlsx":  {"need_markitdown": True, "desc": "Excel 表格"},
        ".xls":   {"need_markitdown": True, "desc": "Excel 97-2003 表格"},
        ".pptx":  {"need_markitdown": True, "desc": "PPT 演示文稿"},
        ".pdf":   {"need_markitdown": True, "desc": "PDF 文档"},
        ".epub":  {"need_markitdown": True, "desc": "EPUB 电子书"},
        ".msg":   {"need_markitdown": True, "desc": "Outlook 邮件"},
        ".ipynb": {"need_markitdown": True, "desc": "Jupyter Notebook"},
        # 图片（需 OCR）
        ".jpg":  {"need_markitdown": True, "desc": "JPEG 图片"},
        ".jpeg": {"need_markitdown": True, "desc": "JPEG 图片"},
        ".png":  {"need_markitdown": True, "desc": "PNG 图片"},
        ".bmp":  {"need_markitdown": True, "desc": "BMP 图片"},
        ".gif":  {"need_markitdown": True, "desc": "GIF 图片"},
        ".webp": {"need_markitdown": True, "desc": "WebP 图片"},
        ".tiff": {"need_markitdown": True, "desc": "TIFF 图片"},
        ".tif":  {"need_markitdown": True, "desc": "TIFF 图片"},
        # 音频（需转文字）
        ".mp3":  {"need_markitdown": True, "desc": "MP3 音频"},
        ".wav":  {"need_markitdown": True, "desc": "WAV 音频"},
        ".m4a":  {"need_markitdown": True, "desc": "M4A 音频"},
        ".ogg":  {"need_markitdown": True, "desc": "OGG 音频"},
        ".flac": {"need_markitdown": True, "desc": "FLAC 音频"},
        # 压缩包
        ".zip":  {"need_markitdown": True, "desc": "ZIP 压缩包"},
    }


def import_file(binary: str, filepath: str, name: str, memory_type: str,
                 enable_ner: bool, gliner_variant: str, env: dict,
                 use_markitdown: bool) -> dict:
    """导入单个文件到 sqlite-graphrag。"""
    ext = os.path.splitext(filepath)[1].lower()

    if use_markitdown:
        # 使用 markitdown 转换为 Markdown 文本，通过 stdin 传入
        text = convert_with_markitdown(filepath)
        if text is None:
            # markitdown 转换失败，回退到直接读文件
            return import_file(binary, filepath, name, memory_type,
                               enable_ner, gliner_variant, env, use_markitdown=False)

        cmd = [
            "remember", "--name", name,
            "--type", memory_type,
            "--description", f"从 {os.path.basename(filepath)} 导入 ({ext})",
            "--body-stdin",
        ]
        if enable_ner:
            cmd.extend(["--enable-ner", "--gliner-variant", gliner_variant])

        result = subprocess.run(
            [binary] + cmd,
            input=text,
            capture_output=True, text=True, timeout=120, env=env
        )
    else:
        # 纯文本文件，直接使用 --body-file
        cmd = [
            "remember", "--name", name,
            "--type", memory_type,
            "--description", f"从 {os.path.basename(filepath)} 导入",
            "--body-file", filepath,
        ]
        if enable_ner:
            cmd.extend(["--enable-ner", "--gliner-variant", gliner_variant])

        result = subprocess.run(
            [binary] + cmd, capture_output=True, text=True, timeout=120, env=env
        )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main():
    parser = argparse.ArgumentParser(
        description="批量导入文档到 sqlite-graphrag 知识库（支持 20+ 格式）"
    )
    parser.add_argument("dir", help="文档目录路径")
    parser.add_argument("--pattern", default=None,
                        help="文件匹配模式，如 *.txt, *.pdf, *.docx（默认自动识别所有支持格式）")
    parser.add_argument("--recursive", action="store_true",
                        help="递归子目录")
    parser.add_argument("--type", default="document",
                        help="记忆类型（默认 document）")
    parser.add_argument("--enable-ner", action="store_true",
                        help="启用 NER 实体提取")
    parser.add_argument("--gliner-variant", default="int8",
                        choices=["fp32", "fp16", "int8", "q4", "q4f16"],
                        help="GLiNER 模型变体（默认 int8）")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅预览，不实际导入")
    parser.add_argument("--max-files", type=int, default=200,
                        help="最大导入文件数（默认 200）")
    parser.add_argument("--hf-mirror", action="store_true",
                        help="使用 HuggingFace 国内镜像")
    parser.add_argument("--no-markitdown", action="store_true",
                        help="禁用 markitdown 转换（仅导入纯文本格式）")
    args = parser.parse_args()

    # 查找二进制
    binary = find_binary()
    if not binary:
        print("[ERROR] 未找到 sqlite-graphrag。请确保已安装。")
        print("  安装: cargo install sqlite-graphrag --locked --force")
        sys.exit(1)

    # 检查 markitdown
    use_markitdown = False
    if not args.no_markitdown:
        md = get_markitdown()
        if md is not None:
            use_markitdown = True
            print(f"[INFO] markitdown 已就绪，支持 20+ 文件格式转换")
        else:
            print("[INFO] markitdown 未安装，仅支持纯文本格式 (.txt .md .json .xml)")
            print("  安装: pip install markitdown")

    # 环境变量
    env = os.environ.copy()
    if args.hf_mirror:
        env["HF_ENDPOINT"] = "https://hf-mirror.com"

    # 获取扩展名映射
    ext_map = get_file_extension_patterns()

    # 收集文件
    all_files = []
    search_pattern = "**/*" if args.recursive else "*"

    for f in glob.glob(os.path.join(args.dir, search_pattern), recursive=args.recursive):
        if not os.path.isfile(f):
            continue

        ext = os.path.splitext(f)[1].lower()

        # 如果指定了 pattern，按 pattern 过滤
        if args.pattern:
            if glob.fnmatch.fnmatch(os.path.basename(f), args.pattern):
                all_files.append(f)
            continue

        # 未指定 pattern：自动识别支持的格式
        if ext in ext_map:
            info = ext_map[ext]
            if info["need_markitdown"] and not use_markitdown:
                continue  # 需要 markitdown 但未安装，跳过
            all_files.append(f)

    if not all_files:
        if args.pattern:
            print(f"[INFO] 在 '{args.dir}' 中未找到匹配 '{args.pattern}' 的文件")
        else:
            print(f"[INFO] 在 '{args.dir}' 中未找到支持的文档文件")
            print("  支持的格式:", ", ".join(sorted(ext_map.keys())))
        sys.exit(0)

    # 限制数量
    files_to_process = all_files[:args.max_files]
    if len(all_files) > args.max_files:
        print(f"[WARN] 找到 {len(all_files)} 个文件，仅处理前 {args.max_files} 个（使用 --max-files 调整）")

    # 按扩展名分组统计
    ext_counts = {}
    for f in files_to_process:
        ext = os.path.splitext(f)[1].lower()
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    print(f"找到 {len(files_to_process)} 个文件待导入:")
    for ext, count in sorted(ext_counts.items()):
        info = ext_map.get(ext, {"desc": ext})
        desc = info["desc"]
        print(f"  .{ext.lstrip('.'):<8} {count:>4} 个  ({desc})")

    if args.dry_run:
        print("\n--- 预览 ---")
        for f in files_to_process:
            name = slugify(os.path.basename(f))
            size = os.path.getsize(f)
            ext = os.path.splitext(f)[1].lower()
            info = ext_map.get(ext, {"desc": ext})
            need_md = info.get("need_markitdown", False)
            flag = " [markitdown]" if need_md else ""
            print(f"  [{name}] <- {f} ({size/1024:.1f} KB){flag}")
        print(f"\n共 {len(files_to_process)} 个文件（预览模式，未实际导入）")
        sys.exit(0)

    # 逐个导入
    success = 0
    failed = 0
    skipped = 0

    for i, filepath in enumerate(files_to_process):
        basename = os.path.basename(filepath)
        name = slugify(basename)
        relpath = os.path.relpath(filepath, args.dir)
        ext = os.path.splitext(filepath)[1].lower()
        info = ext_map.get(ext, {"need_markitdown": False, "desc": ext})
        need_md = info.get("need_markitdown", False)

        print(f"[{i+1}/{len(files_to_process)}] {relpath} -> [{name}]", end=" ")

        try:
            result = import_file(
                binary, filepath, name, args.type,
                args.enable_ner, args.gliner_variant, env,
                use_markitdown=(need_md and use_markitdown)
            )

            if result["returncode"] == 0:
                data = json.loads(result["stdout"])
                success += 1
                print(f"OK (id={data['memory_id']}, {data['elapsed_ms']}ms)")
            else:
                err = (result["stderr"] or result["stdout"])[:200]
                # 如果是因为 body 为空跳过
                if "empty" in err.lower() or "no content" in err.lower():
                    skipped += 1
                    print(f"SKIP (空内容)")
                else:
                    failed += 1
                    print(f"FAIL: {err}")
        except subprocess.TimeoutExpired:
            failed += 1
            print(f"FAIL: 超时 (>120s)")
        except Exception as e:
            failed += 1
            print(f"FAIL: {e}")

    print(f"\n{'='*50}")
    print(f"导入完成: {success} 成功, {failed} 失败, {skipped} 跳过")
    print(f"数据库: graphrag.sqlite（当前目录）")


if __name__ == "__main__":
    main()
