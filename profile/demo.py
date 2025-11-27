#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的PDF处理demo
统计load_images_from_pdf函数的总调用时间
"""

import os
import sys
import time
import glob
import functools
import inspect
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mineru.utils.pdf_image_tools import load_images_from_pdf


def profile_lines(func):
    """
    简单的行级性能分析装饰器
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"\n🔍 开始行级性能分析: {func.__name__}")
        print("=" * 50)

        # 记录每行执行时间
        line_times = {}
        last_time = None
        last_line = None

        def trace_calls(frame, event, arg):
            if event == 'call' and frame.f_code.co_name == func.__name__:
                return trace_lines
            return None

        def trace_lines(frame, event, arg):
            nonlocal last_time, last_line

            if event == 'line':
                current_line = frame.f_lineno
                current_time = time.perf_counter()

                # 计算上一行的执行时间
                if last_time is not None and last_line is not None:
                    exec_time = current_time - last_time
                    line_times[last_line] = line_times.get(last_line, 0) + exec_time

                last_time = current_time
                last_line = current_line

            return trace_lines

        # 设置跟踪
        sys.settrace(trace_calls)

        try:
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            total_time = time.perf_counter() - start_time

            # 停止跟踪
            sys.settrace(None)

            # 显示行级分析结果
            print(f"\n📊 行级性能分析结果 (总耗时: {total_time:.3f}s)")
            print("-" * 50)

            # 获取源代码
            try:
                source_lines = inspect.getsourcelines(func)[0]
                start_line = inspect.getsourcelines(func)[1]
            except:
                print("无法获取源代码")
                return result

            # 按时间排序显示
            sorted_lines = sorted(line_times.items(), key=lambda x: x[1], reverse=True)

            for line_no, exec_time in sorted_lines:
                if exec_time > 0.001:  # 只显示耗时超过1ms的行
                    # 获取源代码
                    if start_line <= line_no < start_line + len(source_lines):
                        line_idx = line_no - start_line
                        if line_idx < len(source_lines):
                            code_line = source_lines[line_idx].strip()
                        else:
                            continue
                    else:
                        continue

                    # 显示格式：行号 时间 代码
                    print(f"行{line_no:3d}: {exec_time:6.3f}s - {code_line}")

            print("-" * 50)
            return result

        except Exception as e:
            sys.settrace(None)
            print(f"❌ 分析出错: {e}")
            raise

    return wrapper


@profile_lines
def process_pdf_directory(directory_path):
    """
    处理目录中的所有PDF文件，统计总时间

    Args:
        directory_path: PDF文件目录路径
    """
    print(f"开始处理目录: {directory_path}")

    # 查找所有PDF文件
    pdf_files = glob.glob(os.path.join(directory_path, "*.pdf"))

    if not pdf_files:
        print("未找到PDF文件")
        return

    print(f"找到 {len(pdf_files)} 个PDF文件")

    total_time = 0.0
    total_pages = 0
    total_images = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] 处理: {os.path.basename(pdf_path)}")

        try:
            # 读取PDF文件
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()

            # 记录开始时间
            start_time = time.time()

            # 调用load_images_from_pdf
            images_list, pdf_doc = load_images_from_pdf(
                pdf_bytes=pdf_bytes,
                dpi=200,
                start_page_id=0,
                end_page_id=None,
                image_type="PIL",
                threads=4
            )

            # 记录结束时间
            end_time = time.time()
            processing_time = end_time - start_time

            # 累计统计
            total_time += processing_time
            pages_count = len(pdf_doc)
            images_count = len(images_list)
            total_pages += pages_count
            total_images += images_count

            # 关闭PDF文档
            pdf_doc.close()

            print(f"  处理完成: {processing_time:.3f}s, {pages_count}页, {images_count}张图")

        except Exception as e:
            print(f"  处理失败: {e}")
            continue

    # 输出总统计
    print(f"\n{'='*50}")
    print("处理完成！总统计:")
    print(f"{'='*50}")
    print(f"处理文件数: {len(pdf_files)}")
    print(f"总页数: {total_pages}")
    print(f"总图片数: {total_images}")
    print(f"load_images_from_pdf 总耗时: {total_time:.3f}s")
    print(f"平均每页耗时: {total_time/total_pages:.3f}s" if total_pages > 0 else "平均每页耗时: N/A")
    print(f"处理速度: {total_pages/total_time:.2f} 页/秒" if total_time > 0 else "处理速度: N/A")


def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("用法: python demo.py <pdf_directory_path>")
        print("示例: python demo.py /path/to/pdf/files")
        return

    directory_path = sys.argv[1]

    if not os.path.isdir(directory_path):
        print(f"错误: 目录不存在 - {directory_path}")
        return

    process_pdf_directory(directory_path)


if __name__ == "__main__":
    main()