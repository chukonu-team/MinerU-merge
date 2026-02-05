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



def parse_markdown(input_dir,pdf_dir):
    list = os.listdir(input_dir)
    for file in list:
        if file.endswith(".json.zip"):
            with zipfile.ZipFile(os.path.join(input_dir, file), 'r') as zip:
                zip.extractall(input_dir)

            base_name = file.replace(".json.zip", "")
            json_path = os.path.join(input_dir, f"{base_name}.json")
            pdf_path = os.path.join(pdf_dir, f"{base_name}.pdf")
            generate_markdown_from_local_json(json_path,pdf_path)

def main():
    parser = argparse.ArgumentParser(description="Process JSON.zip files from S3 and create packages")
    parser.add_argument("--input_dir", required=True, help="输入目录")
    parser.add_argument("--pdf_dir", required=True, help="输出目录")
    args = parser.parse_args()
    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)
    parse_markdown(args.input_dir, args.pdf_dir)


if __name__ == "__main__":
    main()