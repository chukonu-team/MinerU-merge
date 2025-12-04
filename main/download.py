import json
import os
import shutil
import sys
import time
from typing import List
import zipfile

# 现在导入原始脚本
from s3_util import download_from_s3

def load_processed_zip_records(record_file):
    """加载已经处理过的zip文件列表"""
    if not os.path.exists(record_file):
        return set()

    with open(record_file, "r") as f:
        return set(line.strip() for line in f.readlines())

def save_processed_zip_record(record_file, zip_name):
    """写入一个已经处理过的zip名称（不需要全局锁，因为每个 bucket 独占目录）"""
    with open(record_file, "a") as f:
        f.write(zip_name + "\n")

def get_keys_from_txt(bucket_name , key_path) -> List[str]:
    """从S3的TXT文件中获取所有PDF对象的key"""
    # 读取TXT文件内容
    keys = []
    with open(key_path, 'r') as f:
        for line in f:
            key = line.strip()
            if not key:
                continue
            if key.startswith('s3a://') or key.startswith('obs://'):
                # 提取路径部分
                key = key.replace('s3a://','').replace('obs://', '')
                # 移除bucket名称部分（如果有）
                if key.startswith(f"{bucket_name}/"):
                    key = key.split(f"{bucket_name}/", 1)[1]

            # 确保键以.pdf结尾
            if key and key.lower().endswith('.pdf') or key.lower().endswith('.zip'):
                keys.append(key)
            else:
                print(f"Skipping non-PDF key: {key}")

    print(f"Found {len(keys)} valid PDF keys in TXT file")
    return keys


import os
from concurrent.futures import ThreadPoolExecutor, as_completed

def extract_pdfs_from_zip(zip_path, output_dir):
    """解压zip并提取其中的所有PDF文件到 output_dir，支持多级目录"""
    temp_extract_dir = zip_path + "_unzipped"

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(temp_extract_dir)

        # 遍历解压目录，找到所有pdf
        for root, _, files in os.walk(temp_extract_dir):
            for f in files:
                if f.lower().endswith(".pdf"):
                    src = os.path.join(root, f)
                    dst = os.path.join(output_dir, f)

                    shutil.move(src, dst)
                    print(f"Extracted PDF: {dst}")

    except Exception as e:
        print(f"Error extracting zip: {zip_path}: {e}")

    finally:
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir)

def process_bucket(
        bucket_index,
        s3_bucket,
        key_path,
):
    """处理一个数据桶"""
    # 获取桶中的所有PDF文件key
    object_keys = get_keys_from_txt(s3_bucket, key_path)
    print(f"Bucket {bucket_index} has {len(object_keys)} files to process")

    # 创建本地临时目录
    pdf_dir = f"/mnt/data/pdf/{bucket_index}"
    if not os.path.exists(pdf_dir):
        os.makedirs(pdf_dir)

    record_file = os.path.join(pdf_dir, "processed_zip.txt")
    processed_zip = load_processed_zip_records(record_file)

    # 准备下载任务
    def download_file(key,pdf_path):
        """单个文件下载任务"""
        # 构建预期的结果文件路径
        filename = os.path.basename(key)
        # 如果 zip 已处理 → 直接跳过
        if filename.lower().endswith(".zip") and filename in processed_zip:
            print(f"Skipping already processed ZIP: {filename}")
            return None
        # 检查结果是否已存在
        local_path = os.path.join(pdf_path, filename)
        if os.path.exists(local_path) and not local_path.lower().endswith(".zip"):
            print(f"Skipping already processed file: {filename}")
            return None
        try:
            download_from_s3(s3_bucket, key, local_path)
            return local_path
        except Exception as e:
            print(f"Download file error: {e}, key: {key}")
            return None

    # 使用多线程下载文件
    downloaded_files = []
    with ThreadPoolExecutor(max_workers=50) as executor:
        # 提交所有下载任务
        future_to_key = {executor.submit(download_file, key,pdf_dir): key for key in object_keys}
        # 收集下载结果
        for future in as_completed(future_to_key):
            result = future.result()
            if result is not None:
                downloaded_files.append(result)

    if not downloaded_files:
        print(f"Batch {bucket_index} skipped - all files already processed")

    final_pdfs = []
    for file_path in downloaded_files:
        filename = os.path.basename(file_path)
        if file_path.lower().endswith(".zip"):
            print(f"Unzipping zip file: {file_path}")
            extract_pdfs_from_zip(file_path, pdf_dir)
            os.remove(file_path)  # 可选，删除 zip 文件
            save_processed_zip_record(record_file, filename)
        elif file_path.lower().endswith(".pdf"):
            final_pdfs.append(file_path)

    if not final_pdfs:
        print(f"Batch {bucket_index} skipped - no PDF files found")
        return

    print(f"Batch {bucket_index} processed {len(final_pdfs)} PDF files")

if __name__ == "__main__":
    # 从环境变量获取作业索引
    s3_bucket = os.getenv("S3_BUCKET")
    node_name = os.getenv("NODE_NAME")
    print("node_name", node_name)

    json_map_path = os.getenv("JSON_MAP_PATH")
    with open(json_map_path, 'r') as f:
        json_map = json.load(f)

    bucket_list = []
    for key in json_map:
        if json_map[key] == node_name:
            bucket_list.append(key)

    print(f"Found {len(bucket_list)} buckets")
    for bucket_index in bucket_list:
        bucket_txt_key = f"{os.getenv('BUCKET_TXT_KEY_PATH')}/{bucket_index}.txt"
        try:
            process_bucket(
                bucket_index=bucket_index,
                s3_bucket=s3_bucket,
                key_path=bucket_txt_key
            )

        except Exception as e:
            print(f"Error processing bucket {bucket_index}: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)
