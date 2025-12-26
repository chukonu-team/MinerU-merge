import argparse
import json
import os
import random
import subprocess
import zipfile
import shutil
from typing import List, Tuple

# 导入您提供的函数
from mineru.cli.common import _process_output
from mineru.utils.enum_class import MakeMode
from mineru.data.data_reader_writer import FileBasedDataWriter


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

def get_bucket_list(chunk_range):
    """
    根据基础前缀和chunk范围生成完整的前缀列表
    """
    list = []
    # 解析范围
    start, end = map(int, chunk_range.split('-'))

    # 生成每个chunk的前缀
    for i in range(start, end + 1):
        bucket_name = f"{i:06d}"
        list.append(bucket_name)
    return list

def get_file(bucket_map_path , bucket_range , input_dir, output_dir):
    bucket_list = get_bucket_list(bucket_range)
    with open(bucket_map_path, 'r') as f:
        bucket_map = json.load(f)
        for bucket in bucket_list:
            server = bucket_map[bucket]
            result_cmd = f"ssh {server} -o 'StrictHostKeyChecking no' 'find {input_dir}/output/{bucket}/result -maxdepth 1 -type f | head -1'"
            print(result_cmd)
            result = subprocess.run(result_cmd, shell=True, capture_output=True)
            print(result)
            result_name = os.path.basename(result.stdout.decode().strip())
            get_result_cmd = f"scp {server}:{input_dir}/output/{bucket}/result/{result_name} {output_dir}"
            print(get_result_cmd)
            get_result = subprocess.run(get_result_cmd, shell=True, capture_output=True)
            print(get_result)

            pdf_name = result_name.replace(".json.zip", ".pdf")
            pdf_cmd = f"scp {server}:{input_dir}/pdf/{bucket}/{pdf_name} {output_dir}"
            pdf_result = subprocess.run(pdf_cmd, shell=True, capture_output=True)
            print(pdf_result)

def parse_markdown(input_dir):
    list = os.listdir(input_dir)
    for file in list:
        if file.endswith(".json.zip"):
            with zipfile.ZipFile(os.path.join(input_dir, file), 'r') as zip:
                zip.extractall(input_dir)

            base_name = file.replace(".json.zip", "")
            json_path = os.path.join(input_dir, f"{base_name}.json")
            pdf_path = os.path.join(input_dir, f"{base_name}.pdf")
            generate_markdown_from_local_json(json_path,pdf_path)

def main():
    parser = argparse.ArgumentParser(description="Process JSON.zip files from S3 and create packages")

    parser.add_argument("--bucket_map_path", required=True)
    parser.add_argument("--bucket_range", required=True, help="chunk范围，例如: 0000-0010")
    parser.add_argument("--input_dir", required=True, help="输入目录")
    parser.add_argument("--output_dir", required=True, help="输出目录")

    args = parser.parse_args()
    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)
    print(f"Output directory: {args.output_dir}")
    get_file(args.bucket_map_path , args.bucket_range, args.input_dir, args.output_dir)
    parse_markdown(args.output_dir)


if __name__ == "__main__":
    main()