import json
import os
import shutil
import sys
import time
from typing import List
from common import get_subdirectories, has_files

# 现在导入原始脚本
from ocr_pdf import process_pdfs  # 修正导入的函数名


def process():
    # 从环境变量获取作业索引
    gpu_ids = os.getenv("GPU_IDS")
    vram_size_gb = os.getenv("VRAM_SIZE_GB")
    workers_per_gpu = os.getenv("WORKERS_PER_GPU")
    max_pages = os.getenv("MAX_PAGES")
    shuffle_env = os.getenv("SHUFFLE")
    shuffle = True if shuffle_env == "true" else False
    batch_size = os.getenv("BATCH_SIZE")
    proportion = os.getenv("PROPORTION", 0)

    pdf_dir = "/mnt/data/pdf"
    list_dir = get_subdirectories(pdf_dir)
    output_dir = f"/mnt/data/output"
    index = None

    for bucket_index in list_dir:
        print(f"Processing bucket {bucket_index}")
        pdf_path = os.path.join(pdf_dir, bucket_index)
        if not has_files(pdf_path):
            continue

        result_dir = os.path.join(output_dir, bucket_index, "result")
        if os.path.exists(result_dir):
            result_list = os.listdir(result_dir)
            pdf_list = os.listdir(pdf_path)
            cur_proportion = (len(pdf_list) - len(result_list)) / len(pdf_list)
            print("cur_proportion", cur_proportion)
            if cur_proportion < float(proportion):
                print(f"Skipping {bucket_index} because proportion is less than {proportion}")
                continue

        index = bucket_index
        break

    input_path = f"/mnt/data/pdf/{index}"
    output_path = f"/mnt/data/output/{index}"
    try:
        # 运行处理任务
        process_pdfs(
            input_dir=input_path,
            output_dir=output_path,
            vram_size_gb=int(vram_size_gb),
            gpu_ids=gpu_ids,
            workers_per_gpu=int(workers_per_gpu),
            max_pages=int(max_pages),
            shuffle=shuffle,
            batch_size=int(batch_size)
        )

        sys.exit(0)

    except Exception as e:
        print(f"Error processing bucket {index}: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    process()
