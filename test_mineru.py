#!/usr/bin/env python3
"""
简单的MinerU测试脚本
"""
import os
import sys
from pathlib import Path

# 添加mineru模块到路径
sys.path.insert(0, '/home/ubuntu/MinerU')

from demo.demo import parse_doc

def main():
    # 设置输入和输出路径
    pdf_path = Path("/home/ubuntu/MinerU/demo/pdfs/demo1.pdf")
    output_dir = Path("/home/ubuntu/MinerU/test_output")

    print(f"输入文件: {pdf_path}")
    print(f"输出目录: {output_dir}")

    # 检查输入文件是否存在
    if not pdf_path.exists():
        print(f"错误: 找不到输入文件 {pdf_path}")
        return

    # 创建输出目录
    output_dir.mkdir(exist_ok=True)

    print("开始处理PDF...")

    try:
        # 使用MinerU处理PDF
        parse_doc(
            path_list=[pdf_path],
            output_dir=output_dir,
            lang="ch",  # 中文
            backend="vlm-vllm-engine",  # 使用vlm后端
            method="auto"  # 自动选择方法
        )

        print("处理完成！")
        print(f"输出文件保存在: {output_dir}")

        # 列出输出文件
        if output_dir.exists():
            print("\n生成的文件:")
            for file in output_dir.rglob("*"):
                if file.is_file():
                    print(f"  {file.relative_to(output_dir)}")

    except Exception as e:
        print(f"处理过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()