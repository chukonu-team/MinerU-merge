#!/usr/bin/env python3
"""
分步处理测试 - 使用doc_analyze逐个处理PDF文件
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# 添加mineru模块到路径
sys.path.insert(0, '/home/ubuntu/MinerU')

from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2, prepare_env, read_fn
from mineru.data.data_reader_writer import FileBasedDataWriter
from mineru.backend.vlm.vlm_analyze import doc_analyze
from mineru.utils.guess_suffix_or_lang import guess_suffix_by_path
from demo.demo import _process_output
from mineru.utils.enum_class import MakeMode


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


def main():
    """分步处理测试"""
    print("🚀 分步处理测试 (doc_analyze)")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # 设置路径
    demo_dir = "/home/ubuntu/MinerU/demo/pdfs"
    output_base_dir = Path("/home/ubuntu/MinerU/batch_vs_step_step")
    output_base_dir.mkdir(exist_ok=True)

    # 获取PDF文件
    pdf_files = get_pdf_files(demo_dir)
    if not pdf_files:
        print("❌ 未找到PDF文件")
        return

    # 测试3个文件（与批量处理测试相同）
    max_files = min(3, len(pdf_files))
    test_pdf_files = pdf_files[:max_files]

    print(f"📄 测试文件 ({max_files}个):")
    total_size = 0
    for i, pdf_file in enumerate(test_pdf_files, 1):
        file_size = pdf_file.stat().st_size / 1024 / 1024  # MB
        total_size += file_size
        print(f"  {i}. {pdf_file.name} ({file_size:.2f} MB)")
    print(f"总大小: {total_size:.2f} MB")

    # 使用vlm-vllm-engine后端
    backend = "vlm-vllm-engine"

    try:
        # 记录总开始时间
        total_start_time = time.time()

        # 统计变量
        total_pages_processed = 0
        total_files_generated = 0
        processing_times = []

        print(f"\n🔄 开始分步处理 {len(test_pdf_files)} 个PDF...")
        print(f"后端: {backend}")

        # 逐个处理PDF
        for idx, pdf_path in enumerate(test_pdf_files):
            print(f"\n{'-'*60}")
            print(f"处理PDF {idx+1}/{len(test_pdf_files)}: {pdf_path.name}")
            print(f"{'-'*60}")

            # 记录单个PDF处理开始时间
            pdf_start_time = time.time()

            # 读取PDF文件
            pdf_bytes = read_fn(pdf_path)
            pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)
            pdf_file_name = pdf_path.stem

            print(f"📖 已加载: {pdf_path.name}")

            # 准备输出目录
            local_image_dir, local_md_dir = prepare_env(output_base_dir / pdf_file_name, pdf_file_name, "vlm")
            image_writer, md_writer = FileBasedDataWriter(local_image_dir), FileBasedDataWriter(local_md_dir)

            print(f"📁 输出目录: {local_md_dir}")

            # 使用doc_analyze处理单个PDF
            print(f"🤖 开始推理处理...")
            middle_json, infer_result = doc_analyze(
                pdf_bytes,
                image_writer=image_writer,
                backend=backend[4:],  # 去掉"vlm-"前缀
                server_url=None
            )

            # 处理输出文件
            print(f"📝 生成输出文件...")
            pdf_info = middle_json["pdf_info"]
            _process_output(
                pdf_info, pdf_bytes, pdf_file_name, local_md_dir, local_image_dir,
                md_writer, f_draw_layout_bbox=True, f_draw_span_bbox=False, f_dump_orig_pdf=True,
                f_dump_md=True, f_dump_content_list=True, f_dump_middle_json=True, f_dump_model_output=True,
                f_make_md_mode=MakeMode.MM_MD, middle_json=middle_json, model_output=infer_result, is_pipeline=False
            )

            # 记录单个PDF处理结束时间
            pdf_end_time = time.time()
            pdf_processing_time = pdf_end_time - pdf_start_time
            processing_times.append(pdf_processing_time)

            # 统计结果
            pages = len(middle_json["pdf_info"])
            total_pages_processed += pages

            # 统计生成的文件数量
            if Path(local_md_dir).exists():
                output_files = list(Path(local_md_dir).rglob("*"))
                total_files_generated += len(output_files)
                md_files = [f for f in output_files if f.suffix == '.md']
                json_files = [f for f in output_files if f.suffix == '.json']
                img_files = [f for f in output_files if f.suffix.lower() in ['.jpg', '.jpeg', '.png']]

                print(f"✅ 处理完成!")
                print(f"  处理时间: {pdf_processing_time:.2f} 秒")
                print(f"  页数: {pages}")
                print(f"  生成文件: {len(output_files)} 个")
                print(f"    - Markdown: {len(md_files)}")
                print(f"    - JSON: {len(json_files)}")
                print(f"    - 图片: {len(img_files)}")

        # 记录总结束时间
        total_end_time = time.time()
        step_processing_time = total_end_time - total_start_time

        print(f"\n✅ 分步处理完成!")

        print(f"\n📊 处理结果统计:")
        print(f"  处理PDF数量: {len(test_pdf_files)}")
        print(f"  总页数: {total_pages_processed}")
        print(f"  总处理时间: {step_processing_time:.2f} 秒")

        # 计算各种平均值
        avg_time_per_pdf = sum(processing_times) / len(processing_times)
        avg_time_per_page = step_processing_time / total_pages_processed

        print(f"  平均每PDF: {avg_time_per_pdf:.2f} 秒")
        print(f"  平均每页: {avg_time_per_page:.2f} 秒")
        if total_pages_processed > 0:
            print(f"  处理速度: {total_pages_processed/step_processing_time:.2f} 页/秒")
        print(f"  总生成文件: {total_files_generated} 个")

        # 显示每个PDF的详细时间
        print(f"\n⏱️ 各PDF处理时间:")
        for i, (pdf_file, proc_time) in enumerate(zip(test_pdf_files, processing_times)):
            print(f"  {i+1}. {pdf_file.name}: {proc_time:.2f} 秒")
        print(f"  最快: {min(processing_times):.2f} 秒")
        print(f"  最慢: {max(processing_times):.2f} 秒")
        print(f"  方差: {max(processing_times) - min(processing_times):.2f} 秒")

        # 保存结果到文件
        results_file = output_base_dir / "step_results.txt"
        with open(results_file, 'w', encoding='utf-8') as f:
            f.write(f"分步处理测试结果\n")
            f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"处理文件: {', '.join([pdf.name for pdf in test_pdf_files])}\n")
            f.write(f"总处理时间: {step_processing_time:.2f} 秒\n")
            f.write(f"平均每PDF: {avg_time_per_pdf:.2f} 秒\n")
            f.write(f"处理速度: {total_pages_processed/step_processing_time:.2f} 页/秒\n")
            f.write(f"总生成文件: {total_files_generated} 个\n\n")
            f.write(f"各PDF处理时间:\n")
            for i, (pdf_file, proc_time) in enumerate(zip(test_pdf_files, processing_times)):
                f.write(f"  {i+1}. {pdf_file.name}: {proc_time:.2f} 秒\n")

        print(f"\n💾 结果已保存到: {results_file}")
        print(f"🎁 输出目录: {output_base_dir}")
        print(f"🎉 分步处理测试完成!")

    except Exception as e:
        print(f"❌ 分步处理失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()