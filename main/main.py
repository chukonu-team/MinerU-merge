import os
import sys

from common import get_subdirectories, has_files

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
    use_batch = bool(os.getenv("USE_BATCH", "True"))
    min_size = int(os.getenv("MIN_SIZE",300))

    pdf_dir = "/mnt/data/pdf"
    list_dir = get_subdirectories(pdf_dir)
    output_dir = f"/mnt/data/output"
    index = None

    for bucket_index in list_dir:
        print(f"Processing bucket {bucket_index}")
        pdf_path = os.path.join(pdf_dir, bucket_index)
        if not has_files(pdf_path):
            continue

        pdf_list = os.listdir(pdf_path)
        pdf_count = len(pdf_list)

        print(f"pdf_count================{pdf_count}")
        if pdf_count < min_size:
            continue

        result_dir = os.path.join(output_dir, bucket_index, "result")
        if os.path.exists(result_dir):
            result_list = os.listdir(result_dir)
            result_count = len(result_list)
            print(f"result_count:{result_count}")

            if pdf_count - result_count < min_size:
                continue

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
        if use_batch:
            from ocr_pdf_batch import process_pdfs
        else:
            from ocr_pdf import process_pdfs
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
