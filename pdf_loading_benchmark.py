#!/usr/bin/env python3
"""
PDF加载时间对比demo
对比直接加载为PIL图像 vs 通过base64转换的时间差异
"""

import os
import time
import glob
import statistics
from pathlib import Path
from typing import List, Tuple

import sys
sys.path.append('/home/ubuntu/MinerU-merge')

from mineru.utils.pdf_image_tools import load_images_from_pdf
from mineru.utils.enum_class import ImageType
from mineru.utils.pdf_reader import base64_to_pil_image


def load_pdf_files_from_directory(pdf_dir: str) -> List[Tuple[str, bytes]]:
    """
    从指定目录加载所有PDF文件

    Args:
        pdf_dir: PDF文件目录路径

    Returns:
        List[Tuple[str, bytes]]: (文件名, PDF字节数据) 的列表
    """
    pdf_files = []
    pdf_path = Path(pdf_dir)

    if not pdf_path.exists():
        print(f"错误: 目录 {pdf_dir} 不存在")
        return pdf_files

    # 查找所有PDF文件
    pdf_paths = list(pdf_path.glob("*.pdf")) + list(pdf_path.glob("*.PDF"))

    for pdf_path in pdf_paths:
        try:
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            pdf_files.append((pdf_path.name, pdf_bytes))
            print(f"加载PDF文件: {pdf_path.name} (大小: {len(pdf_bytes)} 字节)")
        except Exception as e:
            print(f"加载PDF文件 {pdf_path.name} 失败: {e}")

    return pdf_files


def benchmark_direct_loading(pdf_files: List[Tuple[str, bytes]]) -> List[float]:
    """
    测试直接加载为PIL图像的时间

    Args:
        pdf_files: PDF文件列表

    Returns:
        List[float]: 每个文件的加载时间
    """
    times = []
    print("\n=== 直接加载为PIL图像 ===")

    for filename, pdf_bytes in pdf_files:
        print(f"\n处理文件: {filename}")

        start_time = time.time()
        try:
            # 直接加载为PIL图像
            images_list, pdf_doc = load_images_from_pdf(
                pdf_bytes,
                image_type=ImageType.PIL
            )

            end_time = time.time()
            load_time = end_time - start_time
            times.append(load_time)

            print(f"  加载时间: {load_time:.4f}秒")
            print(f"  图像数量: {len(images_list)}")

            # 关闭PDF文档
            if pdf_doc:
                pdf_doc.close()

        except Exception as e:
            print(f"  加载失败: {e}")
            times.append(0.0)

    return times


def benchmark_base64_loading(pdf_files: List[Tuple[str, bytes]]) -> List[float]:
    """
    测试通过base64转换加载的时间

    Args:
        pdf_files: PDF文件列表

    Returns:
        List[float]: 每个文件的加载时间
    """
    times = []
    print("\n=== 通过Base64转换加载 ===")

    for filename, pdf_bytes in pdf_files:
        print(f"\n处理文件: {filename}")

        start_time = time.time()
        try:
            # 第一步: 加载为base64格式
            step1_time = time.time()
            images_list, pdf_doc = load_images_from_pdf(
                pdf_bytes,
                image_type=ImageType.BASE64
            )
            step1_end = time.time()
            step1_load_time = step1_end - step1_time

            # 第二步: 从base64转换回PIL图像
            step2_time = time.time()
            pil_images = []
            for image_dict in images_list:
                if image_dict and isinstance(image_dict, dict) and "img_base64" in image_dict:
                    pil_img = base64_to_pil_image(image_dict["img_base64"])
                    pil_images.append(pil_img)
            step2_end = time.time()
            step2_convert_time = step2_end - step2_time

            total_time = step1_end - start_time
            times.append(total_time)

            print(f"  总加载时间: {total_time:.4f}秒")
            print(f"    - 转base64时间: {step1_load_time:.4f}秒")
            print(f"    - base64转PIL时间: {step2_convert_time:.4f}秒")
            print(f"  图像数量: {len(images_list)}")

            # 关闭PDF文档
            if pdf_doc:
                pdf_doc.close()

        except Exception as e:
            print(f"  加载失败: {e}")
            times.append(0.0)

    return times


def print_comparison_stats(direct_times: List[float], base64_times: List[float],
                         pdf_files: List[Tuple[str, bytes]]):
    """
    打印对比统计信息
    """
    print("\n" + "="*60)
    print("性能对比统计")
    print("="*60)

    # 过滤掉失败的时间（0.0）
    valid_direct_times = [t for t in direct_times if t > 0]
    valid_base64_times = [t for t in base64_times if t > 0]

    if not valid_direct_times or not valid_base64_times:
        print("没有有效的测试数据")
        return

    print(f"成功测试的文件数量: {len(valid_direct_times)}")
    print(f"PDF文件总大小: {sum(len(pdf_bytes) for _, pdf_bytes in pdf_files if len(pdf_bytes) > 0):,} 字节")

    print(f"\n直接加载时间统计:")
    print(f"  平均时间: {statistics.mean(valid_direct_times):.4f}秒")
    print(f"  中位数: {statistics.median(valid_direct_times):.4f}秒")
    print(f"  最小时间: {min(valid_direct_times):.4f}秒")
    print(f"  最大时间: {max(valid_direct_times):.4f}秒")

    print(f"\nBase64转换时间统计:")
    print(f"  平均时间: {statistics.mean(valid_base64_times):.4f}秒")
    print(f"  中位数: {statistics.median(valid_base64_times):.4f}秒")
    print(f"  最小时间: {min(valid_base64_times):.4f}秒")
    print(f"  最大时间: {max(valid_base64_times):.4f}秒")

    # 计算性能差异
    avg_direct = statistics.mean(valid_direct_times)
    avg_base64 = statistics.mean(valid_base64_times)
    overhead = avg_base64 - avg_direct
    overhead_percent = (overhead / avg_direct) * 100 if avg_direct > 0 else 0

    print(f"\n性能差异:")
    print(f"  平均额外开销: {overhead:.4f}秒")
    print(f"  开销百分比: {overhead_percent:.2f}%")

    if overhead_percent > 0:
        print(f"  Base64方法比直接方法慢 {overhead_percent:.2f}%")
    else:
        print(f"  Base64方法比直接方法快 {-overhead_percent:.2f}%")


def main():
    """
    主函数
    """
    # PDF文件目录 - 可以修改为你想要的目录
    pdf_dir = "/home/ubuntu/MinerU-merge/demo"  # 默认使用demo目录

    # 如果命令行参数提供了目录，则使用提供的目录
    if len(sys.argv) > 1:
        pdf_dir = sys.argv[1]

    print("PDF加载时间对比Demo")
    print("="*40)
    print(f"PDF目录: {pdf_dir}")

    # 加载PDF文件
    pdf_files = load_pdf_files_from_directory(pdf_dir)

    if not pdf_files:
        print(f"在目录 {pdf_dir} 中没有找到PDF文件")
        print("用法: python pdf_loading_benchmark.py [pdf_directory]")
        return

    print(f"\n找到 {len(pdf_files)} 个PDF文件")

    # 基准测试
    print("\n开始基准测试...")

    # 测试直接加载
    direct_times = benchmark_direct_loading(pdf_files)

    # 测试base64加载
    base64_times = benchmark_base64_loading(pdf_files)

    # 打印对比统计
    print_comparison_stats(direct_times, base64_times, pdf_files)

    print("\n测试完成!")


if __name__ == "__main__":
    main()