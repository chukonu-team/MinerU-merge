#!/usr/bin/env python3
"""
MinerU批量测试脚本 - 对比单独处理和批量处理的性能
使用doc_analyze进行逐个处理 vs batch_doc_analyze进行批量处理
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# 添加mineru模块到路径
sys.path.insert(0, '/home/ubuntu/MinerU')

from demo.demo import do_parse, _process_output, parse_doc
from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2, prepare_env, read_fn
from mineru.data.data_reader_writer import FileBasedDataWriter
from mineru.backend.vlm.vlm_analyze import doc_analyze, batch_doc_analyze
from mineru.utils.enum_class import MakeMode
from mineru.utils.guess_suffix_or_lang import guess_suffix_by_path
from mineru.utils.pdf_image_tools import load_images_from_pdf
from mineru.utils.enum_class import ImageType


def get_pdf_files(demo_dir):
    """获取demo目录中的所有PDF文件"""
    pdf_files = []
    demo_path = Path(demo_dir)

    if not demo_path.exists():
        print(f"Demo目录不存在: {demo_dir}")
        return pdf_files

    # 查找所有PDF文件
    for pdf_file in demo_path.glob("*.pdf"):
        if pdf_file.is_file():
            pdf_files.append(pdf_file)

    return sorted(pdf_files)


def test_single_processing(pdf_files, output_dir, backend="vlm-vllm-engine"):
    """
    测试1: 单独处理模式 - 逐个使用doc_analyze处理每个PDF
    参考demo.py的实现方式
    """
    print(f"\n{'='*80}")
    print("🔧 测试1: 单独处理模式 (doc_analyze)")
    print(f"后端: {backend}")
    print(f"开始时间: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*80}")

    total_start_time = time.time()
    results = []

    for idx, pdf_path in enumerate(pdf_files):
        print(f"\n处理PDF {idx+1}/{len(pdf_files)}: {pdf_path.name}")
        start_time = time.time()

        try:
            # 读取PDF文件
            pdf_bytes = read_fn(pdf_path)
            pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)
            pdf_file_name = pdf_path.stem

            # 准备输出目录
            local_image_dir, local_md_dir = prepare_env(output_dir / "single_processing" / pdf_file_name, pdf_file_name, "vlm")
            image_writer, md_writer = FileBasedDataWriter(local_image_dir), FileBasedDataWriter(local_md_dir)

            print(f"  📁 输出目录: {local_md_dir}")

            # 使用doc_analyze处理单个PDF
            middle_json, infer_result = doc_analyze(
                pdf_bytes,
                image_writer=image_writer,
                backend=backend[4:],  # 去掉"vlm-"前缀
                server_url=None
            )

            # 处理输出文件（参考demo.py的_process_output）
            pdf_info = middle_json["pdf_info"]
            _process_output(
                pdf_info, pdf_bytes, pdf_file_name, local_md_dir, local_image_dir,
                md_writer, f_draw_layout_bbox=True, f_draw_span_bbox=False, f_dump_orig_pdf=True,
                f_dump_md=True, f_dump_content_list=True, f_dump_middle_json=True, f_dump_model_output=True,
                f_make_md_mode=MakeMode.MM_MD, middle_json=middle_json, model_output=infer_result, is_pipeline=False
            )

            processing_time = time.time() - start_time

            # 统计生成的文件
            output_files = list(Path(local_md_dir).rglob("*")) if Path(local_md_dir).exists() else []
            md_files = [f for f in output_files if f.suffix == '.md']
            json_files = [f for f in output_files if f.suffix == '.json']
            img_files = [f for f in output_files if f.suffix.lower() in ['.jpg', '.jpeg', '.png']]

            result = {
                'pdf_name': pdf_file_name,
                'status': 'success',
                'processing_time': processing_time,
                'output_files': len(output_files),
                'md_files': len(md_files),
                'json_files': len(json_files),
                'img_files': len(img_files),
                'output_dir': str(local_md_dir)
            }

            results.append(result)
            print(f"  ✅ 处理完成: {processing_time:.2f}s, 生成 {len(output_files)} 个文件")
            print(f"     - Markdown: {len(md_files)}, JSON: {len(json_files)}, Images: {len(img_files)}")

        except Exception as e:
            processing_time = time.time() - start_time
            print(f"  ❌ 处理失败: {e}")
            results.append({
                'pdf_name': pdf_path.stem,
                'status': 'error',
                'error': str(e),
                'processing_time': processing_time
            })

    total_time = time.time() - total_start_time
    successful_results = [r for r in results if r['status'] == 'success']

    print(f"\n📊 单独处理统计:")
    print(f"  总处理时间: {total_time:.2f}s")
    print(f"  成功处理: {len(successful_results)}/{len(pdf_files)}")

    if successful_results:
        avg_time = sum(r['processing_time'] for r in successful_results) / len(successful_results)
        total_files = sum(r['output_files'] for r in successful_results)
        total_pages = sum(len(md_writer) for md_writer in [0])  # 这里可以改进

        print(f"  平均处理时间: {avg_time:.2f}s/PDF")
        print(f"  总生成文件: {total_files}个")

    return results, total_time


def test_batch_processing(pdf_files, output_dir, backend="vlm-vllm-engine"):
    """
    测试2: 批量处理模式 - 使用batch_doc_analyze一次性处理所有PDF
    """
    print(f"\n{'='*80}")
    print("🚀 测试2: 批量处理模式 (batch_doc_analyze)")
    print(f"后端: {backend}")
    print(f"开始时间: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*80}")

    total_start_time = time.time()

    try:
        # 准备所有PDF的字节数据
        pdf_bytes_list = []
        pdf_file_names = []

        for pdf_path in pdf_files:
            pdf_bytes = read_fn(pdf_path)
            pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)
            pdf_bytes_list.append(pdf_bytes)
            pdf_file_names.append(pdf_path.stem)
            print(f"  📄 加载成功: {pdf_path.name}")

        print(f"\n🔄 开始批量处理 {len(pdf_bytes_list)} 个PDF...")

        # 准备图像写入器列表
        image_writers = []
        output_dirs = []

        for pdf_file_name in pdf_file_names:
            local_image_dir, local_md_dir = prepare_env(output_dir / "batch_processing" / pdf_file_name, pdf_file_name, "vlm")
            image_writer = FileBasedDataWriter(local_image_dir)
            image_writers.append(image_writer)
            output_dirs.append((local_image_dir, local_md_dir))

        # 使用batch_doc_analyze批量处理
        all_middle_json, batch_results = batch_doc_analyze(
            pdf_bytes_list=pdf_bytes_list,
            image_writer_list=image_writers,
            backend=backend[4:],  # 去掉"vlm-"前缀
            server_url=None
        )

        batch_processing_time = time.time() - total_start_time

        print(f"✅ 批量推理完成: {batch_processing_time:.2f}s")

        # 处理输出文件
        results = []

        # batch_results包含所有页面的结果，需要按PDF分割
        # 首先计算每个PDF的页数
        images_count_per_pdf = []
        for pdf_bytes in pdf_bytes_list:
            images_list, _ = load_images_from_pdf(pdf_bytes, image_type=ImageType.PIL)
            images_count_per_pdf.append(len(images_list))

        # 分割batch_results
        result_start_idx = 0
        for idx, (pdf_file_name, middle_json, (local_image_dir, local_md_dir)) in enumerate(zip(pdf_file_names, all_middle_json, output_dirs)):
            print(f"\n📝 处理输出文件: {pdf_file_name}")

            try:
                md_writer = FileBasedDataWriter(local_md_dir)
                pdf_info = middle_json["pdf_info"]
                pdf_bytes = pdf_bytes_list[idx]

                # 获取当前PDF的推理结果
                current_pdf_pages = images_count_per_pdf[idx]
                current_result = batch_results[result_start_idx:result_start_idx + current_pdf_pages]
                result_start_idx += current_pdf_pages

                _process_output(
                    pdf_info, pdf_bytes, pdf_file_name, local_md_dir, local_image_dir,
                    md_writer, f_draw_layout_bbox=True, f_draw_span_bbox=False, f_dump_orig_pdf=True,
                    f_dump_md=True, f_dump_content_list=True, f_dump_middle_json=True, f_dump_model_output=True,
                    f_make_md_mode=MakeMode.MM_MD, middle_json=middle_json, model_output=current_result, is_pipeline=False
                )

                # 统计生成的文件
                output_files = list(Path(local_md_dir).rglob("*")) if Path(local_md_dir).exists() else []
                md_files = [f for f in output_files if f.suffix == '.md']
                json_files = [f for f in output_files if f.suffix == '.json']
                img_files = [f for f in output_files if f.suffix.lower() in ['.jpg', '.jpeg', '.png']]

                results.append({
                    'pdf_name': pdf_file_name,
                    'status': 'success',
                    'processing_time': batch_processing_time / len(pdf_files),  # 平均时间
                    'output_files': len(output_files),
                    'md_files': len(md_files),
                    'json_files': len(json_files),
                    'img_files': len(img_files),
                    'output_dir': str(local_md_dir)
                })

                print(f"  ✅ 输出完成: 生成 {len(output_files)} 个文件")
                print(f"     - Markdown: {len(md_files)}, JSON: {len(json_files)}, Images: {len(img_files)}")

            except Exception as e:
                print(f"  ❌ 输出处理失败: {e}")
                results.append({
                    'pdf_name': pdf_file_name,
                    'status': 'output_error',
                    'error': str(e),
                    'processing_time': 0
                })

        # 关闭所有写入器 (FileBasedDataWriter没有close方法，不需要显式关闭)
        pass

        return results, batch_processing_time, {}

    except Exception as e:
        print(f"❌ 批量处理失败: {e}")
        import traceback
        traceback.print_exc()
        return [], 0, {}


def run_performance_comparison():
    """运行性能对比测试"""
    print("🚀 MinerU VLM批量处理性能对比测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 设置路径
    demo_dir = "/home/ubuntu/MinerU/demo/pdfs"
    output_base_dir = Path("/home/ubuntu/MinerU/vlm_performance_test")
    output_base_dir.mkdir(exist_ok=True)

    # 获取PDF文件
    pdf_files = get_pdf_files(demo_dir)
    if not pdf_files:
        print("❌ 未找到PDF文件")
        return

    # 限制测试文件数量
    max_files = min(3, len(pdf_files))
    test_pdf_files = pdf_files[:max_files]

    print(f"\n📄 选择测试文件 ({max_files}个):")
    for i, pdf_file in enumerate(test_pdf_files, 1):
        file_size = pdf_file.stat().st_size / 1024 / 1024  # MB
        print(f"  {i}. {pdf_file.name} ({file_size:.2f} MB)")

    # 使用vlm-vllm-engine后端
    backend = "vlm-vllm-engine"

    # 测试1: 单独处理
    single_results, single_total_time = test_single_processing(test_pdf_files, output_base_dir, backend)

    # 测试2: 批量处理 (暂时注释掉，先确保单独处理正常工作)
    # batch_results, batch_total_time, performance_stats = test_batch_processing(test_pdf_files, output_base_dir, backend)
    # 获取批量处理的推理结果数量
    # batch_pages_count = len(batch_results) if batch_results else 0
    batch_results = []
    batch_total_time = 0
    batch_pages_count = 0

    # 性能对比分析
    print(f"\n{'='*80}")
    print("🏆 性能对比分析")
    print(f"{'='*80}")

    successful_single = [r for r in single_results if r['status'] == 'success']
    successful_batch = [r for r in batch_results if r['status'] == 'success']

    print(f"📈 单独处理统计:")
    print(f"  成功处理: {len(successful_single)}/{len(test_pdf_files)}个PDF")
    print(f"  总处理时间: {single_total_time:.2f}s")
    if successful_single:
        avg_time = sum(r['processing_time'] for r in successful_single) / len(successful_single)
        total_files = sum(r['output_files'] for r in successful_single)
        print(f"  平均处理时间: {avg_time:.2f}s/PDF")
        print(f"  总生成文件: {total_files}个")

    print(f"\n📊 批量处理统计:")
    print(f"  处理PDF数量: {len(test_pdf_files)}")
    print(f"  总处理时间: {batch_total_time:.2f}s")
    print(f"  总图像数量: {batch_pages_count}")
    if batch_total_time > 0 and batch_pages_count > 0:
        print(f"  推理速度: {batch_pages_count/batch_total_time:.2f}页/s")

    # 性能提升计算
    if successful_single and successful_batch and batch_total_time > 0:
        single_time_sum = sum(r['processing_time'] for r in successful_single)
        speedup = single_time_sum / batch_total_time
        time_saved = single_time_sum - batch_total_time
        efficiency_gain = (time_saved / single_time_sum) * 100

        print(f"\n🎯 性能提升:")
        print(f"  单独处理总时间: {single_time_sum:.2f}s")
        print(f"  批量处理总时间: {batch_total_time:.2f}s")
        print(f"  加速比: {speedup:.2f}x")
        print(f"  节省时间: {time_saved:.2f}s ({efficiency_gain:.1f}%)")

        if speedup > 1:
            print(f"  ✅ 批量处理更高效，提升了 {speedup:.2f} 倍性能")
        else:
            print(f"  ⚠️  批量处理性能提升有限")

    # 详细结果对比
    print(f"\n📋 详细处理结果:")
    print(f"{'PDF文件':<20} {'单独处理':<15} {'批量处理':<15} {'状态':<10}")
    print(f"{'-'*60}")

    for pdf_file in test_pdf_files:
        single_result = next((r for r in single_results if r['pdf_name'] == pdf_file.stem), None)
        batch_result = next((r for r in batch_results if r['pdf_name'] == pdf_file.stem), None)

        single_time = f"{single_result['processing_time']:.2f}s" if single_result and single_result['status'] == 'success' else "失败"
        batch_time = f"{batch_result['processing_time']:.2f}s" if batch_result and batch_result['status'] == 'success' else "失败"
        status = "✅" if (single_result and single_result['status'] == 'success' and
                         batch_result and batch_result['status'] == 'success') else "⚠️"

        print(f"{pdf_file.stem:<20} {single_time:<15} {batch_time:<15} {status:<10}")

    print(f"\n🎁 所有输出文件保存在: {output_base_dir}")
    print(f"🎉 性能对比测试完成! 时间: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    run_performance_comparison()