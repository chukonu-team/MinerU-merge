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

# 导入简化的进程池
from process_pool import SimpleProcessPool
from s3_util import upload_to_s3


def get_pdf_page_count(pdf_path):
    """使用fitz获取PDF页数"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        doc.close()
        return page_count
    except Exception as e:
        print(f"Error getting page count for {pdf_path}: {e}")
        return 0


def infer_one_pdf(save_dir , pdf_file_path, lang="en" , backend="pipeline"):
    """PDF推理处理 - 核心计算逻辑"""
    try:
        from mineru.data.data_reader_writer import FileBasedDataWriter
        from mineru.backend.pipeline.model_json_to_middle_json import \
            result_to_middle_json as pipeline_result_to_middle_json
        from mineru.backend.pipeline.pipeline_analyze import doc_analyze as pipeline_doc_analyze
        from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2
        from mineru.backend.vlm.vlm_analyze import doc_analyze as vlm_doc_analyze

        with open(pdf_file_path, 'rb') as fi:
            pdf_bytes = fi.read()

        new_pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes)
        pdf_name = os.path.basename(pdf_file_path)

        local_image_dir = f"{save_dir}/img/{pdf_name}"
        if not os.path.exists(local_image_dir):
            os.makedirs(local_image_dir, exist_ok=True)

        image_writer = FileBasedDataWriter(local_image_dir)

        if backend == "pipeline":
            formula_enable = True
            table_enable = True
            infer_results, all_image_lists, all_pdf_docs, lang_list, ocr_enabled_list = (
                pipeline_doc_analyze(
                    [new_pdf_bytes],
                    [lang],
                    parse_method="ocr",
                    formula_enable=formula_enable,
                    table_enable=table_enable
                )
            )

            # 获取mineru解析的实际页数
            page_count = len(all_pdf_docs[0]) if all_pdf_docs else 0
            model_list = infer_results[0]
            images_list = all_image_lists[0]
            pdf_doc = all_pdf_docs[0]
            _ocr_enable = True
            model_json = copy.deepcopy(model_list)

            middle_json = pipeline_result_to_middle_json(
                model_list, images_list, pdf_doc, image_writer,
                lang, _ocr_enable, formula_enable
            )

            ocr_result = {
                "middle_json": middle_json,
                "model_json": model_json,
                "page_count": page_count
            }
            return ocr_result
        else:
            gpu_memory_utilization = os.environ.get("GPU_MEMORY_UTILIZATION",0.5)
            middle_json, infer_result = vlm_doc_analyze(new_pdf_bytes,
                                                        image_writer=image_writer,
                                                        backend=backend,
                                                        gpu_memory_utilization=gpu_memory_utilization
                                                        )

            ocr_result = {
                "middle_json": middle_json
            }
            return ocr_result


    except Exception as e:
        print(f"Error in infer_one_pdf for {pdf_file_path}: {e}")
        traceback.print_exc()
        return {
            'error': str(e),
            'traceback': traceback.format_exc()
        }


def process_one_pdf_file(pdf_path, save_dir, lang="en", max_pages_per_pdf=1000 , backend="pipeline"):
    """处理单个PDF文件 - 修改版本：提前进行页数检查"""
    fitz_page_count = 0
    pdf_file_name = None
    try:
        result_dir = f"{save_dir}/result"
        if not os.path.exists(result_dir):
            os.makedirs(result_dir, exist_ok=True)

        pdf_file_name = os.path.basename(pdf_path).replace(".pdf", "")
        target_file = f"{result_dir}/{pdf_file_name}.json.zip"

        # 提前使用fitz检查页数
        if max_pages_per_pdf is not None:
            fitz_page_count = get_pdf_page_count(pdf_path)
            if fitz_page_count is not None and fitz_page_count > max_pages_per_pdf:
                print(f"PDF {pdf_path} has {fitz_page_count} pages (limit: {max_pages_per_pdf}), skipped")
                return {
                    'success': False,
                    'input_path': pdf_path,
                    'output_path': None,
                    'page_count': fitz_page_count,
                    'file_size': 0,
                    'skipped': True,
                    'reason': f'Exceeded page limit: {fitz_page_count} > {max_pages_per_pdf}'
                }
            elif fitz_page_count is None:
                print(f"Warning: Could not get page count using fitz for {pdf_path}, will proceed and use mineru page count")

        # 执行OCR推理
        infer_result = infer_one_pdf(save_dir,pdf_path, lang=lang,backend=backend)

        # 处理错误情况
        if 'error' in infer_result:
            error_msg = infer_result['error']
            return {
                'input_path': pdf_path,
                'output_path': None,
                'success': False,
                'error': error_msg,
                'traceback': infer_result.get('traceback', '')
            }

        # 添加PDF路径信息
        infer_result['pdf_path'] = pdf_path
        mineru_page_count = infer_result.get('page_count', fitz_page_count)
        res_json_str = json.dumps(infer_result, ensure_ascii=False)

        # 保存为压缩文件
        with zipfile.ZipFile(target_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            res_json_bytes = res_json_str.encode("utf-8")
            zf.writestr(f"{pdf_file_name}.json", res_json_bytes)

        file_size = os.path.getsize(target_file)
        print(f"Finished processing: {pdf_path} -> {target_file} ({file_size} bytes)")
        print(f"Page count: {mineru_page_count}")

        result = {
            'input_path': pdf_path,
            'output_path': target_file,
            'page_count': mineru_page_count,
            'file_size': file_size,
            'success': True
        }

    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
        traceback.print_exc()
        result = {
            'input_path': pdf_path,
            'output_path': None,
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }

    if pdf_file_name:
        page_result_path = f"{save_dir}/page_result"
        if not os.path.exists(page_result_path):
            os.makedirs(page_result_path, exist_ok=True)
        json_file_name = f"{pdf_file_name}.json"
        temp_json_path = os.path.join(page_result_path, json_file_name)
        with open(temp_json_path, 'w') as f:
            json.dump(result, f)

    return result


def gpu_worker_task(pdf_path, save_dir, max_pages_per_pdf=None, gpu_id=None):
    """
    GPU工作进程的任务函数 - 简化版本
    每个工作进程处理单个PDF文件
    """
    if gpu_id is None:
        gpu_id = os.environ.get("CUDA_VISIBLE_DEVICES", "unknown")

    backend = os.environ.get("BACKEND", "pipeline")
    try:
        # 执行PDF处理
        result = process_one_pdf_file(pdf_path, save_dir, max_pages_per_pdf=max_pages_per_pdf , backend=backend)
        result['gpu_id'] = gpu_id
        return result
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'input_path': pdf_path,
            'gpu_id': gpu_id,
            'traceback': traceback.format_exc()
        }


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
            print(f"Set batch size to: {batch_size}")

        # 创建基于GPU ID的进程池
        self.process_pool = SimpleProcessPool(gpu_ids=gpu_ids, workers_per_gpu=workers_per_gpu)
        print(
            f"Created MinerU pool: {len(gpu_ids)} GPUs × {workers_per_gpu} workers = {len(gpu_ids) * workers_per_gpu} total workers")

    def process_pdf_files(self, pdf_files: List[str], output_dir: str) -> List[Dict]:
        """处理PDF文件列表 - 简化版本"""
        print(f"Processing {len(pdf_files)} PDF files using {len(self.gpu_ids)} GPUs...")

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 过滤已处理的文件
        files_to_process = []
        for pdf_path in pdf_files:
            pdf_name = os.path.basename(pdf_path).replace(".pdf", "")
            target_file = f"{output_dir}/result/{pdf_name}.json.zip"
            if os.path.exists(target_file):
                print(f"Already processed: {pdf_path} -> {target_file}")
                continue
            files_to_process.append(pdf_path)

        if not files_to_process:
            print("No files need processing")
            return []

        print(f"After filtering: {len(files_to_process)} files to process")

        results = []
        task_info = {}  # 存储任务ID和输入路径的映射

        try:
            # 提交所有任务
            for pdf_path in files_to_process:
                task_data = (pdf_path, output_dir, self.max_pages_per_pdf)
                task_id = self.process_pool.submit_task(gpu_worker_task, *task_data)
                task_info[task_id] = pdf_path

            print(f"Submitted {len(files_to_process)} tasks to process pool")

            # 设置完成信号
            self.process_pool.set_complete_signal()

            # 收集结果
            start_time = time.time()

            # 等待所有任务完成
            for _ in range(len(files_to_process)):
                result = self.process_pool.get_result()
                if result:
                    task_id, status, data = result
                    pdf_path = task_info.get(task_id, "unknown")

                    if status == 'success':
                        results.append(data)
                        print(f"Task completed: {pdf_path}")
                    elif status == 'error':
                        error_result = {
                            'success': False,
                            'error': data,
                            'input_path': pdf_path
                        }
                        results.append(error_result)
                        print(f"Task failed: {pdf_path} with error: {data}")

            total_time = time.time() - start_time
            success_count = sum(1 for r in results if r.get('success', False))
            skipped_count = sum(1 for r in results if r.get('skipped', False))

            print(f"\nProcessing complete!")
            print(f"Total time: {total_time:.1f} seconds")
            print(
                f"Success: {success_count}, Skipped: {skipped_count}, Errors: {len(results) - success_count - skipped_count}")

            if success_count > 0:
                print(f"Average: {total_time / success_count:.2f} seconds per successful file")

            return results

        except Exception as e:
            print(f"Unexpected error in process_pdf_files: {e}")
            traceback.print_exc()
            return results
        finally:
            print("Shutting down process pool...")
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
    print(f"Found {len(pdf_files)} PDF files")
    print(f"Using GPUs: {gpu_ids}")
    print(f"Workers per GPU: {workers_per_gpu}")
    print(f"Max pages per PDF: {max_pages or 'No limit'}")

    if not pdf_files:
        print("No PDF files found!")
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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fixed MinerU PDF Processing")
    parser.add_argument('--input-dir', type=str, required=True)
    parser.add_argument('--output-dir', type=str, required=True)
    parser.add_argument('--gpu-ids', type=str, default='0,1,2,3,4,5,6,7')
    parser.add_argument('--workers-per-gpu', type=int, default=2)
    parser.add_argument('--vram-size-gb', type=int, default=8)
    parser.add_argument('--max-pages', type=int, default=None)
    parser.add_argument('--shuffle', action='store_true')
    parser.add_argument('--batch-size', type=int, default=None)
    args = parser.parse_args()

    process_pdfs(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        gpu_ids=args.gpu_ids,
        workers_per_gpu=args.workers_per_gpu,
        vram_size_gb=args.vram_size_gb,
        max_pages=args.max_pages,
        shuffle=args.shuffle,
        batch_size=args.batch_size
    )