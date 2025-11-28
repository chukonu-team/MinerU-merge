#!/usr/bin/env python3
"""修复的MinerU进程池 - 简化版本"""

import os
import time
import json
import glob
import random
from typing import List, Dict, Any, Optional
import copy
import zipfile
import traceback
import logging

from mineru.cli.common import read_fn, convert_pdf_bytes_to_bytes_by_pypdfium2

# 导入简化的进程池
from process_pool import SimpleProcessPool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PID:%(process)d][%(thread)d] %(levelname)s: %(message)s"
)


def get_pdf_page_count(pdf_path):
    """使用fitz获取PDF页数"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        doc.close()
        return page_count
    except Exception as e:
        logging.warning(f"Error getting page count for {pdf_path}: {e}")
        return 0


def process_batch_pdf_files(batch, save_dir, backend="vllm-engine"):
    start = time.time()
    logging.info(f"批处理开始")
    result_dir = f"{save_dir}/result"
    if not os.path.exists(result_dir):
        os.makedirs(result_dir, exist_ok=True)

    pdf_bytes_list = []
    image_writers = []
    pdf_paths = batch['files']
    read_start = time.time()
    from mineru.data.data_reader_writer import FileBasedDataWriter
    for i in range(len(pdf_paths) - 1, -1, -1):
        try:
            pdf_bytes = read_fn(pdf_paths[i])
            pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)
            pdf_bytes_list.append(pdf_bytes)
            pdf_name = os.path.basename(pdf_paths[i])
            local_image_dir = f"/mnt/data/mineru_ocr_local_image_dir/{pdf_name}"
            if not os.path.exists(local_image_dir):
                os.makedirs(local_image_dir, exist_ok=True)
            image_writer = FileBasedDataWriter(local_image_dir)
            image_writers.append(image_writer)
        except Exception as e:
            logging.warning(f"加载 {pdf_paths[i]} 失败: {e}")
            traceback.print_exc()
            del pdf_paths[i]
    logging.info(f"加载完毕，耗时{time.time() - read_start}")
    from mineru.backend.vlm.vlm_analyze import batch_doc_analyze
    gpu_memory_utilization = os.environ.get("GPU_MEMORY_UTILIZATION", 0.5)
    all_middle_json, _ = batch_doc_analyze(
        pdf_bytes_list=pdf_bytes_list,
        image_writer_list=image_writers,
        backend=backend,
        server_url=None,
        gpu_memory_utilization=gpu_memory_utilization
    )
    results = []
    for pdf_path, middle_json in zip(pdf_paths, all_middle_json):
        pdf_file_name = os.path.basename(pdf_path).replace(".pdf", "")
        if middle_json is not None:
            infer_result = {"middle_json": middle_json}
            res_json_str = json.dumps(infer_result, ensure_ascii=False)
            # 保存为压缩文件
            result_dir = f"{save_dir}/result"
            if not os.path.exists(result_dir):
                os.makedirs(result_dir, exist_ok=True)
            target_file = f"{result_dir}/{pdf_file_name}.json.zip"
            with zipfile.ZipFile(target_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                res_json_bytes = res_json_str.encode("utf-8")
                zf.writestr(f"{pdf_file_name}.json", res_json_bytes)
            page_count = get_pdf_page_count(pdf_path)
            file_size = os.path.getsize(target_file)
            result = {
                'input_path': pdf_path,
                'output_path': target_file,
                'page_count': page_count,
                'file_size': file_size,
                'success': True
            }
        else:
            result = {
                'input_path': pdf_path,
                'output_path': None,
                'success': False
            }
        page_result_path = f"{save_dir}/page_result"
        if not os.path.exists(page_result_path):
            os.makedirs(page_result_path, exist_ok=True)
        json_file_name = f"{pdf_file_name}.json"
        temp_json_path = os.path.join(page_result_path, json_file_name)
        with open(temp_json_path, 'w') as f:
            json.dump(result, f)
        results.append(result)
    logging.info(f"批处理结束，耗时{time.time() - start}秒")
    return results


def preprocessing_task_with_image_loading(batch, save_dir, **kwargs):
    """
    增强版预处理函数 - 读取PDF文件、转换为字节格式、加载图像
    这部分工作包含load_images_from_pdf，不依赖GPU，可以在CPU上并行处理
    """
    start = time.time()
    logging.info(f"增强预处理批次开始: {batch.get('file_names', [])}")

    pdf_bytes_list = []
    image_writers = []
    pdf_paths = batch['files'].copy()

    read_start = time.time()
    from mineru.data.data_reader_writer import FileBasedDataWriter

    # 读取PDF文件并转换为字节格式
    for i in range(len(pdf_paths) - 1, -1, -1):
        try:
            pdf_bytes = read_fn(pdf_paths[i])
            pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)
            pdf_bytes_list.append(pdf_bytes)
            pdf_name = os.path.basename(pdf_paths[i])
            local_image_dir = f"/mnt/data/mineru_ocr_local_image_dir/{pdf_name}"
            if not os.path.exists(local_image_dir):
                os.makedirs(local_image_dir, exist_ok=True)
            image_writer = FileBasedDataWriter(local_image_dir)
            image_writers.append(image_writer)
        except Exception as e:
            logging.warning(f"加载 {pdf_paths[i]} 失败: {e}")
            traceback.print_exc()
            del pdf_paths[i]

    preprocess_time = time.time() - read_start
    logging.info(f"PDF读取完毕，耗时{preprocess_time:.2f}秒")

    # 加载图像（这部分原在batch_doc_analyze中）
    image_loading_start = time.time()
    from mineru.backend.vlm.vlm_analyze import load_images_from_pdf

    all_images_list = []
    all_pdf_docs = []
    images_count_per_pdf = []
    pdf_processing_status = []

    # 遍历所有PDF文档，加载图像
    for pdf_bytes in pdf_bytes_list:
        try:
            images_list, pdf_doc = load_images_from_pdf(pdf_bytes, image_type=ImageType.PIL)
            all_images_list.extend(images_list)
            all_pdf_docs.append(pdf_doc)
            images_count_per_pdf.append(len(images_list))
            pdf_processing_status.append(True)  # 标记为成功处理
        except Exception as e:
            logging.warning(f"从PDF加载图像失败: {e}")
            # 添加None作为pdf_doc，标记失败状态
            all_pdf_docs.append(None)
            images_count_per_pdf.append(0)  # 图像数量为0
            pdf_processing_status.append(False)  # 标记为处理失败

    image_loading_time = time.time() - image_loading_start
    logging.info(f"图像加载完毕，耗时{image_loading_time:.2f}秒")

    # 生成有效的PIL图像列表
    images_pil_list = []
    for image_dict in all_images_list:
        if image_dict and isinstance(image_dict, dict) and "img_pil" in image_dict:
            images_pil_list.append(image_dict["img_pil"])

    total_preprocess_time = time.time() - start
    logging.info(f"增强预处理完成，总耗时{total_preprocess_time:.2f}秒，有效图像数: {len(images_pil_list)}")

    # 返回预处理后的数据，供GPU函数使用
    return {
        'pdf_bytes_list': pdf_bytes_list,
        'image_writers': image_writers,
        'pdf_paths': pdf_paths,
        'save_dir': save_dir,
        'preprocess_time': preprocess_time,
        'image_loading_time': image_loading_time,
        'total_preprocess_time': total_preprocess_time,
        'all_images_list': all_images_list,
        'all_pdf_docs': all_pdf_docs,
        'images_count_per_pdf': images_count_per_pdf,
        'pdf_processing_status': pdf_processing_status,
        'images_pil_list': images_pil_list,
        'batch_info': batch
    }


def preprocessing_task(batch, save_dir, **kwargs):
    """
    预处理函数 - 读取PDF文件并转换为字节格式
    这部分工作不依赖GPU，可以在CPU上并行处理
    """
    start = time.time()
    logging.info(f"预处理批次开始: {batch.get('file_names', [])}")

    pdf_bytes_list = []
    image_writers = []
    pdf_paths = batch['files'].copy()

    read_start = time.time()
    from mineru.data.data_reader_writer import FileBasedDataWriter

    # 读取PDF文件并转换为字节格式
    for i in range(len(pdf_paths) - 1, -1, -1):
        try:
            pdf_bytes = read_fn(pdf_paths[i])
            pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)
            pdf_bytes_list.append(pdf_bytes)
            pdf_name = os.path.basename(pdf_paths[i])
            local_image_dir = f"/mnt/data/mineru_ocr_local_image_dir/{pdf_name}"
            if not os.path.exists(local_image_dir):
                os.makedirs(local_image_dir, exist_ok=True)
            image_writer = FileBasedDataWriter(local_image_dir)
            image_writers.append(image_writer)
        except Exception as e:
            logging.warning(f"加载 {pdf_paths[i]} 失败: {e}")
            traceback.print_exc()
            del pdf_paths[i]

    preprocess_time = time.time() - read_start
    logging.info(f"预处理加载完毕，耗时{preprocess_time:.2f}秒")

    # 返回预处理后的数据，供GPU函数使用
    return {
        'pdf_bytes_list': pdf_bytes_list,
        'image_writers': image_writers,
        'pdf_paths': pdf_paths,
        'save_dir': save_dir,
        'preprocess_time': preprocess_time,
        'batch_info': batch
    }


def gpu_processing_task_with_preloaded_images(preprocessed_data, **kwargs):
    """
    GPU处理函数 - 使用GPU进行文档分析并保存结果（基于预加载的图像）
    这部分工作需要GPU，只处理batch_two_step_extract及之后的部分
    """
    start = time.time()

    # 从预处理数据中获取所有必要信息
    all_images_list = preprocessed_data['all_images_list']
    all_pdf_docs = preprocessed_data['all_pdf_docs']
    images_count_per_pdf = preprocessed_data['images_count_per_pdf']
    pdf_processing_status = preprocessed_data['pdf_processing_status']
    images_pil_list = preprocessed_data['images_pil_list']
    save_dir = preprocessed_data['save_dir']
    image_writers = preprocessed_data['image_writers']
    batch = preprocessed_data['batch_info']

    logging.info(f"GPU处理开始（基于预加载图像）: {batch.get('file_names', [])}")

    try:
        # 如果没有有效的图像，直接返回空结果
        if not images_pil_list:
            logging.warning("没有有效的图像，返回空结果")
            all_middle_json = [None] * len(all_pdf_docs)
        else:
            # 获取predictor
            backend = os.environ.get("BACKEND", "vllm-engine")
            logging.info(f"backend: {backend}")

            from mineru.backend.vlm.vlm_analyze import ModelSingleton
            predictor = ModelSingleton().get_model(backend, None, None, **kwargs)

            # GPU推理 - 只调用batch_two_step_extract
            gpu_start = time.time()
            results = predictor.batch_two_step_extract(images=images_pil_list)
            gpu_time = time.time() - gpu_start
            logging.info(f"GPU推理完毕，耗时{gpu_time:.2f}秒")

            # 需要为每个PDF文档分别生成middle_json
            all_middle_json = []
            image_idx = 0

            for i, (pdf_doc, is_success) in enumerate(zip(all_pdf_docs, pdf_processing_status)):
                if not is_success or pdf_doc is None:
                    # 对于处理失败的PDF，返回None
                    all_middle_json.append(None)
                    continue

                # 获取当前PDF的图像数量
                current_pdf_images_count = images_count_per_pdf[i]

                if current_pdf_images_count == 0:
                    # 对于没有图像的PDF，返回None
                    all_middle_json.append(None)
                    continue

                # 获取当前PDF的图像列表和结果
                current_images_list = all_images_list[image_idx: image_idx + current_pdf_images_count]
                current_results = results[image_idx: image_idx + current_pdf_images_count]

                # 为当前PDF生成middle_json
                from mineru.backend.vlm.vlm_analyze import result_to_middle_json
                image_writer = image_writers[i] if i < len(image_writers) else None
                middle_json = result_to_middle_json(current_results, current_images_list, pdf_doc, image_writer)
                all_middle_json.append(middle_json)

                # 更新图像索引
                image_idx += current_pdf_images_count

        # 保存结果
        final_results = []
        for i, (middle_json, is_success) in enumerate(zip(all_middle_json, pdf_processing_status)):
            if not is_success:
                # 对于预处理失败的PDF，跳过保存
                continue

            # 从原始batch信息中获取PDF路径
            if 'files' in batch and i < len(batch['files']):
                pdf_path = batch['files'][i]
            else:
                continue

            pdf_file_name = os.path.basename(pdf_path).replace(".pdf", "")

            if middle_json is not None:
                infer_result = {"middle_json": middle_json}
                res_json_str = json.dumps(infer_result, ensure_ascii=False)

                # 保存为压缩文件
                result_dir = f"{save_dir}/result"
                if not os.path.exists(result_dir):
                    os.makedirs(result_dir, exist_ok=True)
                target_file = f"{result_dir}/{pdf_file_name}.json.zip"
                with zipfile.ZipFile(target_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    res_json_bytes = res_json_str.encode("utf-8")
                    zf.writestr(f"{pdf_file_name}.json", res_json_bytes)

                page_count = get_pdf_page_count(pdf_path)
                file_size = os.path.getsize(target_file)
                result = {
                    'input_path': pdf_path,
                    'output_path': target_file,
                    'page_count': page_count,
                    'file_size': file_size,
                    'success': True
                }
            else:
                result = {
                    'input_path': pdf_path,
                    'output_path': None,
                    'success': False
                }

            # 保存页面结果信息
            page_result_path = f"{save_dir}/page_result"
            if not os.path.exists(page_result_path):
                os.makedirs(page_result_path, exist_ok=True)
            json_file_name = f"{pdf_file_name}.json"
            temp_json_path = os.path.join(page_result_path, json_file_name)
            with open(temp_json_path, 'w') as f:
                json.dump(result, f)
            final_results.append(result)

        total_time = time.time() - start
        logging.info(f"GPU处理完成，总耗时{total_time:.2f}秒")

        return {
            'success': True,
            'results': final_results,
            'preprocess_time': preprocessed_data.get('preprocess_time', 0),
            'image_loading_time': preprocessed_data.get('image_loading_time', 0),
            'gpu_time': gpu_time if 'gpu_time' in locals() else 0,
            'total_preprocess_time': preprocessed_data.get('total_preprocess_time', 0),
            'total_time': total_time,
            'batch_info': batch
        }

    except Exception as e:
        error_time = time.time() - start
        logging.error(f"GPU处理失败: {e}")
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'error_time': error_time,
            'batch_info': batch
        }


def gpu_processing_task(preprocessed_data, **kwargs):
    """
    GPU处理函数 - 使用GPU进行文档分析并保存结果
    这部分工作需要GPU，处理预处理后的数据
    """
    start = time.time()
    pdf_bytes_list = preprocessed_data['pdf_bytes_list']
    image_writers = preprocessed_data['image_writers']
    pdf_paths = preprocessed_data['pdf_paths']
    save_dir = preprocessed_data['save_dir']
    batch = preprocessed_data['batch_info']

    logging.info(f"GPU处理开始: {batch.get('file_names', [])}")

    try:
        backend = os.environ.get("BACKEND", "vllm-engine")
        logging.info(f"backend: {backend}")

        # 调用batch_doc_analyze进行GPU分析
        from mineru.backend.vlm.vlm_analyze import batch_doc_analyze
        gpu_memory_utilization = os.environ.get("GPU_MEMORY_UTILIZATION", 0.5)

        gpu_start = time.time()
        all_middle_json, _ = batch_doc_analyze(
            pdf_bytes_list=pdf_bytes_list,
            image_writer_list=image_writers,
            backend=backend,
            server_url=None,
            gpu_memory_utilization=gpu_memory_utilization
        )
        gpu_time = time.time() - gpu_start
        logging.info(f"GPU分析完毕，耗时{gpu_time:.2f}秒")

        # 保存结果
        results = []
        for pdf_path, middle_json in zip(pdf_paths, all_middle_json):
            pdf_file_name = os.path.basename(pdf_path).replace(".pdf", "")
            if middle_json is not None:
                infer_result = {"middle_json": middle_json}
                res_json_str = json.dumps(infer_result, ensure_ascii=False)

                # 保存为压缩文件
                result_dir = f"{save_dir}/result"
                if not os.path.exists(result_dir):
                    os.makedirs(result_dir, exist_ok=True)
                target_file = f"{result_dir}/{pdf_file_name}.json.zip"
                with zipfile.ZipFile(target_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    res_json_bytes = res_json_str.encode("utf-8")
                    zf.writestr(f"{pdf_file_name}.json", res_json_bytes)

                page_count = get_pdf_page_count(pdf_path)
                file_size = os.path.getsize(target_file)
                result = {
                    'input_path': pdf_path,
                    'output_path': target_file,
                    'page_count': page_count,
                    'file_size': file_size,
                    'success': True
                }
            else:
                result = {
                    'input_path': pdf_path,
                    'output_path': None,
                    'success': False
                }

            # 保存页面结果信息
            page_result_path = f"{save_dir}/page_result"
            if not os.path.exists(page_result_path):
                os.makedirs(page_result_path, exist_ok=True)
            json_file_name = f"{pdf_file_name}.json"
            temp_json_path = os.path.join(page_result_path, json_file_name)
            with open(temp_json_path, 'w') as f:
                json.dump(result, f)
            results.append(result)

        total_time = time.time() - start
        logging.info(f"GPU处理完成，总耗时{total_time:.2f}秒")

        return {
            'success': True,
            'results': results,
            'preprocess_time': preprocessed_data['preprocess_time'],
            'gpu_time': gpu_time,
            'total_time': total_time,
            'batch_info': batch
        }

    except Exception as e:
        error_time = time.time() - start
        logging.error(f"GPU处理失败: {e}")
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'error_time': error_time,
            'batch_info': batch
        }


def gpu_worker_task(batch, save_dir, **kwargs):
    """
    GPU工作进程的任务函数 - 适配双缓冲系统
    现在这个函数调用增强预处理任务（包含图像加载），预处理结果会被放入GPU队列
    """

    logging.info(f"GPU worker task 开始增强预处理: {batch.get('file_names', [])}")
    try:
        # 执行增强预处理任务（包含图像加载）
        preprocessed_data = preprocessing_task_with_image_loading(batch, save_dir, **kwargs)
        logging.info(f"增强预处理完成，准备提交到GPU队列")
        return preprocessed_data
    except Exception as e:
        logging.error(f"增强预处理失败: {e}")
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'batch_info': batch
        }


def create_batches_by_pages(pdf_files, batch_size, output_path, max_pages_per_pdf=1000):
    """
    根据页数创建批次
    :param pdf_files: PDF文件列表
    :param batch_size: 每批次最大页数
    :return: 批次列表，每个批次包含文件列表和总页数
    """
    batches = []
    current_batch = []
    current_batch_pages = 0

    logging.info(f"📦 按页数分批 (每批最多 {batch_size} 页):")

    for i, pdf_file in enumerate(pdf_files):
        page_count = get_pdf_page_count(pdf_file)

        if page_count > max_pages_per_pdf:
            continue
        pdf_file_name = os.path.basename(pdf_file).replace(".pdf", "")
        # #分页时提前记录结果文件页数
        #
        # target_file = f"{output_path}/{pdf_file_name}.json.zip"
        # page_info = {
        #     'input_path': pdf_file,
        #     'output_path': target_file,
        #     'page_count': page_count,
        # }
        # page_result_path = f"{output_path}/page_result"
        # if not os.path.exists(page_result_path):
        #     os.makedirs(page_result_path, exist_ok=True)
        # json_file_name = f"{pdf_file_name}.json"
        # temp_json_path = os.path.join(page_result_path, json_file_name)
        # with open(temp_json_path, 'w') as f:
        #     json.dump(page_info, f)

        # 如果单个文件就超过批次大小，单独作为一批
        if page_count >= batch_size:
            if current_batch:  # 先处理当前批次
                batches.append({
                    'files': current_batch.copy(),
                    'total_pages': current_batch_pages,
                    'file_names': [os.path.basename(f) for f in current_batch]
                })
                logging.info(f"  批次 {len(batches)}: {len(current_batch)} 个文件, {current_batch_pages} 页")
                current_batch = []
                current_batch_pages = 0

            # 大文件单独一批
            batches.append({
                'files': [pdf_file],
                'total_pages': page_count,
                'file_names': [pdf_file_name]
            })
            logging.info(f"  批次 {len(batches)}: {pdf_file}, {page_count} 页 (大文件单独批次)")
            continue

        # 如果当前批次加上这个文件会超过限制，先处理当前批次
        if current_batch_pages + page_count > batch_size:
            batches.append({
                'files': current_batch.copy(),
                'total_pages': current_batch_pages,
                'file_names': [os.path.basename(f) for f in current_batch]
            })
            logging.info(f"  批次 {len(batches)}: {len(current_batch)} 个文件, {current_batch_pages} 页")
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
            'file_names': [os.path.basename(f) for f in current_batch]
        })
        logging.info(f"  批次 {len(batches)}: {len(current_batch)} 个文件, {current_batch_pages} 页")

    return batches


class SimpleMinerUPool:
    """修复的MinerU处理池 - 简化版本"""

    def __init__(self, gpu_ids: List[int], workers_per_gpu: int = 2,
                 vram_size_gb: int = 24, max_pages_per_pdf: Optional[int] = None,
                 batch_size: Optional[int] = None):
        self.gpu_ids = gpu_ids
        self.workers_per_gpu = workers_per_gpu
        self.vram_size_gb = vram_size_gb
        self.max_pages_per_pdf = max_pages_per_pdf
        self.batch_size = batch_size

        # 设置环境变量 - 增加内存使用配置
        os.environ["MINERU_VIRTUAL_VRAM_SIZE"] = str(vram_size_gb)
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

        # 设置batch相关环境变量
        if batch_size is not None:
            os.environ['MINERU_MIN_BATCH_INFERENCE_SIZE'] = str(batch_size)
            logging.info(f"Set batch size to: {batch_size}")

        # 创建基于GPU ID的进程池
        self.process_pool = SimpleProcessPool(gpu_ids=gpu_ids, workers_per_gpu=workers_per_gpu)
        logging.info(
            f"Created MinerU pool: {len(gpu_ids)} GPUs × {workers_per_gpu} workers = {len(gpu_ids) * workers_per_gpu} total workers")

    def process_pdf_files(self, pdf_files: List[str], output_dir: str) -> List[Dict]:
        """处理PDF文件列表 - 简化版本"""
        logging.info(f"Processing {len(pdf_files)} PDF files using {len(self.gpu_ids)} GPUs...")

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 过滤已处理的文件
        files_to_process = []
        for pdf_path in pdf_files:
            pdf_name = os.path.basename(pdf_path).replace(".pdf", "")
            target_file = f"{output_dir}/result/{pdf_name}.json.zip"
            if os.path.exists(target_file):
                logging.info(f"Already processed: {pdf_path} -> {target_file}")
                continue
            files_to_process.append(pdf_path)

        if not files_to_process:
            logging.warning("No files need processing")
            return []

        logging.info(f"After filtering: {len(files_to_process)} files to process")

        results = []
        task_info = {}  # 存储任务ID和输入路径的映射

        try:
            # 提交所有任务
            batch_size = int(os.environ.get('DEFAULT_BATCH_SIZE', '384'))
            start = time.time()
            batches = create_batches_by_pages(files_to_process, batch_size, output_dir)
            logging.info(f"分批耗时：{time.time() - start}")
            for batch in batches:
                task_data = (batch, output_dir)
                task_id = self.process_pool.submit_task(gpu_worker_task, *task_data)
                task_info[task_id] = batch

            logging.info(f"Submitted {len(batches)} tasks to process pool")

            # 设置完成信号
            self.process_pool.set_complete_signal()

            # 收集结果
            start_time = time.time()

            # 等待所有任务完成
            for _ in range(len(batches)):
                result = self.process_pool.get_result()
                if result:
                    task_id, status, data = result
                    pdf_path = task_info.get(task_id, "unknown")

                    if status == 'success':
                        results.append(data)
                        logging.info(f"Task completed: {pdf_path}")
                    elif status == 'error':
                        error_result = {
                            'success': False,
                            'error': data,
                            'input_path': pdf_path
                        }
                        results.append(error_result)
                        logging.error(f"Task failed: {pdf_path} with error: {data}")

            total_time = time.time() - start_time
            success_count = sum(1 for r in results if r.get('success', False))
            skipped_count = sum(1 for r in results if r.get('skipped', False))

            logging.info(f"\nProcessing complete!")
            logging.info(f"Total time: {total_time:.1f} seconds")
            logging.info(
                f"Success: {success_count}, Skipped: {skipped_count}, Errors: {len(results) - success_count - skipped_count}")

            if success_count > 0:
                logging.info(f"Average: {total_time / success_count:.2f} seconds per successful file")

            return results

        except Exception as e:
            logging.error(f"Unexpected error in process_pdf_files: {e}")
            traceback.print_exc()
            return results
        finally:
            logging.info("Shutting down process pool...")
            self.process_pool.shutdown()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 确保进程池被正确关闭
        if hasattr(self, 'process_pool'):
            self.process_pool.shutdown()


def process_pdfs(input_dir, output_dir, gpu_ids='0,1,2,3,4,5,6,7', workers_per_gpu=2,
                 vram_size_gb=24, max_pages=None, shuffle=False,
                 batch_size=None):
    """处理PDF文件的函数，可通过参数直接调用"""
    # 解析GPU ID
    gpu_ids = [int(x.strip()) for x in gpu_ids.split(',')]

    # 获取PDF文件
    pdf_files = glob.glob(f"{input_dir}/*.pdf")
    logging.info(f"Found {len(pdf_files)} PDF files")
    logging.info(f"Using GPUs: {gpu_ids}")
    logging.info(f"Workers per GPU: {workers_per_gpu}")
    logging.info(f"Max pages per PDF: {max_pages or 'No limit'}")

    if not pdf_files:
        logging.warning("No PDF files found!")
        return

    # 创建处理池并运行
    with SimpleMinerUPool(
            gpu_ids=gpu_ids,
            workers_per_gpu=workers_per_gpu,
            vram_size_gb=vram_size_gb,
            max_pages_per_pdf=max_pages,
            batch_size=batch_size
    ) as pool:
        results = pool.process_pdf_files(pdf_files, output_dir)

    return results

