import os
import glob
from mineru.cli.common import read_fn, convert_pdf_bytes_to_bytes_by_pypdfium2
import logging
import fitz  # PyMuPDF
from mineru.backend.vlm.vlm_analyze import load_images_from_pdf
from mineru.utils.enum_class import ImageType
from mineru.utils.pdf_reader import base64_to_pil_image
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PID:%(process)d][%(thread)d] %(levelname)s: %(message)s"
)

def get_pdf_page_count(pdf_path):
    """使用fitz获取PDF页数"""
    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        doc.close()
        return page_count
    except Exception as e:
        logging.error(f"Error getting page count for {pdf_path}: {e}")
        return 0
def preprocess_worker(pdf_path):
    try:
        pdf_bytes = read_fn(pdf_path)
        pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)
        pdf_name = os.path.basename(pdf_path)
        page_count = get_pdf_page_count(pdf_path)
        # 移除threads参数以避免在守护进程中创建子线程
        images_byte_list, _ = load_images_from_pdf(pdf_bytes, image_type=ImageType.BYTES)
        return {
            "success":True,
            "pdf_bytes":pdf_bytes,
            "pdf_name":pdf_name,
            "page_count":page_count,
            "images_byte_list":images_byte_list
        }
    except Exception as e:
        return {
            "success":False,
            "error_msg":str(e)  # 转换为字符串以确保能被序列化
        }




def process_pdf_files(pdf_dir):
    """
    遍历指定路径下的所有PDF文件

    Args:
        pdf_dir (str): PDF文件所在目录路径

    Returns:
        list: PDF文件路径列表
    """
    if not os.path.exists(pdf_dir):
        print(f"错误: 目录 {pdf_dir} 不存在")
        return []

    # 使用glob查找PDF文件
    pdf_pattern = os.path.join(pdf_dir, "*.pdf")
    pdf_files = glob.glob(pdf_pattern)

    print(f"在 {pdf_dir} 中找到 {len(pdf_files)} 个PDF文件:")
    for i, pdf_file in enumerate(pdf_files, 1):
        result=preprocess_worker(pdf_file)

    return pdf_files

if __name__ == "__main__":
    # 输入目录
    pdf_dir = "/home/ubuntu/MinerU-merge/demo/pdfs"

    # 检查目录是否存在
    if not os.path.exists(pdf_dir):
        print(f"错误: 目录 {pdf_dir} 不存在")
        exit(1)

    # 处理PDF文件
    pdf_files = process_pdf_files(pdf_dir)

    if pdf_files:
        print(f"\n成功处理了 {len(pdf_files)} 个PDF文件")
    else:
        print(f"在目录 {pdf_dir} 中未找到PDF文件")