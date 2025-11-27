#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的PDF批量性能测试脚本
快速测试多个PDF文件的load_images_from_pdf函数性能
"""

import os
import sys
import time
import glob
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mineru.utils.pdf_image_tools import load_images_from_pdf

def batch_test_pdfs(pdf_directory: str, max_files: int = None, pattern: str = "*.pdf"):
    """
    批量测试目录中的PDF文件

    Args:
        pdf_directory: PDF文件目录
        max_files: 最大处理文件数，None表示处理全部
        pattern: 文件匹配模式
    """
    print(f"🚀 批量测试PDF目录: {pdf_directory}")
    print(f"📄 文件模式: {pattern}")
    if max_files:
        print(f"🔢 限制文件数: {max_files}")
    print("=" * 60)

    if not os.path.exists(pdf_directory):
        print(f"❌ 目录不存在: {pdf_directory}")
        return

    # 查找PDF文件
    pdf_files = glob.glob(os.path.join(pdf_directory, pattern))
    pdf_files.sort()  # 按文件名排序

    if not pdf_files:
        print(f"❌ 在目录 {pdf_directory} 中未找到匹配的PDF文件")
        return

    if max_files:
        pdf_files = pdf_files[:max_files]

    print(f"📄 找到 {len(pdf_files)} 个PDF文件")

    # 创建输出目录
    output_dir = "./profile_outputs"
    os.makedirs(output_dir, exist_ok=True)

    # 开始批量测试
    start_time = time.time()
    all_results = []

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n📁 [{i}/{len(pdf_files)}] 测试: {os.path.basename(pdf_path)}")
        print("-" * 50)

        try:
            result = quick_pdf_test(pdf_path, dpi=200, max_pages=None)
            if result:
                all_results.append(result)
                # 显示简要结果
                print(f"✅ 完成: {result['pdf_size_mb']:.2f}MB, {result['processed_pages']}页, {result['pages_per_second']:.2f}页/秒")
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            continue

    total_batch_time = time.time() - start_time

    # 生成批量测试汇总
    generate_batch_summary(pdf_directory, all_results, total_batch_time)

    return all_results

def quick_pdf_test(pdf_path: str, dpi: int = 200, max_pages: int = None):
    """
    快速测试PDF解析性能

    Args:
        pdf_path: PDF文件路径
        dpi: 图像分辨率
        max_pages: 最大处理页数

    Returns:
        dict: 性能测试结果
    """
    try:
        import pypdfium2 as pdfium
    except ImportError:
        print("❌ pypdfium2 not installed. Please install it with: pip install pypdfium2")
        return None

    print(f"🚀 开始测试: {pdf_path}")
    print("-" * 50)

    # 1. 基本文件信息
    if not os.path.exists(pdf_path):
        print(f"❌ 文件不存在: {pdf_path}")
        return None

    file_size = os.path.getsize(pdf_path)
    print(f"📄 文件大小: {file_size / 1024 / 1024:.2f} MB")

    # 2. 读取文件
    read_start = time.time()
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    read_time = time.time() - read_start
    print(f"📖 文件读取耗时: {read_time:.3f}s")

    # 3. 获取PDF信息
    info_start = time.time()
    pdf_doc = pdfium.PdfDocument(pdf_bytes)
    total_pages = len(pdf_doc)
    if max_pages:
        total_pages = min(total_pages, max_pages)
    info_time = time.time() - info_start
    print(f"🔍 信息获取耗时: {info_time:.3f}s")
    print(f"📋 总页数: {total_pages}")

    # 4. 核心性能测试 - load_images_from_pdf
    print(f"🎯 开始核心性能测试 (DPI={dpi})...")
    load_start = time.time()

    try:
        images_list, pdf_doc = load_images_from_pdf(
            pdf_bytes=pdf_bytes,
            dpi=dpi,
            start_page_id=0,
            end_page_id=total_pages-1,
            image_type="PIL",
            threads=4
        )

        load_time = time.time() - load_start
        images_count = len(images_list)

        print(f"✅ 测试完成!")
        print(f"⏱️  load_images_from_pdf 耗时: {load_time:.3f}s")
        print(f"🖼️  生成图像数量: {images_count}")
        print(f"📊 平均每页耗时: {load_time / total_pages:.3f}s")

        # 关闭文档
        pdf_doc.close()

        # 5. 性能总结
        total_time = read_time + info_time + load_time
        pages_per_second = total_pages / load_time if load_time > 0 else 0
        throughput_mbps = (file_size / 1024 / 1024) / load_time if load_time > 0 else 0

        print(f"\n📈 性能总结:")
        print(f"   总耗时: {total_time:.3f}s")
        print(f"   - 文件读取: {read_time:.3f}s ({read_time/total_time*100:.1f}%)")
        print(f"   - 信息获取: {info_time:.3f}s ({info_time/total_time*100:.1f}%)")
        print(f"   - 图像解析: {load_time:.3f}s ({load_time/total_time*100:.1f}%)")

        print(f"\n📊 关键指标:")
        print(f"   文件大小: {file_size / 1024 / 1024:.2f} MB")
        print(f"   处理速度: {pages_per_second:.2f} 页/秒")
        print(f"   数据吞吐量: {throughput_mbps:.2f} MB/s")

        return {
            'pdf_path': pdf_path,
            'pdf_size_mb': file_size / 1024 / 1024,
            'processed_pages': total_pages,
            'pages_per_second': pages_per_second,
            'throughput_mbps': throughput_mbps,
            'read_time': read_time,
            'info_time': info_time,
            'load_time': load_time,
            'total_time': total_time
        }

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return None

def generate_batch_summary(pdf_directory: str, results: list, total_time: float):
    """生成批量测试汇总报告"""
    if not results:
        return

    print(f"\n" + "=" * 80)
    print(f"📈 批量测试汇总 - 目录: {pdf_directory}")
    print("=" * 80)

    # 计算汇总统计
    total_files = len(results)
    total_pages = sum(r['processed_pages'] for r in results)
    total_size_mb = sum(r['pdf_size_mb'] for r in results)
    total_load_time = sum(r['load_time'] for r in results)

    avg_file_size_mb = total_size_mb / total_files if total_files > 0 else 0
    avg_pages_per_file = total_pages / total_files if total_files > 0 else 0
    avg_time_per_file = total_load_time / total_files if total_files > 0 else 0
    avg_pages_per_sec = total_pages / total_load_time if total_load_time > 0 else 0

    # 找出最快和最慢的文件
    if results:
        fastest = max(results, key=lambda r: r['pages_per_second'])
        slowest = min(results, key=lambda r: r['pages_per_second'])

        print(f"\n📊 总体统计:")
        print(f"   处理文件数: {total_files}")
        print(f"   总页数: {total_pages}")
        print(f"   总文件大小: {total_size_mb:.2f} MB")
        print(f"   总处理时间: {total_load_time:.3f}s")
        print(f"   批量分析耗时: {total_time:.3f}s")

        print(f"\n📈 平均指标:")
        print(f"   平均文件大小: {avg_file_size_mb:.2f} MB")
        print(f"   平均每文件页数: {avg_pages_per_file:.1f}")
        print(f"   平均每文件耗时: {avg_time_per_file:.3f}s")
        print(f"   平均处理速度: {avg_pages_per_sec:.2f} 页/秒")
        print(f"   平均处理吞吐量: {total_size_mb / total_load_time:.2f} MB/s")

        print(f"\n🏆 性能极值:")
        print(f"   🚀 最快文件: {os.path.basename(fastest['pdf_path'])} ({fastest['pages_per_second']:.2f} 页/秒)")
        print(f"   🐌 最慢文件: {os.path.basename(slowest['pdf_path'])} ({slowest['pages_per_second']:.2f} 页/秒)")

        # 保存汇总报告
        summary_file = os.path.join("./profile_outputs", f"batch_summary_{int(time.time())}.txt")
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("PDF批量解析性能测试汇总报告\n")
            f.write("=" * 60 + "\n")
            f.write(f"分析目录: {pdf_directory}\n")
            f.write(f"分析时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"分析耗时: {total_time:.3f}s\n\n")

            f.write("📊 总体统计\n")
            f.write("-" * 30 + "\n")
            f.write(f"处理文件数: {total_files}\n")
            f.write(f"总页数: {total_pages}\n")
            f.write(f"总文件大小: {total_size_mb:.2f} MB\n")
            f.write(f"总处理时间: {total_load_time:.3f}s\n\n")

            f.write("📈 平均指标\n")
            f.write("-" * 30 + "\n")
            f.write(f"平均文件大小: {avg_file_size_mb:.2f} MB\n")
            f.write(f"平均每文件页数: {avg_pages_per_file:.1f}\n")
            f.write(f"平均每文件耗时: {avg_time_per_file:.3f}s\n")
            f.write(f"平均处理速度: {avg_pages_per_sec:.2f} 页/秒\n")
            f.write(f"平均处理吞吐量: {total_size_mb / total_load_time:.2f} MB/s\n\n")

            f.write("🏆 性能极值\n")
            f.write("-" * 30 + "\n")
            f.write(f"最快文件: {os.path.basename(fastest['pdf_path'])} ({fastest['pages_per_second']:.2f} 页/秒)\n")
            f.write(f"最慢文件: {os.path.basename(slowest['pdf_path'])} ({slowest['pages_per_second']:.2f} 页/秒)\n\n")

            f.write("📋 详细结果\n")
            f.write("-" * 30 + "\n")
            f.write(f"{'文件名':<40} {'大小(MB)':<10} {'页数':<6} {'耗时(s)':<10} {'速度(页/s)':<12}\n")
            f.write("-" * 78 + "\n")

            # 按处理速度排序
            sorted_results = sorted(results, key=lambda r: r['pages_per_second'], reverse=True)

            for result in sorted_results:
                filename = os.path.basename(result['pdf_path'])[:38]
                speed = result['pages_per_second']
                f.write(f"{filename:<40} {result['pdf_size_mb']:<10.2f} {result['processed_pages']:<6} {result['load_time']:<10.3f} {speed:<12.2f}\n")

        print(f"\n📁 批量测试汇总:")
        print(f"   处理文件数: {total_files}")
        print(f"   总页数: {total_pages}")
        print(f"   总文件大小: {total_size_mb:.2f} MB")
        print(f"   平均处理速度: {avg_pages_per_sec:.2f} 页/秒")
        print(f"   分析耗时: {total_time:.3f}s")
        print(f"   📊 汇总报告已保存: {summary_file}")

def main():
    """主函数"""
    print("🎯 MinerU PDF批量解析性能测试工具")
    print("=" * 50)

    if len(sys.argv) < 2:
        print("用法:")
        print("  python batch_test_simple.py <pdf_directory> [max_files]")
        print()
        print("示例:")
        print("  python batch_test_simple.py /path/to/pdfs/")
        print("  python batch_test_simple.py /path/to/pdfs/ --max-files 10")
        return

    pdf_directory = sys.argv[1]
    max_files = None

    if len(sys.argv) >= 3 and sys.argv[2] != "--max-files":
        print("❌ 未知参数，使用 --max-files <num> 限制文件数")
        return
    elif len(sys.argv) >= 4:
        try:
            max_files = int(sys.argv[3])
        except ValueError:
            print("❌ --max-files 需要是数字")
            return

    batch_test_pdfs(pdf_directory, max_files)

if __name__ == "__main__":
    main()