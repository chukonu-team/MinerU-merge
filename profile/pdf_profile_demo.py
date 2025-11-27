#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF解析性能分析工具
用于分析load_images_from_pdf函数的CPU瓶颈
"""

import os
import sys
import time
import cProfile
import pstats
import io
from pathlib import Path
from typing import List
from dataclasses import dataclass
import glob
import linecache
import functools

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mineru.utils.pdf_image_tools import load_images_from_pdf


def line_profiler_decorator(func):
    """
    行级性能分析装饰器
    分析函数中每行代码的执行时间
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"\n🔍 开始行级性能分析: {func.__name__}")
        print("=" * 60)

        # 获取函数源代码
        import inspect
        try:
            source_lines = inspect.getsourcelines(func)[0]
            start_line = inspect.getsourcelines(func)[1]
        except Exception as e:
            print(f"❌ 无法获取源代码: {e}")
            return func(*args, **kwargs)

        # 执行函数并记录每行时间
        line_times = {}
        line_counts = {}

        class LineTracer:
            def __init__(self, func_name, source_lines, start_line):
                self.func_name = func_name
                self.source_lines = source_lines
                self.start_line = start_line
                self.line_times = {}
                self.line_counts = {}
                self.last_time = None
                self.last_line = None

            def trace_calls(self, frame, event, arg):
                if event == 'call' and frame.f_code.co_name == func.__name__:
                    return self.trace_lines
                return None

            def trace_lines(self, frame, event, arg):
                if event == 'line':
                    line_no = frame.f_lineno
                    current_time = time.perf_counter()

                    # 如果有上一行，记录其执行时间
                    if self.last_time is not None and self.last_line is not None:
                        execution_time = current_time - self.last_time

                        if self.last_line not in self.line_times:
                            self.line_times[self.last_line] = 0
                            self.line_counts[self.last_line] = 0

                        self.line_times[self.last_line] += execution_time
                        self.line_counts[self.last_line] += 1

                    self.last_time = current_time
                    self.last_line = line_no

                return self.trace_lines

        # 设置跟踪器
        tracer = LineTracer(func.__name__, source_lines, start_line)
        sys.settrace(tracer.trace_calls)

        try:
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            total_time = time.perf_counter() - start_time

            # 恢复跟踪
            sys.settrace(None)

            # 打印行级分析结果
            print(f"\n📊 行级性能分析结果 (总耗时: {total_time:.3f}s)")
            print("-" * 60)
            print(f"{'行号':<6} {'累计时间(s)':<12} {'调用次数':<8} {'平均时间(ms)':<12} {'代码'}")
            print("-" * 60)

            # 按时间排序显示
            sorted_lines = sorted(tracer.line_times.items(), key=lambda x: x[1], reverse=True)

            for line_no, total_time_line in sorted_lines:
                if total_time_line > 0.001:  # 只显示耗时超过1ms的行
                    count = tracer.line_counts[line_no]
                    avg_time_ms = (total_time_line / count) * 1000

                    # 获取源代码
                    if start_line <= line_no < start_line + len(source_lines):
                        line_idx = line_no - start_line
                        if line_idx < len(source_lines):
                            code_line = source_lines[line_idx].strip()
                            # 限制显示长度
                            if len(code_line) > 50:
                                code_line = code_line[:47] + "..."
                    else:
                        code_line = linecache.getline(__file__, line_no).strip()

                    print(f"{line_no:<6} {total_time_line:<12.3f} {count:<8} {avg_time_ms:<12.3f} {code_line}")

            print("-" * 60)
            return result

        except Exception as e:
            sys.settrace(None)
            print(f"❌ 行级分析出错: {e}")
            raise

    return wrapper


@dataclass
class ProfileResult:
    """性能分析结果"""
    pdf_path: str
    total_time: float
    pdf_size_bytes: int
    pdf_pages: int
    images_count: int
    cpu_percent: float
    memory_usage_mb: float
    profile_stats: str
    file_read_time: float
    info_analysis_time: float


class PDFProfiler:
    """PDF解析性能分析器"""

    def __init__(self):
        self.results: List[ProfileResult] = []
        self.total_load_time = 0.0  # 累计 load_images_from_pdf 调用时间
        self.load_call_count = 0    # 调用次数统计

    def profile_pdf_parsing(
        self,
        pdf_path: str,
        dpi: int = 200,
        start_page_id: int = 0,
        end_page_id: int = None,
        image_type: str = "PIL",
        threads: int = 4,
        output_dir: str = "./profile_outputs"
    ) -> ProfileResult:
        """
        分析PDF解析性能

        Args:
            pdf_path: PDF文件路径
            dpi: 图像分辨率
            start_page_id: 起始页码
            end_page_id: 结束页码
            image_type: 图像类型
            threads: 线程数
            output_dir: 输出目录

        Returns:
            ProfileResult: 性能分析结果
        """
        print(f"\n{'='*50}")
        print(f"分析PDF文件: {pdf_path}")
        print(f"参数: dpi={dpi}, threads={threads}, start_page={start_page_id}, end_page={end_page_id}")
        print(f"{'='*50}")

        # 1. 读取PDF文件信息
        print("1. 读取PDF文件...")
        start_time = time.time()

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        # 获取文件大小
        pdf_size_bytes = os.path.getsize(pdf_path)
        print(f"   文件大小: {pdf_size_bytes / 1024 / 1024:.2f} MB")

        # 读取文件内容
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()

        file_read_time = time.time() - start_time
        print(f"   文件读取耗时: {file_read_time:.3f}s")

        # 2. 预览PDF信息
        print("\n2. 预览PDF信息...")
        try:
            import pypdfium2 as pdfium
        except ImportError:
            raise ImportError("pypdfium2 not installed. Please install it with: pip install pypdfium2")
        preview_start = time.time()

        pdf_doc = pdfium.PdfDocument(pdf_bytes)
        pdf_pages = len(pdf_doc)
        if end_page_id is None:
            end_page_id = pdf_pages - 1

        actual_pages = end_page_id - start_page_id + 1
        print(f"   总页数: {pdf_pages}")
        print(f"   将处理页数: {actual_pages} (页码 {start_page_id}-{end_page_id})")

        pdf_doc.close()
        preview_time = time.time() - preview_start
        print(f"   预览耗时: {preview_time:.3f}s")

        # 3. CPU性能分析 - load_images_from_pdf
        print(f"\n3. 开始CPU性能分析 - load_images_from_pdf...")

        # 创建cProfile对象
        profiler = cProfile.Profile()

        # 开始性能分析
        profiler.enable()
        load_start_time = time.time()

        try:
            # 执行目标函数
            images_list, pdf_doc = load_images_from_pdf(
                pdf_bytes=pdf_bytes,
                dpi=dpi,
                start_page_id=start_page_id,
                end_page_id=end_page_id,
                image_type=image_type,
                threads=threads
            )

            load_time = time.time() - load_start_time
            images_count = len(images_list)

            # 累计总调用时间和次数
            self.total_load_time += load_time
            self.load_call_count += 1

            print(f"   解析完成!")
            print(f"   解析耗时: {load_time:.3f}s")
            print(f"   生成图像数量: {images_count}")
            print(f"   平均每页耗时: {load_time / actual_pages:.3f}s")
            print(f"   累计调用次数: {self.load_call_count}")
            print(f"   累计总时间: {self.total_load_time:.3f}s")

        except Exception as e:
            print(f"   解析失败: {e}")
            raise
        finally:
            # 停止性能分析
            profiler.disable()

            # 关闭PDF文档
            if 'pdf_doc' in locals():
                pdf_doc.close()

        # 4. 处理性能分析结果
        print(f"\n4. 处理性能分析结果...")

        # 创建统计结果
        stats_stream = io.StringIO()
        ps = pstats.Stats(profiler, stream=stats_stream)

        # 按累计时间排序
        ps.sort_stats('cumulative')
        ps.print_stats(30)  # 打印前30个最耗时的函数

        # 获取统计信息字符串
        profile_stats = stats_stream.getvalue()

        # 5. 保存结果
        result = ProfileResult(
            pdf_path=pdf_path,
            total_time=load_time,
            pdf_size_bytes=pdf_size_bytes,
            pdf_pages=actual_pages,
            images_count=images_count,
            cpu_percent=0.0,  # 可以后续添加
            memory_usage_mb=0.0,  # 可以后续添加
            profile_stats=profile_stats,
            file_read_time=file_read_time,
            info_analysis_time=preview_time
        )

        self.results.append(result)

        # 保存详细分析结果到文件
        self._save_profile_result(pdf_path, result, output_dir)

        return result

    def _save_profile_result(self, pdf_path: str, result: ProfileResult, output_dir: str):
        """保存性能分析结果到文件"""
        os.makedirs(output_dir, exist_ok=True)

        pdf_name = Path(pdf_path).stem
        timestamp = int(time.time())

        # 保存详细报告
        report_file = os.path.join(output_dir, f"{pdf_name}_profile_{timestamp}.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"PDF解析性能分析报告\n")
            f.write(f"{'='*50}\n\n")
            f.write(f"文件路径: {pdf_path}\n")
            f.write(f"分析时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write(f"性能指标:\n")
            f.write(f"  文件大小: {result.pdf_size_bytes / 1024 / 1024:.2f} MB\n")
            f.write(f"  处理页数: {result.pdf_pages}\n")
            f.write(f"  生成图像数: {result.images_count}\n")
            f.write(f"  总耗时: {result.total_time:.3f}s\n")
            f.write(f"  平均每页耗时: {result.total_time / result.pdf_pages:.3f}s\n")
            f.write(f"  处理速度: {result.pdf_pages / result.total_time:.2f} 页/秒\n\n")

            f.write(f"详细性能分析 (按累计时间排序):\n")
            f.write(f"{'-'*50}\n")
            f.write(result.profile_stats)

        print(f"   详细报告已保存: {report_file}")

        # 保存profile数据用于进一步分析
        profile_data_file = os.path.join(output_dir, f"{pdf_name}_profile_{timestamp}.prof")

        # 这里可以添加保存原始profile数据的代码
        print(f"   Profile数据已保存: {profile_data_file}")

    def profile_pdf_directory(
        self,
        pdf_directory: str,
        dpi: int = 200,
        start_page_id: int = 0,
        end_page_id: int = None,
        image_type: str = "PIL",
        threads: int = 4,
        output_dir: str = "./profile_outputs",
        max_files: int = None,
        pattern: str = "*.pdf"
    ) -> List[ProfileResult]:
        """
        批量分析目录中的PDF文件

        Args:
            pdf_directory: PDF文件目录路径
            dpi: 图像分辨率
            start_page_id: 起始页码
            end_page_id: 结束页码
            image_type: 图像类型
            threads: 线程数
            output_dir: 输出目录
            max_files: 最大处理文件数，None表示处理全部
            pattern: 文件匹配模式

        Returns:
            List[ProfileResult]: 所有文件的分析结果
        """
        print(f"\n🔍 批量分析目录: {pdf_directory}")
        print(f"📋 参数: DPI={dpi}, 线程={threads}, 文件模式={pattern}")
        print("="*60)

        # 查找所有PDF文件
        if not os.path.exists(pdf_directory):
            raise FileNotFoundError(f"目录不存在: {pdf_directory}")

        pdf_files = glob.glob(os.path.join(pdf_directory, pattern))
        pdf_files.sort()  # 按文件名排序

        if not pdf_files:
            print(f"❌ 在目录 {pdf_directory} 中未找到匹配的PDF文件")
            return []

        if max_files:
            pdf_files = pdf_files[:max_files]
            print(f"📄 找到 {len(glob.glob(os.path.join(pdf_directory, pattern)))} 个PDF文件，限制处理前 {max_files} 个")
        else:
            print(f"📄 找到 {len(pdf_files)} 个PDF文件")

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 开始批量分析
        start_time = time.time()

        for i, pdf_path in enumerate(pdf_files, 1):
            print(f"\n📁 [{i}/{len(pdf_files)}] 分析文件: {os.path.basename(pdf_path)}")
            print("-" * 50)

            try:
                result = self.profile_pdf_parsing(
                    pdf_path=pdf_path,
                    dpi=dpi,
                    start_page_id=start_page_id,
                    end_page_id=end_page_id,
                    image_type=image_type,
                    threads=threads,
                    output_dir=output_dir
                )

                # 显示简要结果
                file_size_mb = result.pdf_size_bytes / 1024 / 1024
                pages_per_sec = result.pdf_pages / result.total_time if result.total_time > 0 else 0
                print(f"✅ 完成: {file_size_mb:.2f}MB, {result.pdf_pages}页, {pages_per_sec:.2f}页/秒")

            except Exception as e:
                print(f"❌ 分析失败: {e}")
                continue

        total_batch_time = time.time() - start_time

        # 生成批量分析汇总
        self._generate_batch_summary(pdf_directory, output_dir, total_batch_time)

        return self.results

    def _generate_batch_summary(self, pdf_directory: str, output_dir: str, total_time: float):
        """生成批量分析汇总报告"""
        if not self.results:
            return

        # 计算汇总统计
        total_files = len(self.results)
        total_pages = sum(r.pdf_pages for r in self.results)
        total_size_mb = sum(r.pdf_size_bytes for r in self.results) / 1024 / 1024
        total_processing_time = sum(r.total_time for r in self.results)

        avg_file_size_mb = total_size_mb / total_files if total_files > 0 else 0
        avg_pages_per_file = total_pages / total_files if total_files > 0 else 0
        avg_time_per_file = total_processing_time / total_files if total_files > 0 else 0
        avg_pages_per_sec = total_pages / total_processing_time if total_processing_time > 0 else 0

        # 找出最快和最慢的文件
        fastest = min(self.results, key=lambda r: r.total_time / r.pdf_pages if r.pdf_pages > 0 else float('inf'))
        slowest = max(self.results, key=lambda r: r.total_time / r.pdf_pages if r.pdf_pages > 0 else 0)

        # 生成汇总报告
        summary_file = os.path.join(output_dir, f"batch_summary_{int(time.time())}.txt")

        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("PDF批量解析性能分析汇总报告\n")
            f.write("="*60 + "\n")
            f.write(f"分析目录: {pdf_directory}\n")
            f.write(f"分析时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"分析耗时: {total_time:.3f}s\n\n")

            f.write("📊 总体统计\n")
            f.write("-" * 30 + "\n")
            f.write(f"处理文件数: {total_files}\n")
            f.write(f"总页数: {total_pages}\n")
            f.write(f"总文件大小: {total_size_mb:.2f} MB\n")
            f.write(f"总处理时间: {total_processing_time:.3f}s\n\n")

            f.write("📈 平均指标\n")
            f.write("-" * 30 + "\n")
            f.write(f"平均文件大小: {avg_file_size_mb:.2f} MB\n")
            f.write(f"平均每文件页数: {avg_pages_per_file:.1f}\n")
            f.write(f"平均每文件耗时: {avg_time_per_file:.3f}s\n")
            f.write(f"平均处理速度: {avg_pages_per_sec:.2f} 页/秒\n")
            f.write(f"平均处理吞吐量: {total_size_mb / total_processing_time:.2f} MB/s\n\n")

            f.write("🏆 性能极值\n")
            f.write("-" * 30 + "\n")
            f.write(f"最快文件: {os.path.basename(fastest.pdf_path)} ({fastest.total_time/fastest.pdf_pages:.3f}s/页)\n")
            f.write(f"最慢文件: {os.path.basename(slowest.pdf_path)} ({slowest.total_time/slowest.pdf_pages:.3f}s/页)\n\n")

            f.write("📋 详细结果\n")
            f.write("-" * 30 + "\n")
            f.write(f"{'文件名':<40} {'大小(MB)':<10} {'页数':<6} {'耗时(s)':<10} {'速度(页/s)':<12}\n")
            f.write("-" * 78 + "\n")

            # 按处理速度排序
            sorted_results = sorted(self.results, key=lambda r: r.pdf_pages / r.total_time if r.total_time > 0 else 0, reverse=True)

            for result in sorted_results:
                filename = os.path.basename(result.pdf_path)[:38]
                size_mb = result.pdf_size_bytes / 1024 / 1024
                speed = result.pdf_pages / result.total_time if result.total_time > 0 else 0
                f.write(f"{filename:<40} {size_mb:<10.2f} {result.pdf_pages:<6} {result.total_time:<10.3f} {speed:<12.2f}\n")

        print(f"\n📈 批量分析汇总:")
        print(f"   处理文件数: {total_files}")
        print(f"   总页数: {total_pages}")
        print(f"   总文件大小: {total_size_mb:.2f} MB")
        print(f"   平均处理速度: {avg_pages_per_sec:.2f} 页/秒")
        print(f"   分析耗时: {total_time:.3f}s")
        print(f"   汇总报告已保存: {summary_file}")

    def print_summary(self):
        """打印所有测试的总结"""
        if not self.results:
            print("没有测试结果")
            return

        print(f"\n{'='*60}")
        print("性能分析总结")
        print(f"{'='*60}")

        # 打印 load_images_from_pdf 总调用统计
        if self.load_call_count > 0:
            avg_load_time = self.total_load_time / self.load_call_count
            print(f"\n🔍 load_images_from_pdf 调用统计:")
            print(f"  总调用次数: {self.load_call_count}")
            print(f"  累计总时间: {self.total_load_time:.3f}s")
            print(f"  平均每次调用: {avg_load_time:.3f}s")
            print(f"  总处理页数: {sum(r.pdf_pages for r in self.results)}")
            print(f"  平均每页总时间: {self.total_load_time / sum(r.pdf_pages for r in self.results):.3f}s")
            print("-" * 60)

        for i, result in enumerate(self.results, 1):
            file_size_mb = result.pdf_size_bytes / 1024 / 1024
            print(f"\n测试 {i}: {os.path.basename(result.pdf_path)}")
            print(f"  文件大小: {file_size_mb:.2f} MB")
            print(f"  处理页数: {result.pdf_pages}")
            print(f"  总耗时: {result.total_time:.3f}s")
            print(f"  平均每页耗时: {result.total_time / result.pdf_pages:.3f}s")
            print(f"  处理速度: {result.pdf_pages / result.total_time:.2f} 页/秒")


@line_profiler_decorator
def main():
    """主函数 - 演示如何使用性能分析工具"""

    # 创建性能分析器
    profiler = PDFProfiler()

    # 检查命令行参数
    if len(sys.argv) < 2:
        print("🎯 MinerU PDF解析性能分析工具")
        print("="*60)
        print()
        print("用法:")
        print("  1. 分析单个PDF文件:")
        print("     python pdf_profile_demo.py <pdf_file_path>")
        print()
        print("  2. 分析多个PDF文件:")
        print("     python pdf_profile_demo.py file1.pdf file2.pdf file3.pdf")
        print()
        print("  3. 批量分析目录中的所有PDF:")
        print("     python pdf_profile_demo.py --directory <pdf_directory>")
        print()
        print("  4. 限制处理的PDF数量:")
        print("     python pdf_profile_demo.py --directory <pdf_directory> --max-files 10")
        print()
        print("示例:")
        print("  python pdf_profile_demo.py /path/to/sample.pdf")
        print("  python pdf_profile_demo.py /path/to/pdf_directory/ --directory --max-files 5")
        print()
        return

    # 解析命令行参数
    args = sys.argv[1:]

    if "--directory" in args:
        # 批量处理目录模式
        dir_index = args.index("--directory")
        if dir_index + 1 >= len(args):
            print("❌ --directory 需要指定目录路径")
            return

        pdf_directory = args[dir_index + 1]

        # 检查可选参数
        max_files = None
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

        # 检查是否为目录
        if not os.path.isdir(pdf_directory):
            print(f"❌ 目录不存在: {pdf_directory}")
            return

        # 开始批量分析
        print(f"🚀 开始批量分析PDF目录: {pdf_directory}")
        if max_files:
            print(f"📋 限制处理文件数: {max_files}")

        try:
            results = profiler.profile_pdf_directory(
                pdf_directory=pdf_directory,
                dpi=200,
                start_page_id=0,
                end_page_id=None,
                image_type="PIL",
                threads=4,
                output_dir="./profile_outputs",
                max_files=max_files,
                pattern="*.pdf"
            )

            if results:
                print(f"\n🎉 批量分析完成! 共处理 {len(results)} 个PDF文件")
            else:
                print(f"\n❌ 批量分析完成，但没有找到PDF文件")

        except Exception as e:
            print(f"\n❌ 批量分析失败: {e}")
            return

    else:
        # 单文件模式
        pdf_files = []

        # 过滤掉选项参数
        for arg in args:
            if not arg.startswith("--"):
                pdf_files.append(arg)

        if not pdf_files:
            print("❌ 请指定要分析的PDF文件路径")
            return

        print(f"🚀 开始分析 {len(pdf_files)} 个PDF文件")

        # 分析每个PDF文件
        for pdf_path in pdf_files:
            try:
                result = profiler.profile_pdf_parsing(
                    pdf_path=pdf_path,
                    dpi=200,  # 可以调整这个参数测试不同分辨率
                    start_page_id=0,
                    end_page_id=None,  # 处理所有页面
                    image_type="PIL",
                    threads=4  # 可以调整这个参数测试不同线程数
                )

                print(f"\n✅ 分析完成: {pdf_path}")

            except Exception as e:
                print(f"\n❌ 分析失败: {pdf_path}")
                print(f"错误: {e}")
                continue

        # 打印总结
        profiler.print_summary()


if __name__ == "__main__":
    main()