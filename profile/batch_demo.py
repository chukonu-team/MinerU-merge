#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的PDF批量性能分析演示
专门解决单文件测试时间过短的问题
"""

import os
import sys
import time
import glob
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mineru.utils.pdf_image_tools import load_images_from_pdf

def quick_batch_test(pdf_directory: str, max_files: int = None):
    """
    快速批量测试PDF文件

    Args:
        pdf_directory: PDF文件目录
        max_files: 最大处理文件数
    """
    print(f"🚀 批量测试PDF目录: {pdf_directory}")
    print("=" * 50)

    if not os.path.exists(pdf_directory):
        print(f"❌ 目录不存在: {pdf_directory}")
        return

    # 查找PDF文件
    pdf_files = glob.glob(os.path.join(pdf_directory, "*.pdf"))
    pdf_files.sort()  # 按文件名排序

    if not pdf_files:
        print(f"❌ 在目录 {pdf_directory} 中未找到PDF文件")
        return

    if max_files:
        pdf_files = pdf_files[:max_files]
        print(f"🔢 限制处理文件数: {len(pdf_files)}")

    print(f"📄 找到 {len(pdf_files)} 个PDF文件")

    # 开始批量测试
    start_time = time.time()
    all_results = []

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n📁 [{i}/{len(pdf_files)}] 测试: {os.path.basename(pdf_path)}")
        print("-" * 40)

        try:
            test_result = test_single_pdf(pdf_path)
            if test_result:
                all_results.append(test_result)

                # 显示简要结果
                print(f"✅ 完成: {test_result['file_size_mb']:.2f}MB, "
                      f"{test_result['pages']}页, "
                      f"{test_result['pages_per_sec']:.2f}页/秒")

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            continue

    # 生成批量测试汇总
    total_time = time.time() - start_time

    if all_results:
        generate_batch_summary(pdf_directory, all_results, total_time)

    print(f"\n🎉 批量测试完成! 共处理 {len(all_results)} 个PDF文件")
    print(f"📊 总耗时: {total_time:.3f}s")
    print(f"📁 详细报告已保存到 ./profile_outputs/")

def test_single_pdf(pdf_path: str) -> dict:
    """测试单个PDF文件"""
    import pypdfium2 as pdfium

    try:
        # 1. 文件信息
        file_size = os.path.getsize(pdf_path)
        file_size_mb = file_size / 1024 / 1024

        # 2. 读取文件
        read_start = time.time()
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
        read_time = time.time() - read_start

        # 3. 获取PDF信息
        info_start = time.time()
        pdf_doc = pdfium.PdfDocument(pdf_bytes)
        total_pages = len(pdf_doc)
        info_time = time.time() - info_start

        # 4. 核心性能测试
        load_start = time.time()
        images_list, pdf_doc_result = load_images_from_pdf(
            pdf_bytes=pdf_bytes,
            dpi=200,
            start_page_id=0,
            end_page_id=total_pages - 1,
            image_type="PIL",
            threads=4
        )
        load_time = time.time() - load_start

        pdf_doc_result.close()

        # 5. 计算性能指标
        if load_time > 0:
            pages_per_sec = total_pages / load_time
        else:
            pages_per_sec = 0

        # 6. 返回结果
        return {
            'pdf_path': pdf_path,
            'file_size_mb': file_size_mb,
            'pages': total_pages,
            'read_time': read_time,
            'info_time': info_time,
            'load_time': load_time,
            'total_time': read_time + info_time + load_time,
            'pages_per_sec': pages_per_sec
        }

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return None

def generate_batch_summary(pdf_directory: str, results: list, total_time: float):
    """生成批量测试汇总报告"""
    if not results:
        return

    os.makedirs("./profile_outputs", exist_ok=True)

    # 计算汇总统计
    total_files = len(results)
    total_pages = sum(r['pages'] for r in results)
    total_size_mb = sum(r['file_size_mb'] for r in results)
    total_load_time = sum(r['load_time'] for r in results)

    avg_file_size_mb = total_size_mb / total_files if total_files > 0 else 0
    avg_pages_per_file = total_pages / total_files if total_files > 0 else 0
    avg_load_time = total_load_time / total_files if total_files > 0 else 0
    avg_pages_per_sec = total_pages / total_load_time if total_load_time > 0 else 0

    # 找出最快和最慢的文件
    if results:
        fastest = max(results, key=lambda r: r['pages_per_sec'] if r['pages_per_sec'] > 0 else 0)
        slowest = min(results, key=lambda r: r['pages_per_sec'] if r['pages_per_sec'] > 0 else 0)

    # 生成汇总报告
    timestamp = int(time.time())
    summary_file = f"./profile_outputs/batch_summary_{timestamp}.txt"

    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("📊 PDF批量解析性能分析报告\n")
        f.write("=" * 60 + "\n")
        f.write(f"分析目录: {pdf_directory}\n")
        f.write(f"分析时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"分析耗时: {total_time:.3f}s\n\n")

        f.write("📈 总体统计\n")
        f.write("-" * 30 + "\n")
        f.write(f"处理文件数: {total_files}\n")
        f.write(f"总页数: {total_pages}\n")
        f.write(f"总文件大小: {total_size_mb:.2f} MB\n")
        f.write(f"总图像解析时间: {total_load_time:.3f}s\n\n")

        f.write("📈 平均指标\n")
        f.write("-" * 30 + "\n")
        f.write(f"平均文件大小: {avg_file_size_mb:.2f} MB\n")
        f.write(f"平均每文件页数: {avg_pages_per_file:.1f}\n")
        f.write(f"平均每文件解析时间: {avg_load_time:.3f}s\n")
        f.write(f"平均处理速度: {avg_pages_per_sec:.2f} 页/秒\n\n")

        if results:
            f.write("🏆 性能极值\n")
            f.write("-" * 30 + "\n")
            f.write(f"🚀 最快文件: {os.path.basename(fastest['pdf_path'])} "
                  f"({fastest['pages_per_sec']:.2f} 页/秒)\n")
            f.write(f"🐌 最慢文件: {os.path.basename(slowest['pdf_path'])} "
                  f"({slowest['pages_per_sec']:.2f} 页/秒)\n\n")

            f.write("📋 详细结果\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'文件名':<35} {'大小(MB)':<10} {'页数':<6} {'解析时间(s)':<12} {'速度(页/s)':<12}\n")
            f.write("-" * 80 + "\n")

            # 按处理速度排序
            sorted_results = sorted(results, key=lambda r: r['pages_per_sec'], reverse=True)

            for result in sorted_results:
                filename = os.path.basename(result['pdf_path'])[:33]
                speed = result['pages_per_sec']
                f.write(f"{filename:<35} {result['file_size_mb']:<10.2f} {result['pages']:<6} "
                      f"{result['load_time']:<12.3f} {speed:<12.2f}\n")

def main():
    """主函数"""
    print("🎯 MinerU PDF批量性能分析工具")
    print("=" * 50)

    if len(sys.argv) < 2:
        print("\n用法:")
        print("  python batch_demo.py <PDF目录路径> [最大文件数]")
        print("\n示例:")
        print("  python batch_demo.py /path/to/pdf/files/")
        print("  python batch_demo.py /path/to/pdf/files/ 10")
        return

    pdf_directory = sys.argv[1]
    max_files = int(sys.argv[2]) if len(sys.argv) > 2 else None

    quick_batch_test(pdf_directory, max_files)

if __name__ == "__main__":
    main()