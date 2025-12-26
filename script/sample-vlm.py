import argparse
import json
import os
import random
import zipfile
import boto3
import tempfile
import shutil
from typing import List, Tuple
from pathlib import Path

# 导入您提供的函数
from mineru.cli.common import _process_output
from mineru.utils.enum_class import MakeMode
from mineru.data.data_reader_writer import FileBasedDataWriter


def read_zip_ocr_res_from_s3(s3_client, bucket: str, key: str, output_dir: str) -> dict:
    """
    从S3读取ZIP文件并解析OCR结果，直接保存到输出目录
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 下载ZIP文件到输出目录
    zip_filename = os.path.basename(key)
    zip_path = os.path.join(output_dir, zip_filename)

    try:
        s3_client.download_file(bucket, key, zip_path)
        print(f"Downloaded ZIP file to: {zip_path}")

        # 读取ZIP文件内容
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # 查找包含JSON数据的文件
            json_files = [name for name in zip_ref.namelist() if name.endswith('.json') or name == 'data']

            if not json_files:
                print(f"No JSON files found in S3 ZIP file: {key}")
                return None

            # 使用第一个找到的JSON文件
            json_file_name = json_files[0]

            # 解压JSON文件到输出目录
            zip_ref.extract(json_file_name, output_dir)
            json_path = os.path.join(output_dir, json_file_name)
            print(f"Extracted JSON file to: {json_path}")

            # 读取JSON内容
            with open(json_path, 'r', encoding='utf-8') as file:
                infra_result = json.load(file)
                return infra_result
    except Exception as e:
        print(f"Error reading ZIP from S3: {e}")
        return None

    return None


def generate_markdown_from_local_json(
        json_path: str,
        pdf_path: str,
        make_md_mode: str = MakeMode.MM_MD,
        local_md_dir=None
) -> str:
    """
    从本地JSON文件生成Markdown
    """
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    # 读取JSON内容
    with open(json_path, "r", encoding="utf-8") as f:
        infer_result = json.load(f)

    if not isinstance(infer_result, dict):
        raise ValueError("Input JSON format invalid: expected a dict at top-level")

    middle_json = infer_result.get("middle_json")

    if middle_json is None:
        raise ValueError("JSON missing required keys: middle_json")

    # 使用PDF文件名
    pdf_file_name = os.path.basename(pdf_path)

    if local_md_dir is None:
        local_md_dir = os.path.dirname(json_path)

    md_writer = FileBasedDataWriter(local_md_dir)
    local_image_dir = os.path.join(local_md_dir, "images")

    pdf_info = middle_json.get("pdf_info")
    if pdf_info is None:
        raise ValueError("middle_json missing 'pdf_info'")

    _process_output(
        pdf_info=pdf_info,
        pdf_bytes=b"",
        pdf_file_name=pdf_file_name,
        local_md_dir=local_md_dir,
        local_image_dir=local_image_dir,
        md_writer=md_writer,
        f_draw_layout_bbox=False,
        f_draw_span_bbox=False,
        f_dump_orig_pdf=False,
        f_dump_md=True,
        f_dump_content_list=False,
        f_dump_middle_json=False,
        f_dump_model_output=False,
        f_make_md_mode=make_md_mode,
        middle_json=middle_json,
        is_pipeline=False,
    )

    # 查找生成的Markdown文件
    md_files = [f for f in os.listdir(local_md_dir) if f.endswith('.md')]
    if md_files:
        return os.path.join(local_md_dir, md_files[0])
    else:
        raise FileNotFoundError("Markdown file was not generated")


def download_pdf_from_s3(s3_client, s3_path: str, local_path: str) -> bool:
    """
    使用boto3从S3下载文件
    """
    try:
        bucket, key = parse_s3_path(s3_path)
        s3_client.download_file(bucket, key, local_path)
        return True
    except Exception as e:
        print(f"Error downloading {s3_path}: {e}")
        return False


def parse_s3_path(s3_path: str) -> Tuple[str, str]:
    """
    解析S3路径，返回bucket和key
    """
    # 处理不同的S3路径格式
    if s3_path.startswith('s3://'):
        path_without_protocol = s3_path[5:]
    elif s3_path.startswith('s3a://'):
        path_without_protocol = s3_path[6:]
    elif s3_path.startswith('obs://'):
        # 华为OBS格式，转换为S3格式
        path_without_protocol = s3_path[6:]
    else:
        raise ValueError(f"Unsupported S3 path format: {s3_path}")

    parts = path_without_protocol.split('/', 1)
    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ""

    return bucket, key


def extract_json_from_zip(zip_path: str, extract_dir: str) -> str:
    """
    从ZIP文件中提取JSON文件
    """
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # 获取ZIP文件中的所有文件
        file_list = zip_ref.namelist()
        print(f"Files in ZIP {zip_path}: {file_list}")

        # 查找JSON文件
        json_files = [f for f in file_list if f.endswith('.json') or f == 'data']

        if not json_files:
            raise ValueError(f"No JSON files found in {zip_path}")

        # 解压JSON文件
        json_file_name = json_files[0]
        zip_ref.extract(json_file_name, extract_dir)

        # 返回JSON文件的路径
        return os.path.join(extract_dir, json_file_name)


def process_json_zip_from_s3(s3_client, json_zip_s3_path: str, pdf_s3_prefix: str, output_dir: str) -> bool:
    """
    从S3处理单个json.zip文件：下载对应的PDF，生成Markdown
    """
    try:
        # 获取文件名（不含扩展名）
        json_bucket, json_key = parse_s3_path(json_zip_s3_path)

        base_name = os.path.basename(json_key).replace('.json.zip', '')
        print(f"Processing file: {base_name}")

        # 为当前文件创建单独的输出目录
        file_output_dir = os.path.join(output_dir, base_name)
        os.makedirs(file_output_dir, exist_ok=True)
        print(f"Created output directory: {file_output_dir}")

        # 构建PDF的S3路径
        pdf_s3_path = f"{pdf_s3_prefix.rstrip('/')}/{base_name}.pdf"
        print(f"Constructed PDF S3 path: {pdf_s3_path}")

        # 下载PDF文件到输出目录
        pdf_path = os.path.join(file_output_dir, f"{base_name}.pdf")
        print(f"Downloading PDF from: {pdf_s3_path}")
        if not download_pdf_from_s3(s3_client, pdf_s3_path, pdf_path):
            print(f"Failed to download PDF from {pdf_s3_path}")
            return False
        print(f"PDF downloaded successfully to: {pdf_path}")

        # 下载ZIP文件到输出目录
        zip_path = os.path.join(file_output_dir, f"{base_name}.json.zip")
        print(f"Downloading ZIP from: {json_zip_s3_path}")
        s3_client.download_file(json_bucket, json_key, zip_path)
        print(f"ZIP downloaded successfully to: {zip_path}")

        # 验证ZIP文件是否下载成功
        if not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0:
            print(f"ZIP file is empty or does not exist: {zip_path}")
            return False

        # 解压JSON文件
        print(f"Extracting JSON from ZIP: {zip_path}")
        json_path = extract_json_from_zip(zip_path, file_output_dir)
        print(f"JSON extracted to: {json_path}")

        # 验证JSON文件是否解压成功
        if not os.path.exists(json_path) or os.path.getsize(json_path) == 0:
            print(f"JSON file is empty or does not exist: {json_path}")
            return False

        # 读取并更新JSON文件中的pdf_path
        print(f"Reading JSON file: {json_path}")
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)

        json_data['pdf_path'] = pdf_path

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print("Updated JSON with PDF path")

        # 生成Markdown
        print("Generating Markdown...")
        md_path = generate_markdown_from_local_json(
            json_path,
            pdf_path,
            local_md_dir=file_output_dir
        )
        print(f"Markdown generated at: {md_path}")

        # 清理临时ZIP文件（可选）
        # os.remove(zip_path)
        # print("Removed temporary ZIP file")

        return True

    except Exception as e:
        print(f"Error processing {json_zip_s3_path}: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_s3_client(aws_access_key_id: str = None,
                  aws_secret_access_key: str = None,
                  endpoint_url: str = None):
    """
    创建S3客户端
    """
    s3_config = {}
    if aws_access_key_id and aws_secret_access_key:
        s3_config['aws_access_key_id'] = aws_access_key_id
        s3_config['aws_secret_access_key'] = aws_secret_access_key

    if endpoint_url:
        s3_config['endpoint_url'] = endpoint_url

    return boto3.client('s3', **s3_config)


def find_json_zip_files_in_s3(s3_client, bucket: str, prefixes: List[str]) -> List[str]:
    """
    在S3桶中的多个前缀下查找所有json.zip文件
    """
    json_zip_files = []

    for prefix in prefixes:
        try:
            print(f"Searching in prefix: {prefix}")
            paginator = s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix)

            for page in page_iterator:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        if key.endswith('.json.zip'):
                            s3_path = f"s3://{bucket}/{key}"
                            json_zip_files.append(s3_path)
                            print(f"Found JSON zip file: {s3_path}")

        except Exception as e:
            print(f"Error listing S3 objects in prefix {prefix}: {e}")

    print(f"Total JSON zip files found: {len(json_zip_files)}")
    return json_zip_files


def generate_chunk_prefixes(base_prefix: str, chunk_range: str) -> List[str]:
    """
    根据基础前缀和chunk范围生成完整的前缀列表
    """
    prefixes = []

    # 解析范围
    start, end = map(int, chunk_range.split('-'))

    # 生成每个chunk的前缀
    for i in range(start, end + 1):
        chunk_name = f"{i:06d}"
        full_prefix = f"{base_prefix.rstrip('/')}/{chunk_name}"
        prefixes.append(full_prefix)
        print(f"Added prefix: {full_prefix}")

    return prefixes


def sample_s3_files(files: List[str], sample_count: int) -> List[str]:
    """
    从S3文件列表中抽样
    """
    if not files:
        return []

    if len(files) <= sample_count:
        return files

    return random.sample(files, sample_count)


def create_zip_packages(output_dir: str, package_count: int) -> List[str]:
    """
    将输出目录中的所有PDF和Markdown文件分成多个包并创建zip文件
    确保相同名称的PDF和Markdown文件分配到同一个包中
    压缩完成后删除子目录
    """
    # 按文件基名分组收集文件
    file_groups = {}
    subdirs_to_remove = []

    for item in os.listdir(output_dir):
        item_path = os.path.join(output_dir, item)
        if os.path.isdir(item_path) and not item.startswith('.'):
            # 获取目录中的所有PDF和Markdown文件
            pdf_files = [f for f in os.listdir(item_path) if f.endswith('.pdf')]
            md_files = [f for f in os.listdir(item_path) if f.endswith('.md')]

            if pdf_files and md_files:
                # 假设每个目录只有一个PDF和一个对应的Markdown文件
                pdf_file = pdf_files[0]
                md_file = md_files[0]

                # 提取基名（不含扩展名）
                pdf_base = os.path.splitext(pdf_file)[0]  # 这会去掉 .pdf

                # 对于Markdown文件，需要特殊处理，因为它可能包含 .pdf 在基名中
                # 例如: "dd94d0bf28218de91a88dfbad78e779a.pdf.md" -> 基名应该是 "dd94d0bf28218de91a88dfbad78e779a"
                md_base_without_md = os.path.splitext(md_file)[0]  # 去掉 .md
                # 如果去掉.md后还有.pdf，再去掉.pdf
                if md_base_without_md.endswith('.pdf'):
                    md_base = md_base_without_md[:-4]  # 去掉末尾的 .pdf
                else:
                    md_base = md_base_without_md

                # 检查基名是否匹配
                if pdf_base == md_base:
                    pdf_path = os.path.join(item_path, pdf_file)
                    md_path = os.path.join(item_path, md_file)

                    # 按基名分组
                    file_groups[pdf_base] = {
                        'pdf': (pdf_path, pdf_file),
                        'md': (md_path, md_file)
                    }

                    # 记录需要删除的子目录
                    subdirs_to_remove.append(item_path)
                    print(f"Matched files: {pdf_base}.pdf and {md_file}")
                else:
                    print(
                        f"Warning: Base names don't match in {item_path}: '{pdf_base}' vs '{md_base}' (from {md_file})")
            else:
                print(f"Warning: Missing PDF or MD files in {item_path}")

    if not file_groups:
        print("No matching PDF and Markdown file pairs found to package")
        return []

    print(f"Found {len(file_groups)} PDF-Markdown file pairs")

    # 将分组转换为列表并随机打乱
    file_pairs = list(file_groups.items())
    random.shuffle(file_pairs)

    # 计算每个包应该包含的文件对数
    pairs_per_package = len(file_pairs) // package_count
    remainder = len(file_pairs) % package_count

    packages = []
    start_index = 0

    for i in range(package_count):
        # 计算当前包的文件对数
        end_index = start_index + pairs_per_package
        if i < remainder:
            end_index += 1

        # 创建zip文件
        zip_path = os.path.join(output_dir, f"package_{i + 1:02d}.zip")
        print(f"Creating package {i + 1}: {zip_path} with {end_index - start_index} file pairs")

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for base_name, files in file_pairs[start_index:end_index]:
                # 添加PDF文件
                pdf_path, pdf_filename = files['pdf']
                zipf.write(pdf_path, pdf_filename)

                # 添加对应的Markdown文件
                md_path, md_filename = files['md']
                zipf.write(md_path, md_filename)

                print(f"  Added {base_name}.pdf and {md_filename} to package")

        packages.append(zip_path)
        start_index = end_index

    # 删除所有子目录
    for subdir in subdirs_to_remove:
        try:
            shutil.rmtree(subdir)
            print(f"Removed directory: {subdir}")
        except Exception as e:
            print(f"Error removing directory {subdir}: {e}")

    print(f"Created {len(packages)} packages and removed {len(subdirs_to_remove)} directories")
    return packages


def main():
    parser = argparse.ArgumentParser(description="Process JSON.zip files from S3 and create packages")
    parser.add_argument("--s3_bucket", required=True, help="S3桶名称")
    parser.add_argument("--s3_prefix", required=True, help="JSON文件的基础S3前缀路径")
    parser.add_argument("--chunk_range", required=True, help="chunk范围，例如: 0000-0010")
    parser.add_argument("--pdf_s3_prefix", required=True, help="PDF文件的S3前缀路径")
    parser.add_argument("--output_dir", required=True, help="输出目录")
    parser.add_argument("--sample_count", type=int, default=1000, help="抽样数量")
    parser.add_argument("--package_count", type=int, default=5, help="分包数量")
    parser.add_argument("--aws_access_key_id", help="AWS访问密钥ID")
    parser.add_argument("--aws_secret_access_key", help="AWS秘密访问密钥")
    parser.add_argument("--endpoint_url", help="S3端点URL（如果不是AWS S3）")

    args = parser.parse_args()

    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)
    print(f"Output directory: {args.output_dir}")

    # 创建S3客户端
    s3_client = get_s3_client(
        args.aws_access_key_id,
        args.aws_secret_access_key,
        args.endpoint_url
    )

    # 生成chunk前缀列表
    prefixes = generate_chunk_prefixes(args.s3_prefix, args.chunk_range)
    print(f"Generated {len(prefixes)} prefixes for search")

    # 查找S3中的所有json.zip文件
    print(f"Searching for JSON zip files in S3 bucket: {args.s3_bucket}")
    all_s3_files = find_json_zip_files_in_s3(s3_client, args.s3_bucket, prefixes)

    if not all_s3_files:
        print("No JSON.zip files found in S3")
        return

    # 抽样文件
    sampled_files = sample_s3_files(all_s3_files, min(args.sample_count, len(all_s3_files)))
    print(f"Sampled {len(sampled_files)} files from S3")

    # 处理每个文件
    processed_count = 0
    for i, s3_file_path in enumerate(sampled_files):
        print(f"Processing file {i + 1}/{len(sampled_files)}: {s3_file_path}")

        if process_json_zip_from_s3(s3_client, s3_file_path, args.pdf_s3_prefix, args.output_dir):
            processed_count += 1
            print(f"Successfully processed file")
        else:
            print(f"Failed to process file")

    print(f"Successfully processed {processed_count} files")

    # 创建zip包并删除子目录
    packages = create_zip_packages(args.output_dir, args.package_count)
    print(f"Created {len(packages)} packages: {packages}")


if __name__ == "__main__":
    main()