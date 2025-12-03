import os
import glob
from mineru.cli.common import read_fn, convert_pdf_bytes_to_bytes_by_pypdfium2
import logging
import fitz  # PyMuPDF
from mineru.backend.vlm.vlm_analyze import load_images_from_pdf
from mineru.utils.enum_class import ImageType
from mineru.utils.pdf_reader import base64_to_pil_image
from concurrent.futures import ProcessPoolExecutor, as_completed
import pypdfium2 as pdfium
from mineru.utils.pdf_image_tools import pdf_page_to_image
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

def process_pdf_page_range(pdf_bytes, start_page, end_page, dpi=200):
    """处理指定范围的PDF页面"""
    try:
        pdf_doc = pdfium.PdfDocument(pdf_bytes)
        images_list = []

        for page_idx in range(start_page, end_page + 1):
            page = pdf_doc[page_idx]
            image_dict = pdf_page_to_image(page, dpi=dpi, image_type=ImageType.BYTES)
            images_list.append((page_idx, image_dict))

        pdf_doc.close()
        return images_list
    except Exception as e:
        logging.error(f"Error processing pages {start_page}-{end_page}: {e}")
        return []

def load_images_from_pdf_parallel(pdf_bytes, dpi=200, num_workers=4):
    """使用进程池并行处理PDF页面转换"""
    try:
        pdf_doc = pdfium.PdfDocument(pdf_bytes)
        total_pages = len(pdf_doc)
        pdf_doc.close()

        if total_pages == 0:
            return []

        # 计算每个进程处理的页面数
        pages_per_worker = max(1, total_pages // num_workers)

        # 创建页面范围列表
        page_ranges = []
        for i in range(num_workers):
            start_page = i * pages_per_worker
            if i == num_workers - 1:
                # 最后一个进程处理剩余所有页面
                end_page = total_pages - 1
            else:
                end_page = start_page + pages_per_worker - 1

            if start_page < total_pages:
                page_ranges.append((start_page, end_page))

        # 使用进程池处理
        all_images = []
        with ProcessPoolExecutor(max_workers=len(page_ranges)) as executor:
            # 提交所有任务
            futures = []
            for start_page, end_page in page_ranges:
                future = executor.submit(process_pdf_page_range, pdf_bytes, start_page, end_page, dpi)
                futures.append(future)

            # 收集结果
            for future in futures:
                try:
                    page_images = future.result()
                    all_images.extend(page_images)
                except Exception as e:
                    logging.error(f"Error in parallel processing: {e}")

        # 按页码排序并提取图片数据
        all_images.sort(key=lambda x: x[0])
        return [img_dict for _, img_dict in all_images]

    except Exception as e:
        logging.error(f"Error in parallel PDF processing: {e}")
        # 回退到单线程处理
        return load_images_from_pdf(pdf_bytes, image_type=ImageType.BYTES)
def preprocess_worker(pdf_path):
    try:
        pdf_bytes = read_fn(pdf_path)
        pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)
        pdf_name = os.path.basename(pdf_path)
        page_count = get_pdf_page_count(pdf_path)

        # 使用并行处理替代原来的单线程处理
        images_byte_list = load_images_from_pdf_parallel(pdf_bytes, dpi=200, num_workers=4)

        return {
            "success":True,
            "pdf_path":pdf_path,
            "pdf_bytes":pdf_bytes,
            "pdf_name":pdf_name,
            "page_count":page_count,
            "images_byte_list":images_byte_list
        }
    except Exception as e:
        return {
            "success":False,
            "pdf_path":pdf_path,
            "error_msg":str(e)  # 转换为字符串以确保能被序列化
        }




def process_pdf_files(pdf_dir, num_workers=4):
    """
    遍历指定路径下的所有PDF文件，使用进程池并行处理

    Args:
        pdf_dir (str): PDF文件所在目录路径
        num_workers (int): 进程池大小，默认4个进程

    Returns:
        list: 处理结果列表
    """
    if not os.path.exists(pdf_dir):
        print(f"错误: 目录 {pdf_dir} 不存在")
        return []

    # 使用glob查找PDF文件
    pdf_pattern = os.path.join(pdf_dir, "*.pdf")
    pdf_files = glob.glob(pdf_pattern)

    print(f"在 {pdf_dir} 中找到 {len(pdf_files)} 个PDF文件:")

    if not pdf_files:
        return []

    # 使用进程池并行处理PDF文件
    results = []
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # 提交所有任务
        future_to_pdf = {executor.submit(preprocess_worker, pdf_file): pdf_file
                        for pdf_file in pdf_files}

        # 收集结果
        for future in as_completed(future_to_pdf):
            pdf_file = future_to_pdf[future]
            try:
                result = future.result()
                results.append(result)
                if result["success"]:
                    print(f"✓ 成功处理: {os.path.basename(pdf_file)} "
                          f"(页数: {result['page_count']}, 图片数: {len(result['images_byte_list'])})")
                else:
                    print(f"✗ 处理失败: {os.path.basename(pdf_file)} - {result['error_msg']}")
            except Exception as e:
                print(f"✗ 处理异常: {os.path.basename(pdf_file)} - {str(e)}")
                results.append({
                    "success": False,
                    "error_msg": str(e),
                    "pdf_name": os.path.basename(pdf_file)
                })

    return results

if __name__ == "__main__":
    # 输入目录
    pdf_dir = "/home/ubuntu/MinerU-merge/demo/pdfs"

    # 检查目录是否存在
    if not os.path.exists(pdf_dir):
        print(f"错误: 目录 {pdf_dir} 不存在")
        exit(1)

    # 处理PDF文件
    results = process_pdf_files(pdf_dir, num_workers=4)

    # 统计处理结果
    successful_count = sum(1 for r in results if r["success"])
    failed_count = len(results) - successful_count

    if results:
        print(f"\n处理完成: 成功 {successful_count} 个, 失败 {failed_count} 个")

        if failed_count > 0:
            print("\n失败文件列表:")
            for result in results:
                if not result["success"]:
                    print(f"  - {result.get('pdf_name', '未知文件')}: {result.get('error_msg', '未知错误')}")
    else:
        print(f"在目录 {pdf_dir} 中未找到PDF文件")