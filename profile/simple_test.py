#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的PDF解析性能测试脚本
快速测试load_images_from_pdf函数的性能
"""

import os
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mineru.utils.pdf_image_tools import load_images_from_pdf
from mineru.utils.enum_class import ImageType
try:
    import pypdfium2 as pdfium
except ImportError:
    print("❌ pypdfium2 not installed. Please install it with: pip install pypdfium2")
    sys.exit(1)


def quick_pdf_test(pdf_path: str, dpi: int = 200, max_pages: int = None):
    """
    快速测试PDF解析性能

    Args:
        pdf_path: PDF文件路径
        dpi: 图像分辨率
        max_pages: 最大处理页数，None表示处理所有页面
    """
    print(f"🚀 开始测试: {pdf_path}")
    print("-" * 50)

    # 1. 基本文件信息
    if not os.path.exists(pdf_path):
        print(f"❌ 文件不存在: {pdf_path}")
        return

    file_size = os.path.getsize(pdf_path)
    print(f"📄 文件大小: {file_size / 1024 / 1024:.2f} MB")

    # 2. 读取文件
    print("📖 读取PDF文件...")
    read_start = time.time()
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    read_time = time.time() - read_start
    print(f"⏱️  文件读取耗时: {read_time:.3f}s")

    # 3. 获取PDF信息
    print("🔍 分析PDF信息...")
    info_start = time.time()
    pdf_doc = pdfium.PdfDocument(pdf_bytes)
    total_pages = len(pdf_doc)

    # 确定处理页数
    end_page = total_pages - 1
    if max_pages is not None:
        end_page = min(max_pages - 1, total_pages - 1)
        print(f"📋 限制处理页数为: {max_pages} 页")

    actual_pages = end_page + 1
    print(f"📋 总页数: {total_pages}, 将处理: {actual_pages} 页")

    pdf_doc.close()
    info_time = time.time() - info_start
    print(f"⏱️  信息获取耗时: {info_time:.3f}s")

    # 4. 核心性能测试 - load_images_from_pdf
    print(f"🎯 开始核心性能测试 (DPI={dpi})...")
    print("   这可能需要一些时间，请耐心等待...")

    load_start = time.time()

    try:
        images_list, pdf_doc = load_images_from_pdf(
            pdf_bytes=pdf_bytes,
            dpi=dpi,
            start_page_id=0,
            end_page_id=end_page,
            image_type=ImageType.PIL,
            threads=4
        )

        load_time = time.time() - load_start
        images_count = len(images_list)

        print(f"✅ 测试完成!")
        print(f"⏱️  load_images_from_pdf 耗时: {load_time:.3f}s")
        print(f"🖼️  生成图像数量: {images_count}")
        print(f"📊 平均每页耗时: {load_time / actual_pages:.3f}s")
        print(f"🚀 处理速度: {actual_pages / load_time:.2f} 页/秒")

        # 5. 性能总结
        total_time = read_time + info_time + load_time
        print(f"\n📈 性能总结:")
        print(f"   总耗时: {total_time:.3f}s")
        print(f"   - 文件读取: {read_time:.3f}s ({read_time/total_time*100:.1f}%)")
        print(f"   - 信息获取: {info_time:.3f}s ({info_time/total_time*100:.1f}%)")
        print(f"   - 图像解析: {load_time:.3f}s ({load_time/total_time*100:.1f}%)")

        # 6. 性能指标
        print(f"\n📊 关键指标:")
        print(f"   文件大小: {file_size / 1024 / 1024:.2f} MB")
        print(f"   处理速度: {actual_pages / load_time:.2f} 页/秒")
        print(f"   数据吞吐量: {file_size / 1024 / 1024 / load_time:.2f} MB/s")
        print(f"   每页平均大小: {file_size / actual_pages / 1024:.1f} KB")

        # 关闭文档
        pdf_doc.close()

        return {
            'pdf_path': pdf_path,
            'file_size_mb': file_size / 1024 / 1024,
            'total_pages': total_pages,
            'processed_pages': actual_pages,
            'images_count': images_count,
            'dpi': dpi,
            'read_time': read_time,
            'info_time': info_time,
            'load_time': load_time,
            'total_time': total_time,
            'pages_per_second': actual_pages / load_time,
            'throughput_mbps': file_size / 1024 / 1024 / load_time
        }

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return None


def compare_dpi_performance(pdf_path: str, dpi_list: list = [150, 200, 300]):
    """
    比较不同DPI下的性能

    Args:
        pdf_path: PDF文件路径
        dpi_list: DPI列表
    """
    print(f"🔬 DPI性能对比测试: {pdf_path}")
    print("=" * 60)

    results = []

    for dpi in dpi_list:
        print(f"\n🎯 测试 DPI = {dpi}")
        result = quick_pdf_test(pdf_path, dpi=dpi)
        if result:
            results.append(result)

    # 输出对比结果
    if len(results) > 1:
        print(f"\n📊 DPI性能对比结果:")
        print("-" * 60)
        print(f"{'DPI':<8} {'耗时(s)':<10} {'速度(页/s)':<12} {'吞吐量(MB/s)':<15} {'每页耗时(s)':<12}")
        print("-" * 60)

        for result in results:
            print(f"{result['dpi']:<8} {result['load_time']:<10.3f} "
                  f"{result['pages_per_second']:<12.2f} {result['throughput_mbps']:<15.2f} "
                  f"{result['load_time']/result['processed_pages']:<12.3f}")


def batch_test_directory(
        pdf_directory: str,
        dpi_list: list = [200],
        max_files: int = None,
        pattern: str = "*.pdf"
    ):
        """
        批量测试目录中的PDF文件

        Args:
            pdf_directory: PDF文件目录
            dpi_list: 要测试的DPI列表
            max_files: 最大处理文件数
            pattern: 文件匹配模式
        """
        print(f"🚀 批量测试PDF目录: {pdf_directory}")
        print(f"📋 测试DPI: {dpi_list}")
        print(f"📄 文件模式: {pattern}")
        if max_files:
            print(f"🔢 限制文件数: {max_files}")
        print("=" * 60)

        if not os.path.exists(pdf_directory):
            print(f"❌ 目录不存在: {pdf_directory}")
            return []

        # 查找PDF文件
        import glob
        pdf_files = glob.glob(os.path.join(pdf_directory, pattern))
        pdf_files.sort()  # 按文件名排序

        if not pdf_files:
            print(f"❌ 在目录 {pdf_directory} 中未找到匹配的PDF文件")
            return []

        if max_files:
            pdf_files = pdf_files[:max_files]

        print(f"📄 找到 {len(pdf_files)} 个PDF文件")

        # 存储所有测试结果
        all_results = []

        # 测试每个DPI配置
        for dpi in dpi_list:
            print(f"\n🎯 测试 DPI = {dpi}")
            print("-" * 40)

            dpi_results = []
            start_time = time.time()

            for i, pdf_path in enumerate(pdf_files, 1):
                print(f"📁 [{i}/{len(pdf_files)}] 测试: {os.path.basename(pdf_path)}")

                try:
                    result = quick_pdf_test(pdf_path, dpi=dpi, max_pages=None)
                    if result:
                        result['dpi'] = dpi
                        dpi_results.append(result)
                except Exception as e:
                    print(f"❌ 测试失败: {e}")
                    continue

            dpi_time = time.time() - start_time
            print(f"\n✅ DPI {dpi} 测试完成!")
            print(f"   成功文件: {len(dpi_results)}/{len(pdf_files)}")
            print(f"   测试耗时: {dpi_time:.3f}s")

            if dpi_results:
                # 计算DPI级别统计
                total_pages = sum(r['processed_pages'] for r in dpi_results)
                total_size_mb = sum(r['pdf_size_mb'] for r in dpi_results)
                total_load_time = sum(r['load_time'] for r in dpi_results)
                avg_pages_per_sec = total_pages / total_load_time if total_load_time > 0 else 0
                throughput_mbps = total_size_mb / total_load_time if total_load_time > 0 else 0

                print(f"   📊 DPI {dpi} 统计:")
                print(f"      总页数: {total_pages}")
                print(f"      总大小: {total_size_mb:.2f} MB")
                print(f"      总耗时: {total_load_time:.3f}s")
                print(f"      平均速度: {avg_pages_per_sec:.2f} 页/秒")
                print(f"      处理吞吐量: {throughput_mbps:.2f} MB/s")

                all_results.extend(dpi_results)

        # 生成批量测试汇总
        _generate_batch_test_summary(pdf_directory, all_results)

        return all_results


def _generate_batch_test_summary(pdf_directory: str, results: list):
        """生成批量测试汇总报告"""
        if not results:
            return

        print(f"\n" + "=" * 80)
        print(f"📈 批量测试汇总 - 目录: {pdf_directory}")
        print("=" * 80)

        # 按DPI分组统计
        dpi_stats = {}
        for r in results:
            dpi = r['dpi']
            if dpi not in dpi_stats:
                dpi_stats[dpi] = {
                    'files': 0,
                    'pages': 0,
                    'size_mb': 0,
                    'total_time': 0,
                    'load_time': 0
                }
            dpi_stats[dpi]['files'] += 1
            dpi_stats[dpi]['pages'] += r['processed_pages']
            dpi_stats[dpi]['size_mb'] += r['pdf_size_mb']
            dpi_stats[dpi]['total_time'] += r['total_time']
            dpi_stats[dpi]['load_time'] += r['load_time']

        # 打印DPI对比表
        print(f"\n🎯 DPI性能对比:")
        print("-" * 80)
        print(f"{'DPI':<8} {'文件数':<8} {'总页数':<10} {'总大小(MB)':<12} {'总耗时(s)':<12} {'速度(页/s)':<12} {'吞吐量(MB/s)':<15}")
        print("-" * 80)

        for dpi in sorted(dpi_stats.keys()):
            stats = dpi_stats[dpi]
            speed = stats['pages'] / stats['load_time'] if stats['load_time'] > 0 else 0
            throughput = stats['size_mb'] / stats['load_time'] if stats['load_time'] > 0 else 0
            print(f"{dpi:<8} {stats['files']:<8} {stats['pages']:<10} {stats['size_mb']:<12.2f} {stats['load_time']:<12.3f} {speed:<12.2f} {throughput:<15.2f}")

        # 找出最佳DPI配置
        print(f"\n🏆 性能最优配置:")
        best_speed_dpi = max(dpi_stats.keys(), key=lambda d:
                          dpi_stats[d]['pages'] / dpi_stats[d]['load_time'] if dpi_stats[d]['load_time'] > 0 else 0)
        best_throughput_dpi = max(dpi_stats.keys(), key=lambda d:
                                dpi_stats[d]['size_mb'] / dpi_stats[d]['load_time'] if dpi_stats[d]['load_time'] > 0 else 0)

        best_speed = dpi_stats[best_speed_dpi]['pages'] / dpi_stats[best_speed_dpi]['load_time']
        best_throughput = dpi_stats[best_throughput_dpi]['size_mb'] / dpi_stats[best_throughput_dpi]['load_time']

        print(f"   🚀 最高处理速度: DPI {best_speed_dpi} ({best_speed:.2f} 页/秒)")
        print(f"   📊 最高吞吐量: DPI {best_throughput_dpi} ({best_throughput:.2f} MB/s)")

        # 找出性能最好和最差的文件
        all_speeds = [(r['pdf_path'], r['processed_pages'] / r['load_time']) for r in results if r['load_time'] > 0]
        if all_speeds:
            fastest_file = max(all_speeds, key=lambda x: x[1])
            slowest_file = min(all_speeds, key=lambda x: x[1])

            print(f"\n📁 文件性能极值:")
            print(f"   🏆 最快文件: {os.path.basename(fastest_file[0])} ({fastest_file[1]:.2f} 页/秒)")
            print(f"   🐌 最慢文件: {os.path.basename(slowest_file[0])} ({slowest_file[1]:.2f} 页/秒)")


def main():
    """主函数"""
    print("🎯 MinerU PDF解析性能快速测试工具")
    print("=" * 50)

    # 检查命令行参数
    if len(sys.argv) < 2:
        print("用法:")
        print("  1. 测试单个PDF文件:")
        print("     python simple_test.py <pdf_file_path>")
        print()
        print("  2. 测试多个PDF文件:")
        print("     python simple_test.py file1.pdf file2.pdf file3.pdf")
        print()
        print("  3. 批量测试目录中的所有PDF:")
        print("     python simple_test.py --directory <pdf_directory>")
        print()
        print("  4. DPI性能对比 (目录模式):")
        print("     python simple_test.py --directory <pdf_directory> --dpi-compare")
        print()
        print("  5. 自定义DPI对比:")
        print("     python simple_test.py --directory <pdf_directory> --dpi-list \"150,200,300\"")
        print()
        print("  6. 限制测试文件数:")
        print("     python simple_test.py --directory <pdf_directory> --max-files 10")
        print()
        print("示例:")
        print("  python simple_test.py /path/to/sample.pdf")
        print("  python simple_test.py /path/to/pdf_directory/ --directory")
        print("  python simple_test.py /path/to/pdf_directory/ --directory --dpi-compare --max-files 5")
        print("  python simple_test.py /path/to/pdf_directory/ --directory --dpi-list \"150,200,300\"")
        return

    args = sys.argv[1:]

    # 目录模式
    if "--directory" in args:
        dir_index = args.index("--directory")
        if dir_index + 1 >= len(args):
            print("❌ --directory 需要指定目录路径")
            return

        pdf_directory = args[dir_index + 1]

        # 解析其他参数
        dpi_compare = "--dpi-compare" in args
        max_files = None
        custom_dpi_list = [200]

        if "--max-files" in args:
            max_files_index = args.index("--max-files")
            if max_files_index + 1 >= len(args):
                print("❌ --max-files 需要指定文件数量")
                return
            try:
                max_files = int(args[max_files_index + 1])
            except ValueError:
                print("❌ --max-files 需要是数字")
                return

        if "--dpi-list" in args:
            dpi_list_index = args.index("--dpi-list")
            if dpi_list_index + 1 >= len(args):
                print("❌ --dpi-list 需要指定DPI列表")
                return
            try:
                custom_dpi_list = [int(d.strip()) for d in args[dpi_list_index + 1].split(',')]
            except ValueError:
                print("❌ --dpi-list 格式错误，应为逗号分隔的数字，如 \"150,200,300\"")
                return

        if not os.path.isdir(pdf_directory):
            print(f"❌ 目录不存在: {pdf_directory}")
            return

        # 执行目录测试
        if dpi_compare:
            # 标准DPI对比
            batch_test_directory(pdf_directory, [150, 200, 300], max_files, "*.pdf")
        elif len(custom_dpi_list) > 1:
            # 自定义DPI对比
            batch_test_directory(pdf_directory, custom_dpi_list, max_files, "*.pdf")
        else:
            # 单一DPI批量测试
            batch_test_directory(pdf_directory, custom_dpi_list, max_files, "*.pdf")

        return

    # 单文件模式
    pdf_files = []

    # 过滤选项参数
    for arg in args:
        if not arg.startswith("--"):
            pdf_files.append(arg)

    if not pdf_files:
        print("❌ 请指定要测试的PDF文件路径")
        return

    # 检查是否需要进行DPI对比
    dpi_compare = '--dpi-compare' in args
    if dpi_compare:
        pdf_files = [f for f in pdf_files if f != '--dpi-compare']

    # 测试每个PDF文件
    for pdf_path in pdf_files:
        if not os.path.exists(pdf_path):
            print(f"❌ 文件不存在: {pdf_path}")
            continue

        if dpi_compare:
            # 进行DPI性能对比
            compare_dpi_performance(pdf_path)
        else:
            # 进行基本测试
            quick_pdf_test(pdf_path, dpi=200, max_pages=None)

        print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()