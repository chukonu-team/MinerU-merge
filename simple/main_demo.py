#!/usr/bin/env python3
"""
Simple Main Demo - 基于 pool.md 设计的简洁架构
三级队列系统：preprocess_queue -> gpu_queue -> post_queue
"""

import os
import sys
import time
from pathlib import Path

# 添加main目录到路径以便导入模块
sys.path.insert(0, '/home/ubuntu/MinerU-merge/main')

from common import get_subdirectories, has_files
from ocr_pdf_pool import process_pdf_files_with_pools


def process():
    """
    主处理函数 - 基于新的三级队列架构设计
    """
    # 基本配置参数
    gpu_ids = "0"  # 使用GPU 0
    vram_size_gb = "24"  # 24GB显存
    workers_per_gpu = "1"  # 每个GPU 1个工作进程
    max_pages = "1000"  # 最大页数限制
    shuffle = False  # 不打乱顺序
    batch_size = "384"  # 批处理大小
    proportion = 0  # 处理比例阈值

    # 设置环境变量以减少GPU内存使用
    os.environ["GPU_MEMORY_UTILIZATION"] = "0.5"
    os.environ["BACKEND"] = "vllm-engine"

    pdf_dir = "/home/ubuntu/MinerU-merge/demo/pdfs"  # 输入目录
    output_dir = "/tmp/result"  # 输出目录

    # 检查是否有子目录，如果没有则直接处理根目录
    list_dir = get_subdirectories(pdf_dir)

    if not list_dir:
        # 如果没有子目录，直接处理pdf_dir中的文件
        print(f"No subdirectories found in {pdf_dir}, processing files directly")
        if not has_files(pdf_dir):
            print(f"No PDF files found in {pdf_dir}")
            sys.exit(1)
        index = ""  # 空字符串表示根目录
    else:
        # 如果有子目录，按原来的逻辑处理
        index = None
        for bucket_index in list_dir:
            print(f"Processing bucket {bucket_index}")
            pdf_path = os.path.join(pdf_dir, bucket_index)
            if not has_files(pdf_path):
                continue

            result_dir = os.path.join(output_dir, bucket_index, "result")
            if os.path.exists(result_dir):
                result_list = os.listdir(result_dir)
                pdf_list = os.listdir(pdf_path)
                cur_proportion = (len(pdf_list) - len(result_list)) / len(pdf_list)
                print("cur_proportion", cur_proportion)
                if cur_proportion < float(proportion):
                    print(f"Skipping {bucket_index} because proportion is less than {proportion}")
                    continue

            index = bucket_index
            break

    input_path = f"{pdf_dir}{index}"
    output_path = f"{output_dir}{index}"

    try:
        print("=== 启动三级队列架构处理系统 ===")
        print(f"输入路径: {input_path}")
        print(f"输出路径: {output_path}")
        print(f"GPU配置: {gpu_ids}, 显存: {vram_size_gb}GB, 每GPU工作进程: {workers_per_gpu}")

        start_time = time.time()

        # 使用新的三级队列架构处理PDF文件
        process_pdf_files_with_pools(
            input_dir=input_path,
            output_dir=output_path,
            vram_size_gb=int(vram_size_gb),
            gpu_ids=gpu_ids,
            workers_per_gpu=int(workers_per_gpu),
            max_pages=int(max_pages),
            shuffle=shuffle,
            batch_size=int(batch_size)
        )

        end_time = time.time()
        processing_time = end_time - start_time

        print(f"=== 处理完成 ===")
        print(f"总处理时间: {processing_time:.2f}秒")
        sys.exit(0)

    except Exception as e:
        print(f"Error processing bucket {index}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    process()