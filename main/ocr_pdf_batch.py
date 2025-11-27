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


def gpu_worker_task(batch, save_dir, **kwargs):
    """
    GPU工作进程的任务函数 - 简化版本
    每个工作进程处理单个PDF文件
    """

    backend = os.environ.get("BACKEND", "pipeline")
    logging.info(f"backend: {backend}")
    try:
        # 执行PDF处理
        process_batch_pdf_files(batch, save_dir, backend)
        return {
            'success': False,
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
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

