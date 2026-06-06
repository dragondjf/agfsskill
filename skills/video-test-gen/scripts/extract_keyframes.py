#!/usr/bin/env python3
"""
关键帧提取脚本 - 从操作视频中提取界面变化的关键帧

核心算法: 帧间 SSIM（结构相似性）比较，低于阈值时判定为场景变化并保存。
内置速度优化: 降采样（sample_every）+ 缩放到小尺寸再计算 SSIM，
原始帧仍以全分辨率保存。

用法:
    # 高效模式（推荐，默认参数）
    python extract_keyframes.py <video_path> <output_dir> --filter-interval 5

    # 精细模式（更多帧、更敏感）
    python extract_keyframes.py <video_path> <output_dir> \
        --threshold 0.95 --sample-every 3 --resize 480

参数说明:
    --threshold      SSIM 阈值，越大越严格（0.98 仅保留剧烈变化，0.85 保留较多变化），默认 0.90
    --sample-every   每隔 N 帧采样一次用于比较，降低计算量，默认 5（即只比较 1/5 的帧）
    --resize         计算 SSIM 时将帧缩放到该宽度（等比缩放），0 表示不缩放，默认 320
    --filter-interval 二次筛选：提取后按时间间隔（秒）取代表帧，0 表示不筛选，默认 0

依赖: pip install opencv-python scikit-image
"""

import os
import sys
import json
import argparse
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim


def extract_keyframes(video_path, output_dir, similarity_threshold=0.90,
                      sample_every=5, resize_width=320):
    """
    从视频中提取界面变化的关键帧

    Args:
        video_path:            视频文件路径
        output_dir:            关键帧输出目录
        similarity_threshold:  SSIM 阈值 (0~1)，低于此值判定为场景变化
        sample_every:          每隔 N 帧采样一次进行比较，其余帧跳过
        resize_width:          计算 SSIM 时缩放的目标宽度，0 = 不缩放

    Returns:
        frame_info: [[图片路径, 时间戳], ...] 列表
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频文件: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps > 0 else 0

    print(f"视频信息: {video_path}")
    print(f"  分辨率: {orig_w}x{orig_h}, 帧率: {fps:.2f} FPS, 总帧数: {total_frames}, 时长: {duration:.1f}s")
    print(f"  参数: threshold={similarity_threshold}, sample_every={sample_every}, resize={resize_width}")

    # 计算缩放尺寸（等比）
    if resize_width > 0 and orig_w > resize_width:
        scale = resize_width / orig_w
        compare_w = resize_width
        compare_h = int(orig_h * scale)
    else:
        compare_w, compare_h = orig_w, orig_h

    frame_info = []
    prev_gray = None
    saved_count = 0
    frame_idx = 0
    compared_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 降采样：只对每隔 sample_every 帧进行比较
        if frame_idx % sample_every != 0:
            frame_idx += 1
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if prev_gray is None:
            # 第一帧始终保存
            prev_gray = gray
            timestamp = frame_idx / fps
            filepath = os.path.join(output_dir, f"key_{saved_count:05d}_{timestamp:.1f}s.jpg")
            cv2.imwrite(filepath, frame)
            frame_info.append([filepath, round(timestamp, 2)])
            saved_count += 1
        else:
            # 缩放后再比较（加速）
            if resize_width > 0:
                gray_resized = cv2.resize(gray, (compare_w, compare_h))
            else:
                gray_resized = gray

            h, w = prev_gray.shape
            gh, gw = gray_resized.shape
            if h != gh or w != gw:
                gray_resized = cv2.resize(gray_resized, (w, h))

            score = ssim(prev_gray, gray_resized)
            compared_count += 1

            if score < similarity_threshold:
                prev_gray = gray_resized
                timestamp = frame_idx / fps
                filepath = os.path.join(output_dir, f"key_{saved_count:05d}_{timestamp:.1f}s.jpg")
                cv2.imwrite(filepath, frame)  # 保存原始分辨率
                frame_info.append([filepath, round(timestamp, 2)])
                saved_count += 1

        frame_idx += 1

        # 进度提示（每 200 比较帧输出一次）
        if compared_count > 0 and compared_count % 200 == 0:
            elapsed = frame_idx / fps
            print(f"  进度: {elapsed:.1f}s / {duration:.1f}s, 已提取 {saved_count} 帧")

    cap.release()
    print(f"完成: 共提取 {saved_count} 个关键帧 (比较了 {compared_count} 帧, 处理了 {frame_idx} 帧)")
    return frame_info


def filter_frames_by_interval(frame_info, interval_seconds=5.0):
    """
    二次筛选：按时间间隔选取代表帧，减少冗余

    当关键帧过多（如 >50）时，可调用此函数按固定间隔采样。
    典型用法：每 5 秒取一帧代表该时间段的主要界面。

    Args:
        frame_info:       [[图片路径, 时间戳], ...] 列表
        interval_seconds: 采样间隔（秒），默认 5.0

    Returns:
        filtered: [[图片路径, 时间戳], ...] 筛选后的列表
    """
    if not frame_info:
        return []

    filtered = [frame_info[0]]  # 始终保留第一帧
    last_ts = frame_info[0][1]

    for item in frame_info[1:]:
        ts = item[1]
        if ts - last_ts >= interval_seconds:
            filtered.append(item)
            last_ts = ts

    # 始终保留最后一帧
    if filtered[-1] != frame_info[-1]:
        filtered.append(frame_info[-1])

    return filtered


def main():
    parser = argparse.ArgumentParser(description="从操作视频中提取关键帧")
    parser.add_argument("video_path", help="视频文件路径")
    parser.add_argument("output_dir", help="关键帧输出目录")
    parser.add_argument("--threshold", type=float, default=0.90,
                        help="SSIM 相似度阈值 (0~1)，默认 0.90")
    parser.add_argument("--sample-every", type=int, default=5,
                        help="每隔 N 帧采样一次进行比较，默认 5")
    parser.add_argument("--resize", type=int, default=320,
                        help="计算 SSIM 时缩放的目标宽度，0=不缩放，默认 320")
    parser.add_argument("--filter-interval", type=float, default=0,
                        help="二次筛选间隔（秒），0=不筛选，默认 0")
    args = parser.parse_args()

    frame_info = extract_keyframes(
        args.video_path, args.output_dir,
        similarity_threshold=args.threshold,
        sample_every=args.sample_every,
        resize_width=args.resize,
    )

    # 二次筛选
    if args.filter_interval > 0:
        before_count = len(frame_info)
        frame_info = filter_frames_by_interval(frame_info, args.filter_interval)
        print(f"二次筛选: {before_count} -> {len(frame_info)} 帧 (间隔 {args.filter_interval}s)")

    # 保存 frame_info.json
    output_dir = args.output_dir
    info_path = os.path.join(output_dir, "frame_info.json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(frame_info, f, ensure_ascii=False, indent=2)
    print(f"帧信息已保存至: {info_path}")

    # 打印摘要
    for path, ts in frame_info:
        print(f"  [{ts:.1f}s] {os.path.basename(path)}")


if __name__ == "__main__":
    main()
