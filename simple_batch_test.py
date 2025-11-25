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


def process_pdf_and_get_info(pdf_path):
    """
    处理PDF文件：获取页数并转换为字节数据
    在一个函数中完成所有PDF相关操作，减少重复读取
    返回: (page_count, pdf_bytes, is_valid, error_message)
    """
    try:
        # 第一步：尝试读取PDF字节数据
        pdf_bytes = read_fn(pdf_path)

        # 第二步：尝试获取页数
        pdf_document = pypdfium2.PdfDocument(pdf_bytes)
        page_count = len(pdf_document)
        pdf_document.close()

        # 第三步：转换为处理用的字节数据
        processed_pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)

        return page_count, processed_pdf_bytes, True, None

    except Exception as e:
        error_msg = str(e)
        print(f"⚠️ 处理 {pdf_path.name} 失败: {error_msg}")

        # 根据错误类型提供更具体的提示
        if "password" in error_msg.lower() or "encrypted" in error_msg.lower():
            error_msg = f"PDF文件已加密或需要密码: {error_msg}"
        elif "corrupted" in error_msg.lower() or "damaged" in error_msg.lower():
            error_msg = f"PDF文件已损坏: {error_msg}"
        elif "invalid" in error_msg.lower():
            error_msg = f"无效的PDF文件: {error_msg}"

        return 0, None, False, error_msg


def get_pdf_page_count_safe(pdf_path):
    """安全获取PDF文件的页数，处理异常情况"""
    try:
        # 只读取页数，不处理字节，避免内存占用
        pdf_bytes = read_fn(pdf_path)
        pdf_document = pypdfium2.PdfDocument(pdf_bytes)
        page_count = len(pdf_document)
        pdf_document.close()
        return page_count, True, None
    except Exception as e:
        error_msg = str(e)

        # 根据错误类型提供更具体的提示
        if "password" in error_msg.lower() or "encrypted" in error_msg.lower():
            error_msg = f"PDF文件已加密或需要密码: {error_msg}"
        elif "corrupted" in error_msg.lower() or "damaged" in error_msg.lower():
            error_msg = f"PDF文件已损坏: {error_msg}"
        elif "invalid" in error_msg.lower():
            error_msg = f"无效的PDF文件: {error_msg}"

        return 0, False, error_msg


def process_single_batch(batch_idx, batch_files, estimated_pages, output_base_dir, backend, overall_stats):
    """
    处理单个批次
    返回: (success, actual_pages_processed)
    """
    try:
        print(f"\n--- 处理批次 {batch_idx} ---")
        print(f"文件: {len(batch_files)} 个")
        print(f"预估页数: {estimated_pages} 页")
        print(f"文件名: {', '.join([f.name for f in batch_files])}")

        # 实时准备PDF数据
        pdf_bytes_list = []
        pdf_file_names = []
        actual_pages_in_batch = 0

        print(f"📖 实时加载批次 {batch_idx} PDF文件...")

        for i, pdf_path in enumerate(batch_files):
            print(f"  📄 加载 {i+1}/{len(batch_files)}: {pdf_path.name}")

            try:
                # 实时读取和处理PDF
                pdf_bytes = read_fn(pdf_path)
                pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)

                # 验证处理后的数据
                if pdf_bytes is None or len(pdf_bytes) == 0:
                    print(f"    ❌ 转换失败，跳过文件")
                    continue

                pdf_bytes_list.append(pdf_bytes)
                pdf_file_names.append(pdf_path.stem)

                # 获取实际页数
                try:
                    temp_pdf = pypdfium2.PdfDocument(read_fn(pdf_path))
                    actual_page_count = len(temp_pdf)
                    temp_pdf.close()
                    actual_pages_in_batch += actual_page_count
                    print(f"    ✅ 成功: {actual_page_count} 页")
                except:
                    print(f"    ⚠️ 无法确认页数，跳过")
                    continue

            except Exception as e:
                print(f"    ❌ 处理失败: {e}")
                continue

        if not pdf_bytes_list:
            print(f"  ❌ 批次 {batch_idx} 没有有效文件，跳过")
            return False

        print(f"  📦 批次 {batch_idx} 实际加载: {len(pdf_bytes_list)}/{len(batch_files)} 文件, {actual_pages_in_batch} 页")

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
        overall_stats['total_files_processed'] += len(pdf_bytes_list)
        overall_stats['total_pages_processed'] += batch_pages_processed
        overall_stats['total_files_generated'] += batch_files_generated

        print(f"📊 批次 {batch_idx} 统计:")
        print(f"  处理文件: {len(pdf_bytes_list)} 个")
        print(f"  处理页数: {batch_pages_processed} 页")
        print(f"  生成文件: {batch_files_generated} 个")
        print(f"  处理速度: {batch_pages_processed/batch_processing_time:.2f} 页/秒")

        return True

    except Exception as e:
        print(f"❌ 批次 {batch_idx} 处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


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
    for i, pdf_file in enumerate(test_pdf_files, 1):
        file_size = pdf_file.stat().st_size / 1024 / 1024  # MB
        total_size += file_size
        print(f"  {i}. {pdf_file.name} ({file_size:.2f} MB)")
    print(f"总大小: {total_size:.2f} MB")

    # 使用vlm-vllm-engine后端
    backend = "vlm-vllm-engine"

    print(f"\n🎯 动态分批处理模式:")
    print(f"  文件数量: {len(test_pdf_files)}")
    print(f"  批次大小: {batch_size} 页/批次")

    try:
        total_start_time = time.time()
        overall_stats = {
            'total_files_processed': 0,
            'total_pages_processed': 0,
            'total_files_generated': 0,
            'batch_count': 0,
            'total_files_attempted': 0,
            'failed_files': 0
        }

        print(f"\n🔄 开始动态分批处理...")
        print(f"后端: {backend}")

        # 动态批次处理
        current_batch_files = []
        current_batch_pages = 0
        batch_idx = 0

        # 使用 for i in range 循环逐步处理文件
        for i in range(len(test_pdf_files)):
            pdf_file = test_pdf_files[i]
            print(f"\n📄 处理文件 {i+1}/{len(test_pdf_files)}: {pdf_file.name}")

            # 获取页数（如果失败则跳过）
            page_count, is_valid, error_msg = get_pdf_page_count_safe(pdf_file)
            overall_stats['total_files_attempted'] += 1

            if not is_valid or page_count == 0:
                print(f"  ❌ 跳过文件: {error_msg}")
                overall_stats['failed_files'] += 1
                continue

            print(f"  ✅ 页数: {page_count}")

            # 判断是否需要开始新批次
            if (len(current_batch_files) > 0 and current_batch_pages + page_count > batch_size) or page_count >= batch_size:
                # 先处理当前批次
                if current_batch_files:
                    batch_idx += 1
                    success = process_single_batch(
                        batch_idx,
                        current_batch_files,
                        current_batch_pages,
                        output_base_dir,
                        backend,
                        overall_stats
                    )
                    if success:
                        overall_stats['batch_count'] += 1

                current_batch_files = []
                current_batch_pages = 0

            # 如果是超大文件，单独处理
            if page_count >= batch_size:
                batch_idx += 1
                success = process_single_batch(
                    batch_idx,
                    [pdf_file],
                    page_count,
                    output_base_dir,
                    backend,
                    overall_stats
                )
                if success:
                    overall_stats['batch_count'] += 1
                continue

            # 添加到当前批次
            current_batch_files.append(pdf_file)
            current_batch_pages += page_count
            print(f"  📦 加入当前批次: {len(current_batch_files)} 文件, {current_batch_pages} 页")

        # 处理最后一个批次
        if current_batch_files:
            batch_idx += 1
            success = process_single_batch(
                batch_idx,
                current_batch_files,
                current_batch_pages,
                output_base_dir,
                backend,
                overall_stats
            )
            if success:
                overall_stats['batch_count'] += 1

        total_end_time = time.time()
        total_processing_time = total_end_time - total_start_time

        print(f"\n🎉 动态分批处理完成!")
        print(f"\n🎯 总体性能统计:")
        print(f"  原始PDF数量: {len(test_pdf_files)} 个")
        print(f"  尝试处理: {overall_stats['total_files_attempted']} 个")
        print(f"  处理失败: {overall_stats['failed_files']} 个")
        print(f"  成功处理PDF数量: {overall_stats['total_files_processed']} 个")
        print(f"  总批次数: {overall_stats['batch_count']}")
        print(f"  总页数: {overall_stats['total_pages_processed']}")
        print(f"  总处理时间: {total_processing_time:.2f} 秒")
        if overall_stats['total_files_processed'] > 0:
            print(f"  平均每PDF: {total_processing_time/overall_stats['total_files_processed']:.2f} 秒")
        if overall_stats['total_pages_processed'] > 0:
            print(f"  平均每页: {total_processing_time/overall_stats['total_pages_processed']:.2f} 秒")
            print(f"  处理速度: {overall_stats['total_pages_processed']/total_processing_time:.2f} 页/秒")
        print(f"  总生成文件: {overall_stats['total_files_generated']} 个")
        if overall_stats['batch_count'] > 0:
            print(f"  平均每批次: {total_processing_time/overall_stats['batch_count']:.2f} 秒")

        # 保存结果到文件
        results_file = output_base_dir / "batch_results.txt"
        with open(results_file, 'w', encoding='utf-8') as f:
            f.write(f"动态分批处理测试结果\n")
            f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"批次大小: {batch_size} 页/批次\n")
            f.write(f"原始文件数: {len(test_pdf_files)}\n")
            f.write(f"尝试处理数: {overall_stats['total_files_attempted']}\n")
            f.write(f"处理失败数: {overall_stats['failed_files']}\n")
            f.write(f"成功处理文件数: {overall_stats['total_files_processed']}\n")
            f.write(f"总批次数: {overall_stats['batch_count']}\n")
            f.write(f"总处理时间: {total_processing_time:.2f} 秒\n")
            if overall_stats['total_files_processed'] > 0:
                f.write(f"平均每PDF: {total_processing_time/overall_stats['total_files_processed']:.2f} 秒\n")
            if overall_stats['total_pages_processed'] > 0:
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