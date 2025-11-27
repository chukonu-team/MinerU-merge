#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinerU PDF批量性能分析工具
专门用于批量处理整个PDF目录，解决单文件测试时间过短的问题
"""

import os
import sys
import time
import glob
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mineru.utils.pdf_image_tools import load_images_from_pdf

def analyze_pdf_directory(pdf_directory: str, dpi: int = 200, max_files: int = None):
    """
    批量分析PDF目录

    Args:
        pdf_directory: PDF文件目录
        dpi: 图像分辨率
        max_files: 最大处理文件数，None表示处理全部
    """
    print(f"🚀 批量分析PDF目录: {pdf_directory}")
    print(f"🔧 参数: DPI={dpi}, 限制文件数={max_files}")
    print("=" * 60)

    if not os.path.exists(pdf_directory):
        print(f"❌ 目录不存在: {pdf_directory}")
        return []

    # 查找PDF文件
    pdf_files = glob.glob(os.path.join(pdf_directory, "*.pdf"))
    pdf_files.sort()  # 按文件名排序

    if not pdf_files:
        print(f"❌ 在目录 {pdf_directory} 中未找到PDF文件")
        return []

    if max_files:
        pdf_files = pdf_files[:max_files]

    print(f"📄 找到 {len(pdf_files)} 个PDF文件")

    # 创建输出目录
    output_dir = "./profile_outputs"
    os.makedirs(output_dir, exist_ok=True)

    # 开始批量分析
    start_time = time.time()
    results = []

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n📁 [{i}/{len(pdf_files)}] 分析: {os.path.basename(pdf_path)}")
        print("-" * 50)

        try:
            import pypdfium2 as pdfium

            # 1. 读取文件
            read_start = time.time()
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            read_time = time.time() - read_start

            # 2. 获取PDF信息
            info_start = time.time()
            pdf_doc = pdfium.PdfDocument(pdf_bytes)
            total_pages = len(pdf_doc)
            info_time = time.time() - info_start

            # 3. 核心性能测试
            load_start = time.time()
            images_list, pdf_doc_result = load_images_from_pdf(
                pdf_bytes=pdf_bytes,
                dpi=dpi,
                start_page_id=0,
                end_page_id=total_pages - 1,
                image_type="PIL",
                threads=4
            )
            load_time = time.time() - load_start

            # 4. 关闭文档
            pdf_doc_result.close()

            # 5. 计算性能指标
            file_size_mb = os.path.getsize(pdf_path) / 1024 / 1024
            pages_per_sec = total_pages / load_time if load_time > 0 else 0
            throughput_mbps = file_size_mb / load_time if load_time > 0 else 0

            # 6. 显示结果
            print(f"✅ 完成: {file_size_mb:.2f}MB, {total_pages}页, {pages_per_sec:.2f}页/秒")
            print(f"📊 关键指标:")
            print(f"   文件大小: {file_size_mb:.2f} MB")
            print(f"   处理速度: {pages_per_sec:.2f} 页/秒")
            print(f"   数据吞吐量: {throughput_mbps:.2f} MB/s")

            # 7. 保存结果
            results.append({
                'pdf_path': pdf_path,
                'file_size_mb': file_size_mb,
                'total_pages': total_pages,
                'pages_per_sec': pages_per_sec,
                'read_time': read_time,
                'info_time': info_time,
                'load_time': load_time,
                'total_time': read_time + info_time + load_time
            })

        except Exception as e:
            print(f"❌ 分析失败: {e}")
            continue

    total_batch_time = time.time() - start_time

    # 生成汇总报告
    print(f"\n" + "=" * 60)
    print(f"📈 批量分析汇总:")
    print(f"   处理文件数: {len(results)}")
    print(f"   总页数: {sum(r['total_pages'] for r in results)}")
    print(f"   总文件大小: {sum(r['file_size_mb'] for r in results):.2f} MB")
    print(f"   总处理时间: {total_batch_time:.3f}s")

    if results:
        avg_size_mb = sum(r['file_size_mb'] for r in results) / len(results)
        avg_pages_per_file = sum(r['total_pages'] for r in results) / len(results)
        avg_time_per_file = total_batch_time / len(results)
        avg_pages_per_sec = sum(r['total_pages'] for r in results) / total_batch_time
        avg_throughput = sum(r['file_size_mb'] for r in results) / total_batch_time

        print(f"   平均文件大小: {avg_size_mb:.2f} MB")
        print(f"   平均每文件页数: {avg_pages_per_file:.1f}")
        print(f"   平均每文件耗时: {avg_time_per_file:.3f}s")
        print(f"   平均处理速度: {avg_pages_per_sec:.2f} 页/秒")
        print(f"   平均处理吞吐量: {avg_throughput:.2f} MB/s")

        # 找出性能极值
        fastest = max(results, key=lambda r: r['pages_per_sec'])
        slowest = min(results, key=lambda r: r['pages_per_sec'])

        print(f"\n🏆 性能极值:")
        print(f"   🚀 最快文件: {os.path.basename(fastest['pdf_path'])} ({fastest['pages_per_sec']:.2f} 页/秒)")
        print(f"   🐌 最慢文件: {os.path.basename(slowest['pdf_path'])} ({slowest['pages_per_sec']:.2f} 页/秒)")

        # 保存详细报告
        summary_file = os.path.join(output_dir, f"batch_summary_{int(time.time())}.txt")
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("PDF批量解析性能分析汇总报告\n")
            f.write("=" * 60 + "\n")
            f.write(f"分析目录: {pdf_directory}\n")
            f.write(f"分析时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"分析耗时: {total_batch_time:.3f}s\n\n")

            f.write("📊 总体统计\n")
            f.write("-" * 30 + "\n")
            f.write(f"处理文件数: {len(results)}\n")
            f.write(f"总页数: {sum(r['total_pages'] for r in results)}\n")
            f.write(f"总文件大小: {sum(r['file_size_mb'] for r in results):.2f} MB\n")
            f.write(f"总处理时间: {total_batch_time:.3f}s\n\n")

            f.write("📈 平均指标\n")
            f.write("-" * 30 + "\n")
            f.write(f"平均文件大小: {avg_size_mb:.2f} MB\n")
            f.write(f"平均每文件页数: {avg_pages_per_file:.1f}\n")
            f.write(f"平均每文件耗时: {avg_time_per_file:.3f}s\n")
            f.write(f"平均处理速度: {avg_pages_per_sec:.2f} 页/秒\n")
            f.write(f"平均处理吞吐量: {avg_throughput:.2f} MB/s\n\n")

            f.write("🏆 性能极值\n")
            f.write("-" * 30 + "\n")
            f.write(f"最快文件: {os.path.basename(fastest['pdf_path'])} ({fastest['pages_per_sec']:.2f} 页/秒)\n")
            f.write(f"最慢文件: {os.path.basename(slowest['pdf_path'])} ({slowest['pages_per_sec']:.2f} 页/秒)\n\n")

            f.write("📋 详细结果\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'文件名':<30} {'大小(MB)':<8} {'页数':<6} {'速度(页/s)':<12}\n")
            f.write("-" * 80 + "\n")

            # 按处理速度排序
            sorted_results = sorted(results, key=lambda r: r['pages_per_sec'], reverse=True)
            for result in sorted_results:
                filename = os.path.basename(result['pdf_path'])[:28]
                size_mb = result['file_size_mb']
                pages = result['total_pages']
                speed = result['pages_per_sec']
                f.write(f"{filename:<30} {size_mb:<8.2f} {pages:<6} {speed:<12.2f}\n")

        print(f"\n📁 批量分析汇总:")
        print(f"   处理文件数: {len(results)}")
        print(f"   总页数: {sum(r['total_pages'] for r in results)}")
        print(f"   总文件大小: {sum(r['file_size_mb'] for r in results):.2f} MB")
        print(f"   平均处理速度: {avg_pages_per_sec:.2f} 页/秒")
        print(f"   📊 汇总报告已保存: {summary_file}")

    return results

def main():
    """主函数"""
    print("🎯 MinerU PDF批量性能分析工具")
    print("=" * 50)

    if len(sys.argv) < 2:
        print("\n用法:")
        print("  python batch_analyzer.py <PDF目录路径> [选项]")
        print("\n选项:")
        print("  --dpi <数值>     设置DPI分辨率 (默认200)")
        print("  --max-files <数量> 限制处理的文件数量")
        print("\n示例:")
        print("  python batch_analyzer.py /path/to/pdfs/")
        print("  python batch_analyzer.py /path/to/pdfs/ --dpi 300")
        print("  python batch_analyzer.py /path/to/pdfs/ --max-files 10")
        return

    pdf_directory = sys.argv[1]
    dpi = 200
    max_files = None

    # 解析参数
    for i in range(2, len(sys.argv)):
        if sys.argv[i] == "--dpi":
            if i + 1 < len(sys.argv):
                try:
                    dpi = int(sys.argv[i + 1])
                except ValueError:
                    print(f"❌ --dpi 后面需要是数字，但得到了: {sys.argv[i + 1]}")
                    return
        elif sys.argv[i] == "--max-files":
            if i + 1 < len(sys.argv):
                try:
                    max_files = int(sys.argv[i + 1])
                except ValueError:
                    print(f"❌ --max-files 后面需要是数字，但得到了: {sys.argv[i + 1]}")
                    return

    print(f"🚀 开始批量分析: {pdf_directory}")
    print(f"📋 参数: DPI={dpi}, 最大文件数={max_files if max_files else '无'}")

    # 执行分析
    results = analyze_pdf_directory(pdf_directory, dpi, max_files)

    print(f"\n🎉 批量分析完成! 共处理 {len(results)} 个PDF文件")

if __name__ == "__main__":
    main()