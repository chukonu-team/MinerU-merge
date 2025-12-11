#!/usr/bin/env python3
"""测试pdf_doc修复的脚本"""

import os
import sys
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def test_pdf_processing():
    """测试PDF处理流程"""
    print("=== 测试PDF处理修复 ===")

    # 检查demo目录
    pdf_dir = "/home/ubuntu/MinerU-merge/demo/pdfs"
    if not os.path.exists(pdf_dir):
        print(f"❌ PDF目录不存在: {pdf_dir}")
        return False

    # 检查是否有PDF文件
    import glob
    pdf_files = glob.glob(f"{pdf_dir}/*.pdf")
    if not pdf_files:
        print(f"❌ 没有找到PDF文件在: {pdf_dir}")
        return False

    print(f"✅ 找到 {len(pdf_files)} 个PDF文件:")
    for pdf in pdf_files:
        print(f"  - {os.path.basename(pdf)}")

    # 设置测试环境变量
    os.environ["GPU_MEMORY_UTILIZATION"] = "0.3"  # 降低GPU内存使用
    os.environ["BACKEND"] = "transformers"  # 使用transformers后端更稳定

    try:
        # 导入处理函数
        from main.ocr_pdf_batch import process_pdfs

        output_dir = "/tmp/test_result"

        print(f"✅ 开始处理PDF文件到: {output_dir}")
        results = process_pdfs(
            input_dir=pdf_dir,
            output_dir=output_dir,
            gpu_ids="0",  # 使用单个GPU
            workers_per_gpu=1,
            max_pages=10,  # 进一步限制页数进行测试
            shuffle=False,
            batch_size=384
        )

        print(f"✅ 处理完成，结果: {len(results)} 项")
        success_count = sum(1 for r in results if r.get('success', False))
        print(f"✅ 成功: {success_count}/{len(results)}")

        if success_count > 0:
            print("🎉 测试成功！pdf_doc修复有效")
            return True
        else:
            print("❌ 测试失败，没有成功处理的文件")
            return False

    except Exception as e:
        print(f"❌ 测试失败，错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pdf_processing()
    sys.exit(0 if success else 1)