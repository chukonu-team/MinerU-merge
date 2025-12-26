import os
from concurrent.futures import ThreadPoolExecutor
import threading
from common import get_subdirectories, has_files
from s3_util import upload_to_s3

# 创建线程锁以确保文件写入的线程安全
file_write_lock = threading.Lock()


def append_record(record_file, filename):
    """线程安全写文件"""
    with file_write_lock:
        with open(record_file, "a", encoding="utf8") as f:
            f.write(filename + "\n")


def upload_one_file(local_path, s3_bucket, s3_key, record_file, filename, uploaded_set):
    """单文件上传任务"""
    if filename in uploaded_set:
        return

    upload_to_s3(local_path, s3_bucket, s3_key)
    append_record(record_file, filename)
    uploaded_set.add(filename)   # 内存内更新无竞争

def process_bucket_directory(bucket_index, output_dir, s3_bucket, result_key, page_key):
    """处理单个bucket目录的上传任务"""
    upload_result_list = set()
    upload_result_file = os.path.join(output_dir, bucket_index, "upload_result.txt")


    if os.path.exists(upload_result_file):
        with open(upload_result_file, "r", encoding="utf8") as f:
            for line in f:
                line = line.strip()
                upload_result_list.add(line)

    # 处理result目录
    result_dir = os.path.join(output_dir, bucket_index, "result")
    if has_files(result_dir):
        list_result = os.listdir(result_dir)

        with ThreadPoolExecutor(max_workers=10) as pool:
            for filename in list_result:
                local_path = os.path.join(result_dir, filename)
                s3_key = os.path.join(result_key, bucket_index, filename)

                pool.submit(
                    upload_one_file,
                    local_path, s3_bucket, s3_key,
                    upload_result_file, filename, upload_result_list
                )

    # 处理page_result目录
    upload_page_list = set()
    upload_page_file = os.path.join(output_dir, bucket_index, "upload_page.txt")


    if os.path.exists(upload_page_file):
        with open(upload_page_file, "r", encoding="utf8") as f:
            for line in f:
                line = line.strip()
                upload_page_list.add(line)

    page_dir = os.path.join(output_dir, bucket_index, "page_result")
    if has_files(page_dir):
        list_page = os.listdir(page_dir)
        with ThreadPoolExecutor(max_workers=10) as pool:
            for filename in list_page:
                local_path = os.path.join(page_dir, filename)
                s3_key = os.path.join(page_key, bucket_index, filename)

                pool.submit(
                    upload_one_file,
                    local_path, s3_bucket, s3_key,
                    upload_page_file, filename, upload_page_list
                )


def upload(s3_bucket, result_key, page_key):
    output_dir = '/mnt/data/output'
    list_dir = get_subdirectories(output_dir)

    # 使用线程池执行器创建多线程
    # 可以通过环境变量设置线程数，默认使用10个线程
    max_workers = int(os.environ.get('UPLOAD_MAX_WORKERS', 50))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 为每个bucket目录提交一个任务到线程池
        futures = [
            executor.submit(
                process_bucket_directory,
                bucket_index,
                output_dir,
                s3_bucket,
                result_key,
                page_key
            )
            for bucket_index in list_dir
        ]

        # 等待所有任务完成（可选，用于异常处理）
        for future in futures:
            try:
                future.result()  # 这会重新抛出任务中的任何异常
            except Exception as e:
                print(f"Error processing bucket directory: {e}")


if __name__ == '__main__':
    s3_bucket = os.environ['S3_BUCKET']
    result_key = os.environ['RESULT_KEY']
    page_key = os.environ['PAGE_KEY']
    upload(s3_bucket, result_key, page_key)