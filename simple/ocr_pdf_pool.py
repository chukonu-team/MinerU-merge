#!/usr/bin/env python3
"""
OCR PDF with Pool - 基于三级队列架构的PDF处理系统
集成preprocess_queue, gpu_queue, post_queue
"""

import os
import sys
import json
import time
import glob
import shutil
import traceback
import multiprocessing as mp
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import zipfile
import base64
from PIL import Image
import io

# 添加simple目录到路径以便导入模块
sys.path.insert(0, str(Path(__file__).parent))

from process_pool import SimpleProcessPool


def load_pdf_and_convert_to_images(pdf_path: str, max_pages: int = None):
    """
    预处理函数：加载PDF并转换为图像

    根据参数说明，每个元素应该包含：
    - success: True/False; 标记这个任务是正常还是失败
    - error_message: 如果是失败的，这里是异常message
    - filePath: pdf文件路径

    Args:
        pdf_path: PDF文件路径
        max_pages: 最大页数限制

    Returns:
        dict: 预处理结果对象
    """
    try:
        import fitz  # PyMuPDF

        print(f"预处理加载PDF: {pdf_path}")

        # 读取PDF文件
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()

        # 转换为图像
        pdf_doc = fitz.open(pdf_path)
        page_count = pdf_doc.page_count

        if max_pages and page_count > max_pages:
            print(f"Warning: PDF has {page_count} pages, limiting to {max_pages}")
            page_count = max_pages

        all_images_list = []
        for page_num in range(page_count):
            page = pdf_doc[page_num]
            # 获取页面图像
            mat = fitz.Matrix(2.0, 2.0)  # 2x放大
            pix = page.get_pixmap(matrix=mat)
            # 转换为Base64
            img_data = pix.tobytes("png")
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            all_images_list.append(img_base64)

        pdf_doc.close()

        result = {
            'success': True,
            'error_message': None,
            'filePath': pdf_path,
            'pdf_bytes': pdf_bytes,
            'all_images_list': all_images_list,
            'images_count': page_count
        }

        print(f"预处理完成: {page_count} 页, 图像数量: {len(all_images_list)}")

        return result

    except Exception as e:
        print(f"预处理PDF失败 {pdf_path}: {e}")
        result = {
            'success': False,
            'error_message': str(e),
            'filePath': pdf_path,
            'pdf_bytes': None,
            'all_images_list': [],
            'images_count': 0
        }
        return result


def gpu_inference_task(batch_data: Dict[str, Any], gpu_id: int = 0) -> Dict[str, Any]:
    """
    GPU推理任务：处理多个PDF的批次

    根据参数说明，gpu_queue会接收一个任务，包含：
    - success: True/False[]; 标记每个pdf是成功还是失败
    - error_message: [] 每个pdf处理，若错误是message，否则None
    - pdf_paths: []
    - pdf_bytes_list: []
    - all_images_list: []
    - images_count_per_pdf: []

    Args:
        batch_data: 批次数据，包含多个PDF的预处理结果
        gpu_id: GPU设备ID

    Returns:
        dict: GPU推理结果
    """
    try:
        print(f"GPU推理开始 (GPU {gpu_id}) - 处理批次")

        # 设置GPU环境
        os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu_id)

        # 处理批次数据
        pdf_paths = batch_data.get('pdf_paths', [])
        pdf_bytes_list = batch_data.get('pdf_bytes_list', [])
        all_images_list = batch_data.get('all_images_list', [])
        images_count_per_pdf = batch_data.get('images_count_per_pdf', [])

        # 初始化结果数组
        gpu_results = []
        success_list = []
        error_message_list = []

        print(f"处理批次: {len(pdf_paths)} 个PDF文件")

        # 对每个PDF进行GPU推理
        for pdf_idx, pdf_path in enumerate(pdf_paths):
            try:
                pdf_images = all_images_list[pdf_idx] if pdf_idx < len(all_images_list) else []
                page_count = images_count_per_pdf[pdf_idx] if pdf_idx < len(images_count_per_pdf) else 0

                # 这里应该调用实际的GPU模型推理
                # 为了演示，我们模拟GPU推理过程
                time.sleep(0.5)  # 模拟GPU推理时间

                # 模拟GPU推理结果
                pdf_gpu_results = []
                for i, img_base64 in enumerate(pdf_images):
                    result = {
                        'page_idx': i,
                        'text': f"Extracted text from page {i}",
                        'confidence': 0.95,
                        'layout': {
                            'blocks': [
                                {
                                    'type': 'text',
                                    'bbox': [0, 0, 100, 100],
                                    'text': f"Sample text block on page {i}"
                                }
                            ]
                        }
                    }
                    pdf_gpu_results.append(result)

                gpu_results.append(pdf_gpu_results)
                success_list.append(True)
                error_message_list.append(None)

                print(f"GPU推理完成: {pdf_path} - {len(pdf_gpu_results)} 页")

            except Exception as e:
                print(f"GPU推理失败: {pdf_path} - {e}")
                gpu_results.append([])
                success_list.append(False)
                error_message_list.append(str(e))

        print(f"批次GPU推理完成: 成功 {sum(success_list)}/{len(success_list)} 个")

        return {
            'success': success_list,
            'error_message': error_message_list,
            'gpu_results': gpu_results,
            'pdf_paths': pdf_paths,
            'pdf_bytes_list': pdf_bytes_list,
            'all_images_list': all_images_list,
            'images_count_per_pdf': images_count_per_pdf,
            'gpu_id': gpu_id,
            'batch_size': len(pdf_paths)
        }

    except Exception as e:
        print(f"GPU推理失败 (GPU {gpu_id}): {e}")
        return {
            'success': [False] * len(batch_data.get('pdf_paths', [1])),
            'error_message': [str(e)] * len(batch_data.get('pdf_paths', [1])),
            'gpu_results': [],
            'pdf_paths': batch_data.get('pdf_paths', []),
            'pdf_bytes_list': [],
            'all_images_list': [],
            'images_count_per_pdf': [],
            'gpu_id': gpu_id,
            'batch_size': 0
        }


def postprocessing_task(gpu_result_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """
    后处理任务：将GPU推理结果转换为最终输出格式并保存

    根据参数说明，post_queue会接收：
    - 'gpu_results': gpu_results,
    - 'all_images_list'
    - 'pdf_bytes_list'
    - 其他参数

    Args:
        gpu_result_data: GPU推理结果数据，包含批次处理结果
        **kwargs: 其他参数（包含save_dir等）

    Returns:
        dict: 后处理结果
    """
    try:
        print("后处理开始")

        save_dir = kwargs.get('save_dir')
        if not save_dir:
            raise ValueError("save_dir is required")

        os.makedirs(save_dir, exist_ok=True)

        # 从GPU结果中提取数据
        success_list = gpu_result_data.get('success', [])
        error_message_list = gpu_result_data.get('error_message', [])
        gpu_results = gpu_result_data.get('gpu_results', [])
        pdf_paths = gpu_result_data.get('pdf_paths', [])
        pdf_bytes_list = gpu_result_data.get('pdf_bytes_list', [])
        all_images_list = gpu_result_data.get('all_images_list', [])
        images_count_per_pdf = gpu_result_data.get('images_count_per_pdf', [])
        gpu_id = gpu_result_data.get('gpu_id', 0)
        batch_size = gpu_result_data.get('batch_size', 0)

        print(f"后处理批次: {batch_size} 个文件")

        processed_results = []
        total_success = 0

        # 对每个PDF进行后处理
        for pdf_idx in range(batch_size):
            try:
                pdf_path = pdf_paths[pdf_idx] if pdf_idx < len(pdf_paths) else 'unknown.pdf'
                pdf_name = os.path.basename(pdf_path)

                if pdf_idx < len(success_list) and success_list[pdf_idx]:
                    # 成功处理的情况
                    pdf_gpu_results = gpu_results[pdf_idx] if pdf_idx < len(gpu_results) else []

                    # 转换为middle JSON格式
                    middle_json_data = {
                        'pdf_info': {
                            'name': pdf_name,
                            'path': pdf_path,
                            'status': 'success',
                            'pages_count': images_count_per_pdf[pdf_idx] if pdf_idx < len(images_count_per_pdf) else 0
                        },
                        'pages': pdf_gpu_results,
                        'metadata': {
                            'gpu_id': gpu_id,
                            'batch_index': pdf_idx,
                            'images_processed': len(pdf_gpu_results)
                        }
                    }

                    # 保存为压缩JSON
                    output_file = os.path.join(save_dir, f"{Path(pdf_name).stem}.zip")

                    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        json_str = json.dumps(middle_json_data, ensure_ascii=False, indent=2)
                        zipf.writestr(f"{Path(pdf_name).stem}.json", json_str.encode('utf-8'))

                    processed_results.append({
                        'pdf_name': pdf_name,
                        'success': True,
                        'output_file': output_file,
                        'pages_processed': len(pdf_gpu_results)
                    })
                    total_success += 1

                    print(f"后处理完成: {pdf_name} -> {output_file}")

                else:
                    # 处理失败的情况
                    error_msg = error_message_list[pdf_idx] if pdf_idx < len(error_message_list) else 'Unknown error'

                    # 保存错误信息
                    error_file = os.path.join(save_dir, f"{Path(pdf_name).stem}_error.txt")
                    with open(error_file, 'w', encoding='utf-8') as f:
                        f.write(f"Processing failed for {pdf_name}\n\n")
                        f.write(f"Error: {error_msg}\n\n")
                        f.write(f"GPU ID: {gpu_id}\n")
                        f.write(f"Batch Index: {pdf_idx}\n")

                    processed_results.append({
                        'pdf_name': pdf_name,
                        'success': False,
                        'error': error_msg,
                        'error_file': error_file
                    })

                    print(f"后处理失败: {pdf_name} - {error_msg}")

            except Exception as e:
                pdf_name = os.path.basename(pdf_paths[pdf_idx]) if pdf_idx < len(pdf_paths) else f'batch_item_{pdf_idx}'
                print(f"后处理异常: {pdf_name} - {e}")

                processed_results.append({
                    'pdf_name': pdf_name,
                    'success': False,
                    'error': str(e)
                })

        print(f"批次后处理完成: 成功 {total_success}/{batch_size} 个")

        return {
            'success': True,
            'batch_results': processed_results,
            'total_success': total_success,
            'batch_size': batch_size,
            'gpu_id': gpu_id,
            'save_dir': save_dir
        }

    except Exception as e:
        print(f"后处理失败: {e}")
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


def process_pdf_files_with_pools(input_dir: str, output_dir: str,
                               vram_size_gb: int = 24, gpu_ids: str = "0",
                               workers_per_gpu: int = 1, max_pages: int = None,
                               shuffle: bool = False, batch_size: int = 384):
    """
    使用三级队列系统处理PDF文件

    根据pool.md设计：
    - preProcessPool: 会一次一次读取多个pdf文件直到page count达到要求，或者超时（比如1s）
    - 然后将多个pdf打包为一个batch，作为一个任务发送到gpu_queue

    Args:
        input_dir: 输入PDF目录
        output_dir: 输出目录
        vram_size_gb: GPU显存大小
        gpu_ids: GPU设备ID字符串，逗号分隔
        workers_per_gpu: 每个GPU的工作进程数
        max_pages: 最大页数限制
        shuffle: 是否随机打乱文件顺序
        batch_size: 批处理大小（页数）
    """
    print("=== 启动三级队列PDF处理系统 ===")

    # 解析GPU ID
    gpu_id_list = [int(g.strip()) for g in gpu_ids.split(',')]
    print(f"使用GPU设备: {gpu_id_list}")

    # 获取PDF文件列表
    pdf_files = []
    for ext in ['*.pdf', '*.PDF']:
        pdf_files.extend(glob.glob(os.path.join(input_dir, ext)))

    if not pdf_files:
        print("未找到PDF文件")
        return

    if shuffle:
        import random
        random.shuffle(pdf_files)

    print(f"找到 {len(pdf_files)} 个PDF文件待处理")

    # 创建三级队列进程池
    print("创建三级队列进程池...")

    # 根据pool.md设计配置队列系统
    pool = SimpleProcessPool(
        gpu_ids=gpu_id_list,
        workers_per_gpu=workers_per_gpu,
        enable_preprocessing=True,
        max_gpu_queue_size=100,  # GPU队列最大长度100
        preprocessing_workers=2,  # 预处理工作进程数
        postprocessing_workers=2   # 后处理工作进程数
    )

    try:
        processed_count = 0
        total_files = len(pdf_files)
        batch_count = 0

        print(f"开始批处理，批次大小: {batch_size} 页")

        # 批处理逻辑：一次读取多个pdf文件直到page count达到要求，或者超时
        batch_pdf_files = []
        total_pages_in_batch = 0
        batch_timeout = time.time() + 1.0  # 1秒超时

        for pdf_file in pdf_files:
            try:
                # 预处理单个PDF
                pdf_name = os.path.basename(pdf_file)
                print(f"预处理PDF: {pdf_name}")

                preprocessed_result = load_pdf_and_convert_to_images(pdf_file, max_pages)

                # 将预处理结果添加到当前批次
                if preprocessed_result.get('success', False):
                    batch_pdf_files.append(preprocessed_result)
                    total_pages_in_batch += preprocessed_result.get('images_count', 0)
                    print(f"  成功处理: {preprocessed_result.get('images_count', 0)} 页")
                else:
                    print(f"  处理失败: {preprocessed_result.get('error_message', 'Unknown error')}")

                # 检查是否需要提交批次
                batch_ready = (
                    total_pages_in_batch >= batch_size or  # 达到页数要求
                    time.time() > batch_timeout  # 超时
                )

                if batch_ready and batch_pdf_files:
                    # 准备批次数据
                    batch_data = {
                        'success': [result['success'] for result in batch_pdf_files],
                        'error_message': [result['error_message'] for result in batch_pdf_files],
                        'pdf_paths': [result['filePath'] for result in batch_pdf_files],
                        'pdf_bytes_list': [result['pdf_bytes'] for result in batch_pdf_files],
                        'all_images_list': [result['all_images_list'] for result in batch_pdf_files],
                        'images_count_per_pdf': [result['images_count'] for result in batch_pdf_files]
                    }

                    print(f"提交批次 {batch_count}: {len(batch_pdf_files)} 个文件, {total_pages_in_batch} 页")

                    # 提交批次到GPU队列
                    task_id = pool.submit_task(
                        gpu_inference_task,
                        batch_data,
                        gpu_id_list[0]  # 使用第一个GPU
                    )

                    print(f"已提交GPU任务 {task_id}")

                    # 重置批次
                    batch_count += 1
                    batch_pdf_files = []
                    total_pages_in_batch = 0
                    batch_timeout = time.time() + 1.0  # 重置超时

                    processed_count += len(batch_pdf_files)

            except Exception as e:
                print(f"处理PDF {pdf_file} 时出错: {e}")

        # 提交剩余的批次
        if batch_pdf_files:
            batch_data = {
                'success': [result['success'] for result in batch_pdf_files],
                'error_message': [result['error_message'] for result in batch_pdf_files],
                'pdf_paths': [result['filePath'] for result in batch_pdf_files],
                'pdf_bytes_list': [result['pdf_bytes'] for result in batch_pdf_files],
                'all_images_list': [result['all_images_list'] for result in batch_pdf_files],
                'images_count_per_pdf': [result['images_count'] for result in batch_pdf_files]
            }

            print(f"提交最后批次 {batch_count}: {len(batch_pdf_files)} 个文件, {total_pages_in_batch} 页")

            task_id = pool.submit_task(
                gpu_inference_task,
                batch_data,
                gpu_id_list[0]
            )

            print(f"已提交GPU任务 {task_id}")

        print(f"所有批次已提交到GPU队列，等待处理完成...")

        # 等待所有任务完成
        results_received = 0
        while not pool.all_tasks_completed() and time.time() < time.time() + 300:  # 5分钟超时
            time.sleep(5)

            # 打印队列状态
            pre_size = pool.get_preprocessing_queue_size()
            gpu_size = pool.get_gpu_queue_size()
            post_size = pool.get_postprocessing_queue_size()

            print(f"队列状态 - 预处理: {pre_size}, GPU: {gpu_size}, 后处理: {post_size}")

            # 收集已完成的任务结果
            while True:
                result = pool.get_result(timeout=1.0)
                if result is None:
                    break

                task_id, status, result_data = result
                results_received += 1

                if status == 'success':
                    if 'total_success' in result_data:
                        print(f"后处理任务 {task_id} 完成: 成功 {result_data['total_success']} 个文件")

                        # 显示详细结果
                        for batch_result in result_data.get('batch_results', []):
                            if batch_result.get('success', False):
                                print(f"  ✓ {batch_result['pdf_name']} -> {batch_result.get('output_file', '')}")
                            else:
                                print(f"  ✗ {batch_result['pdf_name']} - {batch_result.get('error', 'Unknown error')}")
                    else:
                        print(f"任务 {task_id} 完成: {result_data}")
                else:
                    print(f"任务 {task_id} 失败: {result_data}")

        print(f"=== 处理完成 ===")
        print(f"收到 {results_received} 个结果")
        print(f"总处理文件数: {processed_count}/{total_files}")

    finally:
        # 关闭进程池
        print("关闭三级队列进程池...")
        pool.shutdown()


if __name__ == "__main__":
    # 测试用例
    input_dir = "/tmp/test_pdfs"
    output_dir = "/tmp/test_output"

    process_pdf_files_with_pools(
        input_dir=input_dir,
        output_dir=output_dir,
        gpu_ids="0",
        workers_per_gpu=1,
        max_pages=10,
        shuffle=False,
        batch_size=384
    )