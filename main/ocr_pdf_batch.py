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
from mineru.data.data_reader_writer import FileBasedDataWriter
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


def preprocessing_worker(batch, save_dir, **kwargs):
    """
    增强版预处理函数 - 读取PDF文件、转换为字节格式、加载图像
    这部分工作包含load_images_from_pdf，不依赖GPU，可以在CPU上并行处理
    """
    start = time.time()
    logging.info(f"增强预处理批次开始: {batch.get('file_names', [])}")

    pdf_bytes_list = []
    local_image_dirs = []
    pdf_paths = batch['files'].copy()

    read_start = time.time()

    # 读取PDF文件并转换为字节格式
    for pdf_path in pdf_paths:
        try:
            pdf_bytes = read_fn(pdf_path)
            pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)
            pdf_bytes_list.append(pdf_bytes)
            pdf_name = os.path.basename(pdf_path)
            local_image_dir = f"/tmp/data/mineru_ocr_local_image_dir/{pdf_name}"
            if not os.path.exists(local_image_dir):
                os.makedirs(local_image_dir, exist_ok=True)
            local_image_dirs.append(local_image_dir)
        except Exception as e:
            logging.warning(f"加载 {pdf_path} 失败: {e}")
            traceback.print_exc()
            # 使用None填充占位，保持列表长度一致
            pdf_bytes_list.append(None)
            pdf_name = os.path.basename(pdf_path)
            local_image_dir = f"/tmp/data/mineru_ocr_local_image_dir/{pdf_name}"
            if not os.path.exists(local_image_dir):
                os.makedirs(local_image_dir, exist_ok=True)
            local_image_dirs.append(local_image_dir)

    preprocess_time = time.time() - read_start
    logging.info(f"PDF读取完毕，耗时{preprocess_time:.2f}秒")

    # 加载图像（这部分原在batch_doc_analyze中）
    image_loading_start = time.time()
    from mineru.backend.vlm.vlm_analyze import load_images_from_pdf
    from mineru.utils.enum_class import ImageType

    all_images_list = []
    images_count_per_pdf = []
    pdf_processing_status = []

    # 遍历所有PDF文档，加载图像（使用BYTES格式以支持序列化）
    for pdf_bytes in pdf_bytes_list:
        if pdf_bytes is None:
            # PDF字节数据为空，直接标记为失败
            images_count_per_pdf.append(0)
            pdf_processing_status.append(False)
            continue

        try:
            images_list, pdf_doc = load_images_from_pdf(pdf_bytes, image_type=ImageType.BYTES)
            all_images_list.extend(images_list)
            images_count_per_pdf.append(len(images_list))
            pdf_processing_status.append(True)  # 标记为成功处理
            # 立即关闭pdf_doc对象，避免序列化问题
            if pdf_doc is not None:
                try:
                    pdf_doc.close()
                except:
                    pass
        except Exception as e:
            logging.warning(f"从PDF加载图像失败: {e}")
            images_count_per_pdf.append(0)  # 图像数量为0
            pdf_processing_status.append(False)  # 标记为处理失败

    image_loading_time = time.time() - image_loading_start
    logging.info(f"图像加载完毕，耗时{image_loading_time:.2f}秒")

    # 直接使用pdf_bytes，避免序列化问题
    logging.info(f"使用pdf_bytes方式，避免pdf_doc序列化问题")



    total_preprocess_time = time.time() - start
    logging.info(f"增强预处理完成，总耗时{total_preprocess_time:.2f}秒，有效图像数: {len(all_images_list)}")

    # 过滤掉无效的PDF，只保留成功的
    valid_indices = [i for i, status in enumerate(pdf_processing_status) if status]
    valid_pdf_bytes_list = [pdf_bytes_list[i] for i in valid_indices]
    valid_local_image_dirs = [local_image_dirs[i] for i in valid_indices]
    valid_pdf_paths = [pdf_paths[i] for i in valid_indices]
    valid_images_count_per_pdf = [images_count_per_pdf[i] for i in valid_indices]
    valid_pdf_processing_status = [pdf_processing_status[i] for i in valid_indices]

    # 重新构建有效的all_images_list，只包含成功PDF的图像
    valid_all_images_list = []
    image_idx = 0
    for i, count in enumerate(images_count_per_pdf):
        if pdf_processing_status[i] and count > 0:
            # 添加当前PDF的所有图像到有效列表
            valid_all_images_list.extend(all_images_list[image_idx:image_idx + count])
        image_idx += count

    successful_count = len(valid_indices)
    total_count = len(pdf_paths)

    logging.info(f"过滤结果: 成功 {successful_count}/{total_count} 个PDF，有效图像数: {len(valid_all_images_list)}")
    if successful_count < total_count:
        failed_indices = [i for i, status in enumerate(pdf_processing_status) if not status]
        failed_files = [os.path.basename(pdf_paths[i]) for i in failed_indices]
        logging.warning(f"跳过的文件: {failed_files}")

    # 返回过滤后的预处理数据（只包含成功的PDF）
    return {
        'pdf_bytes_list': valid_pdf_bytes_list,
        'local_image_dirs': valid_local_image_dirs,
        'pdf_paths': valid_pdf_paths,
        'save_dir': save_dir,
        'preprocess_time': preprocess_time,
        'image_loading_time': image_loading_time,
        'total_preprocess_time': total_preprocess_time,
        'all_images_list': valid_all_images_list,  # 只包含成功PDF的bytes图像数据
        'images_count_per_pdf': valid_images_count_per_pdf,
        'pdf_processing_status': valid_pdf_processing_status,  # 现在全部为True
        'images_pil_list': [],  # 清空PIL图像列表，避免序列化问题
        'batch_info': batch,
        'original_batch_size': total_count,  # 保存原始批次大小用于日志
        'successful_count': successful_count  # 保存成功数量
    }



def gpu_processing_task_with_preloaded_images(preprocessed_data, **kwargs):
    """
    GPU处理函数 - 使用GPU进行文档分析的第一阶段（只包含batch_two_step_extract）
    这部分工作需要GPU，只处理推理部分，结果保存交给后处理CPU队列
    预处理阶段已经过滤掉无效PDF，这里只处理有效的数据
    """
    start = time.time()
    logging.info(f"=== GPU处理阶段1详细时间分析开始 ===")

    # 从预处理数据中获取所有必要信息（已经是过滤后的有效数据）
    all_images_list = preprocessed_data['all_images_list']
    pdf_bytes_list = preprocessed_data['pdf_bytes_list']  # PDF字节数据
    images_count_per_pdf = preprocessed_data['images_count_per_pdf']
    pdf_processing_status = preprocessed_data['pdf_processing_status']  # 现在应该全部为True
    save_dir = preprocessed_data['save_dir']
    local_image_dirs = preprocessed_data['local_image_dirs']
    batch = preprocessed_data['batch_info']

    original_batch_size = preprocessed_data.get('original_batch_size', 0)
    successful_count = preprocessed_data.get('successful_count', 0)

    logging.info(f"GPU处理开始: 原始批次{original_batch_size}个文件，成功{successful_count}个，有效图像数: {len(all_images_list)}")

    # 如果没有有效图像，直接返回空结果
    if not all_images_list:
        logging.warning("没有有效图像，跳过GPU处理")
        return {
            'success': True,
            'gpu_results': [],
            'preprocess_time': preprocessed_data.get('preprocess_time', 0),
            'image_loading_time': preprocessed_data.get('image_loading_time', 0),
            'total_preprocess_time': preprocessed_data.get('total_preprocess_time', 0),
            'total_time': time.time() - start,
            'data_preprocess_time': 0,
            'model_init_time': 0,
            'gpu_time': 0,
            'batch_info': batch,
            'all_images_list': all_images_list,
            'pdf_bytes_list': pdf_bytes_list,
            'images_count_per_pdf': images_count_per_pdf,
            'pdf_processing_status': pdf_processing_status,
            'save_dir': save_dir,
            'local_image_dirs': local_image_dirs
        }

    try:
        # 步骤1: 数据预处理 - 从bytes图像数据重建PIL图像列表
        data_preprocess_start = time.time()
        images_pil_list = []

        # 转换bytes图像数据为PIL格式（所有数据都是有效的）
        for image_dict in all_images_list:
            try:
                from mineru.utils.pdf_reader import bytes_to_pil
                pil_img = bytes_to_pil(image_dict["img_bytes"])
                images_pil_list.append(pil_img)
            except Exception as e:
                logging.warning(f"转换bytes图像到PIL失败: {e}")

        data_preprocess_time = time.time() - data_preprocess_start
        logging.info(f"步骤1 - 数据预处理 (bytes→PIL转换): {data_preprocess_time:.2f}秒，转换图像数: {len(images_pil_list)}")

        # 步骤2: 模型初始化
        model_init_start = time.time()
        backend = os.environ.get("BACKEND", "vllm-engine")
        logging.info(f"backend: {backend}")

        # 过滤掉不支持的参数，只传递有效的GPU配置
        filtered_kwargs = kwargs.copy()
        gpu_memory_utilization = os.environ.get("GPU_MEMORY_UTILIZATION",0.5)
        if 'gpu_id' in filtered_kwargs:
            del filtered_kwargs['gpu_id']  # vLLM不支持gpu_id参数

        from mineru.backend.vlm.vlm_analyze import ModelSingleton

        predictor = ModelSingleton().get_model(backend, None, None, gpu_memory_utilization=gpu_memory_utilization, **filtered_kwargs)
        model_init_time = time.time() - model_init_start
        logging.info(f"步骤2 - 模型初始化: {model_init_time:.2f}秒")

        # 步骤3: GPU推理 - 只调用batch_two_step_extract
        gpu_start = time.time()
        gpu_results = predictor.batch_two_step_extract(images=images_pil_list)
        gpu_time = time.time() - gpu_start
        logging.info(f"步骤3 - GPU推理 (纯AI模型推理): {gpu_time:.2f}秒，推理结果数: {len(gpu_results)}")

        total_time = time.time() - start
        logging.info(f"GPU处理阶段1完成，总耗时{total_time:.2f}秒")

        # 详细时间分析汇总
        logging.info(f"=== GPU处理阶段1详细时间分析汇总 ===")
        logging.info(f"数据预处理 (bytes→PIL转换): {data_preprocess_time:.2f}秒 ({data_preprocess_time/total_time*100:.1f}%)")
        logging.info(f"模型初始化: {model_init_time:.2f}秒 ({model_init_time/total_time*100:.1f}%)")
        logging.info(f"GPU推理 (纯AI模型推理): {gpu_time:.2f}秒 ({gpu_time/total_time*100:.1f}%)")

        # 验证GPU结果数量与图像数量匹配
        if len(gpu_results) != len(images_pil_list):
            logging.warning(f"GPU结果数量({len(gpu_results)})与图像数量({len(images_pil_list)})不匹配")

        # 返回GPU处理结果，包含所有必要信息给后处理阶段
        return {
            'success': True,
            'gpu_results': gpu_results,
            'preprocess_time': preprocessed_data.get('preprocess_time', 0),
            'image_loading_time': preprocessed_data.get('image_loading_time', 0),
            'total_preprocess_time': preprocessed_data.get('total_preprocess_time', 0),
            'total_time': total_time,
            'data_preprocess_time': data_preprocess_time,
            'model_init_time': model_init_time,
            'gpu_time': gpu_time,
            'batch_info': batch,
            'all_images_list': all_images_list,
            'pdf_bytes_list': pdf_bytes_list,
            'images_count_per_pdf': images_count_per_pdf,
            'pdf_processing_status': pdf_processing_status,
            'save_dir': save_dir,
            'local_image_dirs': local_image_dirs
        }

    except Exception as e:
        error_time = time.time() - start
        logging.error(f"GPU处理阶段1失败: {e}")
        traceback.print_exc()
        # 即使GPU处理失败，也要返回错误信息给后处理阶段处理
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'error_time': error_time,
            'batch_info': batch,
            'all_images_list': all_images_list,
            'pdf_bytes_list': pdf_bytes_list,
            'images_count_per_pdf': images_count_per_pdf,
            'pdf_processing_status': pdf_processing_status,
            'save_dir': save_dir,
            'local_image_dirs': local_image_dirs
        }


def postprocessing_task(gpu_result_data, **kwargs):
    """
    后处理CPU队列任务函数 - 处理GPU结果后的文件保存等耗时操作
    这部分工作在CPU上处理，包括result_to_middle_json、JSON序列化、ZIP压缩写入等

    注意：现在接收到的是过滤后的数据，需要为所有原始文件生成结果（包括失败的）
    """
    start = time.time()
    logging.info(f"=== 后处理CPU任务开始 ===")

    # 从GPU处理结果中获取所有必要信息
    gpu_results = gpu_result_data.get('gpu_results', [])
    all_images_list = gpu_result_data.get('all_images_list', [])
    pdf_bytes_list = gpu_result_data.get('pdf_bytes_list', [])
    images_count_per_pdf = gpu_result_data.get('images_count_per_pdf', [])
    pdf_processing_status = gpu_result_data.get('pdf_processing_status', [])
    save_dir = gpu_result_data.get('save_dir')
    local_image_dirs = gpu_result_data.get('local_image_dirs', [])
    batch = gpu_result_data.get('batch_info', {})

    # 获取原始批次信息
    original_batch_size = gpu_result_data.get('original_batch_size', 0)
    successful_count = gpu_result_data.get('successful_count', 0)

    # 检查GPU处理是否成功
    gpu_success = gpu_result_data.get('success', False)
    gpu_error = gpu_result_data.get('error')

    logging.info(f"后处理开始: 原始批次{original_batch_size}个文件，成功{successful_count}个，GPU成功={gpu_success}")

    try:
        # 步骤1: 结果后处理 - 为每个PDF文档分别生成middle_json
        postprocess_start = time.time()
        all_middle_json = []
        image_idx = 0

        for i, is_success in enumerate(pdf_processing_status):
            logging.info(f"步骤1.1 loop index:{i} - 预处理成功: {is_success}")

            # 如果预处理失败，直接返回None
            if not is_success:
                all_middle_json.append(None)
                continue

            # 如果GPU处理失败，也返回None
            if not gpu_success:
                all_middle_json.append(None)
                continue

            # 获取当前PDF的图像数量
            current_pdf_images_count = images_count_per_pdf[i]
            if current_pdf_images_count == 0:
                # 对于没有图像的PDF，返回None
                all_middle_json.append(None)
                continue

            # 获取当前PDF的图像列表和结果
            # current_images_list = all_images_list[image_idx: image_idx + current_pdf_images_count]
            current_images_list = []
            for image_dict in all_images_list[image_idx: image_idx + current_pdf_images_count]:
                if image_dict and isinstance(image_dict, dict) and "img_bytes" in image_dict:
                    # 将bytes转换回PIL图像
                    try:
                        from mineru.utils.pdf_reader import bytes_to_pil
                        pil_img = bytes_to_pil(image_dict["img_bytes"])
                        current_images_list.append({"img_pil":pil_img,"scale":image_dict["scale"]})
                    except Exception as e:
                        logging.warning(f"转换bytes图像到PIL失败: {e}")





            current_gpu_results = gpu_results[image_idx: image_idx + current_pdf_images_count]

            # 为当前PDF生成middle_json，使用pdf_bytes避免序列化问题
            if i >= len(pdf_bytes_list):
                logging.error(f"索引超出范围: i={i}, len(pdf_bytes_list)={len(pdf_bytes_list)}")
                all_middle_json.append(None)
                continue

            pdf_bytes = pdf_bytes_list[i]
            if pdf_bytes is None:
                logging.error(f"PDF字节数据为空: i={i}")
                all_middle_json.append(None)
                continue

            try:
                from mineru.backend.vlm.vlm_analyze import result_to_middle_json
                import pypdfium2 as pdfium

                # 直接从pdf_bytes创建pdf_doc对象
                pdf_doc = pdfium.PdfDocument(pdf_bytes)
                local_image_dir = local_image_dirs[i]
                image_writer = FileBasedDataWriter(local_image_dir)
                try:
                    middle_json = result_to_middle_json(current_gpu_results, current_images_list, pdf_doc, image_writer)
                    all_middle_json.append(middle_json)
                    logging.info(f"成功生成middle_json for PDF {i} from bytes")
                finally:
                    # 确保文档对象被正确关闭
                    try:
                        pdf_doc.close()
                    except:
                        pass

            except Exception as create_doc_error:
                logging.error(f"从bytes创建PDF文档失败 {i}: {create_doc_error}")
                all_middle_json.append(None)

            # 更新图像索引
            image_idx += current_pdf_images_count

        postprocess_time = time.time() - postprocess_start
        logging.info(f"步骤1 - 结果后处理 (表格合并、标题优化等): {postprocess_time:.2f}秒")

        # 步骤2: 文件保存 - 保存结果
        file_save_start = time.time()
        final_results = []

        logging.info(f"=== 步骤2 - 文件保存详细调试开始 ===")
        logging.info(f"待处理文件数量: {len(all_middle_json)}")
        logging.info(f"预处理状态列表: {pdf_processing_status}")
        logging.info(f"batch信息: {batch}")

        for i, (middle_json, is_success) in enumerate(zip(all_middle_json, pdf_processing_status)):
            logging.info(f"--- 处理文件 {i+1}/{len(all_middle_json)} ---")
            logging.info(f"  预处理成功: {is_success}")
            logging.info(f"  middle_json是否为None: {middle_json is None}")

            if not is_success:
                logging.warning(f"  跳过文件 {i+1}: 预处理失败")
                continue

            # 从原始batch信息中获取PDF路径
            if 'files' in batch and i < len(batch['files']):
                pdf_path = batch['files'][i]
                logging.info(f"  PDF路径: {pdf_path}")
            else:
                logging.error(f"  无法获取PDF路径: batch['files']存在={('files' in batch)}, i={i}, len(batch['files'])={len(batch.get('files', []))}")
                continue

            pdf_file_name = os.path.basename(pdf_path).replace(".pdf", "")
            logging.info(f"  PDF文件名: {pdf_file_name}")

            if middle_json is not None:
                logging.info(f"  开始生成target_file...")

                try:
                    # 步骤2.1: 创建推理结果
                    infer_result = {"middle_json": middle_json}
                    logging.info(f"  步骤2.1 - 创建推理结果: 成功")

                    # 步骤2.2: JSON序列化
                    res_json_str = json.dumps(infer_result, ensure_ascii=False)
                    json_size = len(res_json_str.encode('utf-8'))
                    logging.info(f"  步骤2.2 - JSON序列化: 成功, 大小: {json_size} bytes")

                    # 步骤2.3: 创建结果目录
                    result_dir = f"{save_dir}/result"
                    if not os.path.exists(result_dir):
                        os.makedirs(result_dir, exist_ok=True)
                        logging.info(f"  步骤2.3 - 创建结果目录: {result_dir}")
                    else:
                        logging.info(f"  步骤2.3 - 结果目录已存在: {result_dir}")

                    # 步骤2.4: 构建target_file路径
                    target_file = f"{result_dir}/{pdf_file_name}.json.zip"
                    logging.info(f"  步骤2.4 - target_file路径: {target_file}")

                    # 步骤2.5: ZIP压缩写入
                    logging.info(f"  步骤2.5 - 开始ZIP压缩写入...")
                    with zipfile.ZipFile(target_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                        res_json_bytes = res_json_str.encode("utf-8")
                        zf.writestr(f"{pdf_file_name}.json", res_json_bytes)
                    logging.info(f"  步骤2.5 - ZIP压缩写入完成")

                    # 步骤2.6: 获取文件信息
                    page_count = get_pdf_page_count(pdf_path)
                    file_size = os.path.getsize(target_file)
                    logging.info(f"  步骤2.6 - 文件信息: 页数={page_count}, 文件大小={file_size} bytes")

                    # 步骤2.7: 创建成功结果
                    result = {
                        'input_path': pdf_path,
                        'output_path': target_file,
                        'page_count': page_count,
                        'file_size': file_size,
                        'success': True
                    }
                    logging.info(f"  步骤2.7 - 创建成功结果: {target_file}")

                except Exception as save_error:
                    logging.error(f"  ❌ 文件保存过程中发生错误: {save_error}")
                    logging.error(f"  详细错误堆栈:\n{traceback.format_exc()}")

                    # 步骤2.8: 创建失败结果
                    result = {
                        'input_path': pdf_path,
                        'output_path': None,
                        'success': False,
                        'save_error': str(save_error)
                    }
                    logging.info(f"  步骤2.8 - 创建失败结果")
            else:
                # GPU处理失败或middle_json为None的情况
                failure_reason = 'middle_json is None'
                if not gpu_success:
                    failure_reason = f'GPU processing failed: {gpu_error}'

                logging.warning(f"  无法保存文件: {failure_reason}")
                result = {
                    'input_path': pdf_path,
                    'output_path': None,
                    'success': False,
                    'reason': failure_reason
                }

            # 步骤2.9: 保存页面结果信息
            page_result_path = f"{save_dir}/page_result"
            if not os.path.exists(page_result_path):
                os.makedirs(page_result_path, exist_ok=True)
                logging.info(f"  步骤2.9 - 创建页面结果目录: {page_result_path}")

            json_file_name = f"{pdf_file_name}.json"
            temp_json_path = os.path.join(page_result_path, json_file_name)

            try:
                with open(temp_json_path, 'w') as f:
                    json.dump(result, f, indent=2)
                logging.info(f"  步骤2.9 - 保存页面结果文件: {temp_json_path}")
            except Exception as page_save_error:
                logging.error(f"  ❌ 保存页面结果文件失败: {page_save_error}")

            final_results.append(result)
            logging.info(f"  文件 {i+1} 处理完成，成功: {result['success']}")

        logging.info(f"=== 步骤2 - 文件保存详细调试结束 ===")
        success_count = sum(1 for r in final_results if r['success'])
        logging.info(f"文件保存统计: 成功 {success_count}/{len(final_results)} 个文件")

        file_save_time = time.time() - file_save_start
        logging.info(f"步骤2 - 文件保存 (JSON序列化、ZIP压缩写入): {file_save_time:.2f}秒")

        total_time = time.time() - start
        logging.info(f"后处理CPU任务完成，总耗时{total_time:.2f}秒")

        # 详细时间分析汇总
        logging.info(f"=== 后处理CPU任务详细时间分析汇总 ===")
        if 'postprocess_time' in locals():
            logging.info(f"结果后处理 (表格合并、标题优化等): {postprocess_time:.2f}秒 ({postprocess_time/total_time*100:.1f}%)")
        if 'file_save_time' in locals():
            logging.info(f"文件保存 (JSON序列化、ZIP压缩写入): {file_save_time:.2f}秒 ({file_save_time/total_time*100:.1f}%)")

        # 返回最终结果
        return {
            'success': True,
            'results': final_results,
            'preprocess_time': gpu_result_data.get('preprocess_time', 0),
            'image_loading_time': gpu_result_data.get('image_loading_time', 0),
            'gpu_time': gpu_result_data.get('gpu_time', 0),
            'total_preprocess_time': gpu_result_data.get('total_preprocess_time', 0),
            'total_time': total_time,
            'postprocess_time': postprocess_time if 'postprocess_time' in locals() else 0,
            'file_save_time': file_save_time if 'file_save_time' in locals() else 0,
            'batch_info': batch
        }

    except Exception as e:
        error_time = time.time() - start
        logging.error(f"后处理CPU任务失败: {e}")
        traceback.print_exc()

        # 即使后处理失败，也要为每个PDF创建失败结果
        error_results = []
        for i, is_success in enumerate(pdf_processing_status):
            if not is_success:
                continue

            if 'files' in batch and i < len(batch['files']):
                pdf_path = batch['files'][i]
                failure_reason = f'Postprocessing failed: {str(e)}'
                if not gpu_success:
                    failure_reason = f'GPU processing failed: {gpu_error}'

                error_results.append({
                    'input_path': pdf_path,
                    'output_path': None,
                    'success': False,
                    'reason': failure_reason
                })

                # 保存页面结果信息
                pdf_file_name = os.path.basename(pdf_path).replace(".pdf", "")
                page_result_path = f"{save_dir}/page_result"
                if not os.path.exists(page_result_path):
                    os.makedirs(page_result_path, exist_ok=True)

                json_file_name = f"{pdf_file_name}.json"
                temp_json_path = os.path.join(page_result_path, json_file_name)
                try:
                    with open(temp_json_path, 'w') as f:
                        json.dump(error_results[-1], f, indent=2)
                except:
                    pass

        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'error_time': error_time,
            'results': error_results,
            'batch_info': batch
        }



def gpu_worker_task(batch, save_dir, **kwargs):
    """
    GPU工作进程的任务函数 - 适配三级队列系统
    现在这个函数调用增强预处理任务（包含图像加载），预处理结果会被放入GPU队列
    """

    logging.info(f"GPU worker task 开始增强预处理: {batch.get('file_names', [])}")
    try:
        # 执行增强预处理任务（包含图像加载）
        preprocessed_data = preprocessing_worker(batch, save_dir, **kwargs)
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

        # 创建基于GPU ID的进程池 - 现在支持三级队列
        self.process_pool = SimpleProcessPool(gpu_ids=gpu_ids, workers_per_gpu=workers_per_gpu,
            enable_preprocessing=True,
            max_gpu_queue_size=8,
            preprocessing_workers=4,
            postprocessing_workers=2)  # 添加后处理工作进程数
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

