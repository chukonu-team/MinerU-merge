#!/usr/bin/env python3
"""
批量处理测试 - 使用batch_doc_analyze按页数分批处理多个PDF
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
from mineru.backend.vlm.vlm_analyze import batch_doc_analyze
import pypdfium2  # 用于获取PDF页数


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


def get_pdf_page_count(pdf_path):
    """获取PDF文件的页数"""
    try:
        pdf_bytes = read_fn(pdf_path)
        # 使用pypdfium2计算页数
        pdf_document = pypdfium2.PdfDocument(pdf_bytes)
        page_count = len(pdf_document)
        pdf_document.close()
        return page_count
    except Exception as e:
        print(f"⚠️ 无法获取 {pdf_path.name} 的页数: {e}")
        return 0


def create_batches_by_pages(pdf_files, batch_size):
    """
    根据页数创建批次
    :param pdf_files: PDF文件列表
    :param batch_size: 每批次最大页数
    :return: 批次列表，每个批次包含文件列表和总页数
    """
    batches = []
    current_batch = []
    current_batch_pages = 0

    print(f"📦 按页数分批 (每批最多 {batch_size} 页):")

    for i, pdf_file in enumerate(pdf_files):
        page_count = get_pdf_page_count(pdf_file)

        # 如果单个文件就超过批次大小，单独作为一批
        if page_count >= batch_size:
            if current_batch:  # 先处理当前批次
                batches.append({
                    'files': current_batch.copy(),
                    'total_pages': current_batch_pages,
                    'file_names': [f.stem for f in current_batch]
                })
                print(f"  批次 {len(batches)}: {len(current_batch)} 个文件, {current_batch_pages} 页")
                current_batch = []
                current_batch_pages = 0

            # 大文件单独一批
            batches.append({
                'files': [pdf_file],
                'total_pages': page_count,
                'file_names': [pdf_file.stem]
            })
            print(f"  批次 {len(batches)}: {pdf_file.name}, {page_count} 页 (大文件单独批次)")
            continue

        # 如果当前批次加上这个文件会超过限制，先处理当前批次
        if current_batch_pages + page_count > batch_size:
            batches.append({
                'files': current_batch.copy(),
                'total_pages': current_batch_pages,
                'file_names': [f.stem for f in current_batch]
            })
            print(f"  批次 {len(batches)}: {len(current_batch)} 个文件, {current_batch_pages} 页")
            current_batch = []
            current_batch_pages = 0

        # 添加到当前批次
        current_batch.append(pdf_file)
        current_batch_pages += page_count

    # 处理最后一个批次
    if current_batch:
        batches.append({
            'files': current_batch,
            'total_pages': current_batch_pages,
            'file_names': [f.stem for f in current_batch]
        })
        print(f"  批次 {len(batches)}: {len(current_batch)} 个文件, {current_batch_pages} 页")

    return batches


def main():
    """批量处理测试"""
    print("🚀 批量处理测试 (batch_doc_analyze - 按页数分批)")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # 获取批次大小（环境变量或默认值）
    batch_size = int(os.environ.get('DEFAULT_BATCH_SIZE', '384'))
    print(f"📦 批次大小设置: {batch_size} 页/批次")

    # 设置路径
    demo_dir = "/home/ubuntu/MinerU/demo/pdfs"
    output_base_dir = Path("/home/ubuntu/MinerU/batch_vs_step_batch")
    output_base_dir.mkdir(exist_ok=True)

    # 获取PDF文件
    pdf_files = get_pdf_files(demo_dir)
    if not pdf_files:
        print("❌ 未找到PDF文件")
        return

    # 限制测试文件数量（可选）
    max_files = int(os.environ.get('MAX_FILES', str(len(pdf_files))))
    test_pdf_files = pdf_files[:max_files]

    print(f"\n📄 发现PDF文件 ({len(test_pdf_files)}个):")
    total_size = 0
    total_pages = 0
    for i, pdf_file in enumerate(test_pdf_files, 1):
        file_size = pdf_file.stat().st_size / 1024 / 1024  # MB
        page_count = get_pdf_page_count(pdf_file)
        total_size += file_size
        total_pages += page_count
        print(f"  {i}. {pdf_file.name} ({file_size:.2f} MB, {page_count} 页)")
    print(f"总大小: {total_size:.2f} MB")
    print(f"总页数: {total_pages} 页")

    # 使用vlm-vllm-engine后端
    backend = "vlm-vllm-engine"

    # 创建批次
    batches = create_batches_by_pages(test_pdf_files, batch_size)
    if not batches:
        print("❌ 无法创建处理批次")
        return

    print(f"\n🎯 分批统计:")
    print(f"  总批次数: {len(batches)}")
    print(f"  总文件数: {len(test_pdf_files)}")
    print(f"  总页数: {sum(batch['total_pages'] for batch in batches)}")

    try:
        total_start_time = time.time()
        overall_stats = {
            'total_files_processed': 0,
            'total_pages_processed': 0,
            'total_files_generated': 0,
            'batch_count': len(batches)
        }

        print(f"\n🔄 开始分批处理...")
        print(f"后端: {backend}")

        # 逐批处理
        for batch_idx, batch in enumerate(batches, 1):
            print(f"\n--- 处理批次 {batch_idx}/{len(batches)} ---")
            print(f"文件: {len(batch['files'])} 个")
            print(f"页数: {batch['total_pages']} 页")
            print(f"文件名: {', '.join(batch['file_names'])}")

            # 准备PDF数据
            pdf_bytes_list = []
            pdf_file_names = batch['file_names']

            print(f"📖 加载批次 {batch_idx} PDF文件...")
            for pdf_path in batch['files']:
                pdf_bytes = read_fn(pdf_path)
                pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)
                pdf_bytes_list.append(pdf_bytes)
                print(f"  ✅ {pdf_path.name}")

            # 创建图像写入器
            image_writers = []
            output_dirs = []

            print(f"📁 准备批次 {batch_idx} 输出目录...")
            for pdf_file_name in pdf_file_names:
                local_image_dir, local_md_dir = prepare_env(output_base_dir / pdf_file_name, pdf_file_name, "vlm")
                image_writer = FileBasedDataWriter(local_image_dir)
                image_writers.append(image_writer)
                output_dirs.append((local_image_dir, local_md_dir))
                print(f"  📂 {pdf_file_name}: {local_md_dir}")

            print(f"🔄 处理批次 {batch_idx}...")
            batch_start_time = time.time()

            # 使用batch_doc_analyze批量处理
            all_middle_json, _ = batch_doc_analyze(
                pdf_bytes_list=pdf_bytes_list,
                image_writer_list=image_writers,
                backend=backend[4:],  # 去掉"vlm-"前缀
                server_url=None
            )

            batch_end_time = time.time()
            batch_processing_time = batch_end_time - batch_start_time

            print(f"✅ 批次 {batch_idx} 处理完成! 用时: {batch_processing_time:.2f} 秒")

            # 统计当前批次结果
            batch_pages_processed = 0
            batch_files_generated = 0

            for i, (pdf_file_name, middle_json) in enumerate(zip(pdf_file_names, all_middle_json)):
                if isinstance(middle_json, dict) and "pdf_info" in middle_json:
                    pages = len(middle_json["pdf_info"])
                    batch_pages_processed += pages
                    print(f"  📄 {pdf_file_name}: {pages} 页")

                    # 统计生成的文件数量
                    local_image_dir, local_md_dir = output_dirs[i]
                    if Path(local_md_dir).exists():
                        output_files = list(Path(local_md_dir).rglob("*"))
                        batch_files_generated += len(output_files)
                        print(f"     生成文件: {len(output_files)} 个")

            # 更新总体统计
            overall_stats['total_files_processed'] += len(batch['files'])
            overall_stats['total_pages_processed'] += batch_pages_processed
            overall_stats['total_files_generated'] += batch_files_generated

            print(f"📊 批次 {batch_idx} 统计:")
            print(f"  处理文件: {len(batch['files'])} 个")
            print(f"  处理页数: {batch_pages_processed} 页")
            print(f"  生成文件: {batch_files_generated} 个")
            print(f"  处理速度: {batch_pages_processed/batch_processing_time:.2f} 页/秒")

        total_end_time = time.time()
        total_processing_time = total_end_time - total_start_time

        print(f"\n🎉 所有批次处理完成!")
        print(f"\n🎯 总体性能统计:")
        print(f"  处理PDF数量: {overall_stats['total_files_processed']} 个")
        print(f"  总批次数: {overall_stats['batch_count']}")
        print(f"  总页数: {overall_stats['total_pages_processed']}")
        print(f"  总处理时间: {total_processing_time:.2f} 秒")
        print(f"  平均每PDF: {total_processing_time/overall_stats['total_files_processed']:.2f} 秒")
        print(f"  平均每页: {total_processing_time/overall_stats['total_pages_processed']:.2f} 秒")
        if overall_stats['total_pages_processed'] > 0:
            print(f"  处理速度: {overall_stats['total_pages_processed']/total_processing_time:.2f} 页/秒")
        print(f"  总生成文件: {overall_stats['total_files_generated']} 个")
        print(f"  平均每批次: {total_processing_time/overall_stats['batch_count']:.2f} 秒")

        # 保存结果到文件
        results_file = output_base_dir / "batch_results.txt"
        with open(results_file, 'w', encoding='utf-8') as f:
            f.write(f"分批处理测试结果\n")
            f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"批次大小: {batch_size} 页/批次\n")
            f.write(f"总批次数: {overall_stats['batch_count']}\n")
            f.write(f"处理文件数: {overall_stats['total_files_processed']}\n")
            f.write(f"总处理时间: {total_processing_time:.2f} 秒\n")
            f.write(f"平均每PDF: {total_processing_time/overall_stats['total_files_processed']:.2f} 秒\n")
            f.write(f"处理速度: {overall_stats['total_pages_processed']/total_processing_time:.2f} 页/秒\n")
            f.write(f"总生成文件: {overall_stats['total_files_generated']} 个\n")

        print(f"\n💾 结果已保存到: {results_file}")
        print(f"🎁 输出目录: {output_base_dir}")
        print(f"🎉 分批处理测试完成!")

    except Exception as e:
        print(f"❌ 分批处理失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()