#!/usr/bin/env python3
"""
MinerU批量测试脚本 - 处理demo目录中的所有PDF文件，包含VLM批量对比测试
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# 添加mineru模块到路径
sys.path.insert(0, '/home/ubuntu/MinerU')

from demo.demo import parse_doc
from mineru.backend.vlm.vlm_analyze import doc_analyze, batch_doc_analyze, ModelSingleton
from mineru.data.data_reader_writer import DataWriter
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

def process_single_pdf(pdf_path, output_dir, backend, pdf_index, total_pdfs):
    """处理单个PDF文件"""
    print(f"\n{'='*60}")
    print(f"处理PDF {pdf_index+1}/{total_pdfs}: {pdf_path.name}")
    print(f"后端: {backend}")
    print(f"开始时间: {datetime.now().strftime('%H:%M:%S')}")

    start_time = time.time()

    try:
        # 为每个PDF创建独立的输出目录
        pdf_output_dir = output_dir / pdf_path.stem / backend

        # 使用MinerU处理PDF
        parse_doc(
            path_list=[pdf_path],
            output_dir=pdf_output_dir,
            lang="ch",  # 中文
            backend=backend,  # 指定后端
            method="auto"  # 自动选择方法
        )

        processing_time = time.time() - start_time

        print(f"✅ 处理完成!")
        print(f"处理时间: {processing_time:.2f}秒")
        print(f"输出目录: {pdf_output_dir}")

        # 统计输出文件
        output_files = []
        if pdf_output_dir.exists():
            for file in pdf_output_dir.rglob("*"):
                if file.is_file():
                    output_files.append(file.relative_to(pdf_output_dir))

        print(f"生成文件数量: {len(output_files)}")

        # 检查关键文件
        md_files = [f for f in output_files if f.suffix == '.md']
        json_files = [f for f in output_files if f.suffix == '.json']
        img_files = [f for f in output_files if f.suffix.lower() in ['.jpg', '.jpeg', '.png']]

        print(f"  - Markdown文件: {len(md_files)}")
        print(f"  - JSON文件: {len(json_files)}")
        print(f"  - 图片文件: {len(img_files)}")

        return {
            'pdf_name': pdf_path.name,
            'status': 'success',
            'processing_time': processing_time,
            'output_files': len(output_files),
            'md_files': len(md_files),
            'json_files': len(json_files),
            'img_files': len(img_files),
            'output_dir': str(pdf_output_dir)
        }

    except Exception as e:
        processing_time = time.time() - start_time
        print(f"❌ 处理失败: {e}")
        return {
            'pdf_name': pdf_path.name,
            'status': 'error',
            'error': str(e),
            'processing_time': processing_time
        }

def run_batch_test():
    """运行批量测试"""
    print("🚀 MinerU 批量测试开始")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 设置路径
    demo_dir = "/home/ubuntu/MinerU/demo/pdfs"
    output_base_dir = Path("/home/ubuntu/MinerU/batch_test_output")

    # 获取所有PDF文件
    pdf_files = get_pdf_files(demo_dir)

    if not pdf_files:
        print("❌ 未找到PDF文件")
        return

    print(f"📄 找到 {len(pdf_files)} 个PDF文件:")
    for i, pdf_file in enumerate(pdf_files, 1):
        file_size = pdf_file.stat().st_size / 1024 / 1024  # MB
        print(f"  {i}. {pdf_file.name} ({file_size:.2f} MB)")

    # 选择要测试的后端
    backends = ["pipeline", "vlm-vllm-engine"]

    # 处理每个PDF文件
    all_results = []

    for backend in backends:
        print(f"\n🔧 使用后端: {backend}")

        backend_results = []
        backend_start_time = time.time()

        for i, pdf_file in enumerate(pdf_files):
            result = process_single_pdf(pdf_file, output_base_dir, backend, i, len(pdf_files))
            backend_results.append(result)
            all_results.append(result)

        backend_total_time = time.time() - backend_start_time
        successful_pdfs = [r for r in backend_results if r['status'] == 'success']

        print(f"\n📊 {backend} 后端统计:")
        print(f"  总处理时间: {backend_total_time:.2f}秒")
        print(f"  成功处理: {len(successful_pdfs)}/{len(pdf_files)}")

        if successful_pdfs:
            avg_time = sum(r['processing_time'] for r in successful_pdfs) / len(successful_pdfs)
            total_files = sum(r['output_files'] for r in successful_pdfs)
            total_md = sum(r['md_files'] for r in successful_pdfs)
            total_img = sum(r['img_files'] for r in successful_pdfs)

            print(f"  平均处理时间: {avg_time:.2f}秒/PDF")
            print(f"  总生成文件: {total_files}个")
            print(f"  - Markdown: {total_md}个")
            print(f"  - 图片: {total_img}个")

    # 生成总结报告
    print(f"\n{'='*60}")
    print("📋 批量测试总结报告")
    print(f"{'='*60}")

    successful_results = [r for r in all_results if r['status'] == 'success']
    failed_results = [r for r in all_results if r['status'] == 'error']

    print(f"总处理任务: {len(all_results)}")
    print(f"成功: {len(successful_results)}")
    print(f"失败: {len(failed_results)}")

    if successful_results:
        print(f"\n✅ 成功处理的PDF:")
        for result in successful_results:
            print(f"  - {result['pdf_name']}: {result['processing_time']:.2f}秒, "
                  f"{result['output_files']}个文件 ({result['md_files']}md, {result['img_files']}img)")

    if failed_results:
        print(f"\n❌ 处理失败的PDF:")
        for result in failed_results:
            print(f"  - {result['pdf_name']}: {result['error']}")

    # 性能对比
    print(f"\n🏆 后端性能对比:")
    for backend in backends:
        backend_successful = [r for r in successful_results if backend in r['output_dir']]
        if backend_successful:
            avg_time = sum(r['processing_time'] for r in backend_successful) / len(backend_successful)
            total_files = sum(r['output_files'] for r in backend_successful)
            print(f"  {backend}:")
            print(f"    - 成功处理: {len(backend_successful)}个PDF")
            print(f"    - 平均处理时间: {avg_time:.2f}秒")
            print(f"    - 总生成文件: {total_files}个")

    print(f"\n🎁 所有输出文件保存在: {output_base_dir}")
    print(f"🎉 批量测试完成! 时间: {datetime.now().strftime('%H:%M:%S')}")


def load_pdf_bytes(pdf_path):
    """加载PDF文件字节数据"""
    with open(pdf_path, 'rb') as f:
        return f.read()


def create_mock_image_writer(output_dir):
    """创建模拟的图像写入器"""
    class MockImageWriter:
        def __init__(self, output_dir):
            self.output_dir = output_dir
            self.image_count = 0

        def write(self, data, filename):
            # 模拟写入操作，不实际保存文件
            self.image_count += 1
            return f"mock_{filename}"

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()

    return MockImageWriter


def test_vlm_batch_performance():
    """VLM批量处理性能对比测试"""
    print("\n" + "="*80)
    print("🚀 VLM批量处理性能对比测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # 设置路径
    demo_dir = "/home/ubuntu/MinerU/demo/pdfs"
    output_base_dir = Path("/home/ubuntu/MinerU/vlm_batch_test_output")
    output_base_dir.mkdir(exist_ok=True)

    # 获取PDF文件
    pdf_files = get_pdf_files(demo_dir)
    if not pdf_files:
        print("❌ 未找到PDF文件")
        return

    # 限制测试文件数量（避免处理时间过长）
    max_files = min(3, len(pdf_files))  # 最多测试3个文件
    test_pdf_files = pdf_files[:max_files]

    print(f"📄 选择测试文件 ({max_files}个):")
    for i, pdf_file in enumerate(test_pdf_files, 1):
        file_size = pdf_file.stat().st_size / 1024 / 1024  # MB
        print(f"  {i}. {pdf_file.name} ({file_size:.2f} MB)")

    # 加载PDF字节数据
    pdf_bytes_list = []
    for pdf_file in test_pdf_files:
        try:
            pdf_bytes = load_pdf_bytes(pdf_file)
            pdf_bytes_list.append(pdf_bytes)
            print(f"✅ 加载成功: {pdf_file.name}")
        except Exception as e:
            print(f"❌ 加载失败 {pdf_file.name}: {e}")
            return

    # 创建图像写入器列表
    mock_writer_class = create_mock_image_writer(output_base_dir)
    image_writers = [mock_writer_class(output_base_dir / f"pdf_{i}") for i in range(len(pdf_bytes_list))]

    # VLM配置（使用vllm-engine）
    vlm_config = {
        "backend": "vllm-engine",
        "model_path": None,  # 使用默认模型
        "server_url": None,
        "gpu_memory_utilization": 0.8,
        "max_model_len": 8192,
    }

    print(f"\n🔧 使用VLM配置:")
    for key, value in vlm_config.items():
        print(f"  {key}: {value}")

    # 测试1: 单独处理（使用doc_analyze）
    print(f"\n{'-'*60}")
    print("📊 测试1: 单独处理 (doc_analyze)")
    print(f"{'-'*60}")

    single_start_time = time.time()
    single_results = []

    try:
        # 获取模型实例（复用，避免重复初始化）
        predictor = ModelSingleton().get_model(**vlm_config)

        for i, (pdf_bytes, pdf_file) in enumerate(zip(pdf_bytes_list, test_pdf_files)):
            print(f"\n处理PDF {i+1}/{len(pdf_bytes_list)}: {pdf_file.name}")
            start_time = time.time()

            try:
                # 使用doc_analyze处理单个PDF
                middle_json, results = doc_analyze(
                    pdf_bytes=pdf_bytes,
                    image_writer=image_writers[i],
                    predictor=predictor,
                    **vlm_config
                )

                processing_time = time.time() - start_time
                single_results.append({
                    'pdf_name': pdf_file.name,
                    'processing_time': processing_time,
                    'pages': len(results),
                    'status': 'success'
                })

                print(f"✅ 单独处理完成: {processing_time:.2f}s, {len(results)}页")

            except Exception as e:
                processing_time = time.time() - start_time
                print(f"❌ 单独处理失败: {e}")
                single_results.append({
                    'pdf_name': pdf_file.name,
                    'processing_time': processing_time,
                    'status': 'error',
                    'error': str(e)
                })

    except Exception as e:
        print(f"❌ 单独处理测试失败: {e}")
        return

    single_total_time = time.time() - single_start_time

    # 测试2: 批量处理（使用batch_doc_analyze）
    print(f"\n{'-'*60}")
    print("📊 测试2: 批量处理 (batch_doc_analyze)")
    print(f"{'-'*60}")

    batch_start_time = time.time()

    try:
        # 使用batch_doc_analyze处理所有PDF
        print(f"\n开始批量处理 {len(pdf_bytes_list)} 个PDF...")

        all_middle_json, batch_results, performance_stats = batch_doc_analyze(
            pdf_bytes_list=pdf_bytes_list,
            image_writer_list=image_writers,
            predictor=predictor,
            **vlm_config
        )

        batch_total_time = time.time() - batch_start_time
        batch_processing_time = performance_stats.get('total_time', batch_total_time)

        print(f"✅ 批量处理完成: {batch_processing_time:.2f}s")

    except Exception as e:
        print(f"❌ 批量处理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 性能对比分析
    print(f"\n{'='*80}")
    print("🏆 性能对比分析")
    print(f"{'='*80}")

    # 统计单独处理结果
    successful_single = [r for r in single_results if r['status'] == 'success']
    total_single_time = sum(r['processing_time'] for r in successful_single)
    total_pages_single = sum(r['pages'] for r in successful_single)

    print(f"📈 单独处理统计:")
    print(f"  成功处理: {len(successful_single)}/{len(test_pdf_files)}个PDF")
    print(f"  总处理时间: {total_single_time:.2f}s")
    print(f"  平均处理时间: {total_single_time/len(successful_single):.2f}s/PDF" if successful_single else "  平均处理时间: N/A")
    print(f"  总处理页数: {total_pages_single}")
    print(f"  处理速度: {total_pages_single/total_single_time:.2f}页/s" if total_single_time > 0 else "  处理速度: N/A")

    print(f"\n📊 批量处理统计:")
    print(f"  处理PDF数量: {performance_stats.get('total_pdfs', len(pdf_bytes_list))}")
    print(f"  总处理时间: {batch_processing_time:.2f}s")
    print(f"  总处理页数: {performance_stats.get('total_images', len(batch_results))}")
    print(f"  处理速度: {performance_stats.get('inference_speed_images_per_sec', 0):.2f}页/s")

    # 性能提升计算
    if total_single_time > 0 and batch_processing_time > 0:
        speedup = total_single_time / batch_processing_time
        time_saved = total_single_time - batch_processing_time
        efficiency_gain = (time_saved / total_single_time) * 100

        print(f"\n🎯 性能提升:")
        print(f"  加速比: {speedup:.2f}x")
        print(f"  节省时间: {time_saved:.2f}s ({efficiency_gain:.1f}%)")

        if speedup > 1:
            print(f"  ✅ 批量处理更高效，提升了 {speedup:.2f} 倍性能")
        else:
            print(f"  ⚠️  批量处理性能提升有限")

    # 详细结果对比
    print(f"\n📋 详细处理结果:")
    print(f"{'PDF文件':<20} {'单独处理时间':<15} {'批量处理包含':<15}")
    print(f"{'-'*50}")

    for i, (single_result, pdf_file) in enumerate(zip(single_results, test_pdf_files)):
        single_time = f"{single_result['processing_time']:.2f}s" if single_result['status'] == 'success' else "失败"
        batch_included = "✅ 包含" if single_result['status'] == 'success' else "N/A"
        print(f"{pdf_file.name:<20} {single_time:<15} {batch_included:<15}")

    print(f"\n🎁 测试输出保存在: {output_base_dir}")
    print(f"🎉 VLM批量对比测试完成! 时间: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    # 运行原始的批量测试
    run_batch_test()

    # 运行VLM批量对比测试
    test_vlm_batch_performance()