#!/usr/bin/env python3
"""修复的MinerU进程池 - 简化版本"""

import os
import time


import traceback
import logging

from mineru.cli.common import read_fn, convert_pdf_bytes_to_bytes_by_pypdfium2



def preprocessing_worker(batch, save_dir, **kwargs):
    """
    增强版预处理函数 - 读取PDF文件、转换为字节格式、加载图像
    这部分工作包含load_images_from_pdf，不依赖GPU，可以在CPU上并行处理
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



    # 加载图像（这部分原在batch_doc_analyze中）
    image_loading_start = time.time()
    from mineru.backend.vlm.vlm_analyze import load_images_from_pdf
    from mineru.utils.enum_class import ImageType

    all_images_list = []
    images_count_per_pdf = []
    pdf_processing_status = []

    # 遍历所有PDF文档，加载图像（使用BASE64格式以支持序列化）
    for pdf_bytes in pdf_bytes_list:
        try:
            images_list, pdf_doc = load_images_from_pdf(pdf_bytes, image_type=ImageType.BASE64)
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


    # 生成有效的PIL图像列表（从base64转换回PIL格式用于GPU处理）
    images_pil_list = []
    for image_dict in all_images_list:
        if image_dict and isinstance(image_dict, dict) and "img_base64" in image_dict:
            # 将base64字符串转换回PIL图像
            try:
                from mineru.utils.pdf_reader import base64_to_pil_image
                pil_img = base64_to_pil_image(image_dict["img_base64"])
                # 将PIL图像存储回字典中以保持兼容性
                image_dict["img_pil"] = pil_img
                images_pil_list.append(pil_img)
            except Exception as e:
                logging.warning(f"转换base64图像到PIL失败: {e}")

    total_preprocess_time = time.time() - start
    logging.info(f"增强预处理完成，总耗时{total_preprocess_time:.2f}秒，有效图像数: {len(images_pil_list)}")

    # 返回预处理后的数据（直接使用pdf_bytes，不包含all_pdf_docs避免序列化问题）
    return {
        'pdf_bytes_list': pdf_bytes_list,
        'image_writers': image_writers,
        'pdf_paths': pdf_paths,
        'save_dir': save_dir,
        'total_preprocess_time': total_preprocess_time,
        'all_images_list': all_images_list,  # 包含base64图像数据，可以序列化
        'images_count_per_pdf': images_count_per_pdf,
        'pdf_processing_status': pdf_processing_status,
        'images_pil_list': [],  # 清空PIL图像列表，避免序列化问题
        'batch_info': batch
    }
