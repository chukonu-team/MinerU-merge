import os
import glob
import time
import json
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

# 导入MinerU相关模块
try:
    from mineru.cli.common import read_fn, convert_pdf_bytes_to_bytes_by_pypdfium2
    from mineru.data.data_reader_writer import FileBasedDataWriter
except ImportError:
    print("警告: MinerU模块不可用，使用模拟功能")
    def read_fn(path):
        with open(path, 'rb') as f:
            return f.read()
    def convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, start_page, end_page):
        return pdf_bytes
    class FileBasedDataWriter:
        def __init__(self, path):
            self.path = path
            os.makedirs(path, exist_ok=True)


class PDFServer:
    """PDF处理服务器核心类"""

    def __init__(self, num_workers: int = 4, max_queue_size: int = 1000):
        """
        初始化PDF处理服务器

        Args:
            num_workers: 工作线程数量
            max_queue_size: 队列最大大小
        """
        self.preProcessQueue = queue.Queue(maxsize=max_queue_size)
        self.preProcessPool = ThreadPoolExecutor(max_workers=num_workers)
        self.results: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        self.num_workers = num_workers
        self.max_queue_size = max_queue_size
        print(f"PDF服务器初始化完成，工作线程数: {num_workers}, 队列大小: {max_queue_size}")

    def add_pdf_files_from_directory(self, pdf_dir: str) -> int:
        """
        从指定目录添加PDF文件到队列

        Args:
            pdf_dir: PDF文件所在目录

        Returns:
            int: 添加的PDF文件数量
        """
        if not os.path.exists(pdf_dir):
            print(f"目录不存在: {pdf_dir}")
            return 0

        # 获取目录下所有PDF文件
        pdf_pattern = os.path.join(pdf_dir, "*.pdf")
        pdf_files = glob.glob(pdf_pattern)
        pdf_pattern_recursive = os.path.join(pdf_dir, "**/*.pdf")
        pdf_files.extend(glob.glob(pdf_pattern_recursive, recursive=True))
        pdf_files = sorted(list(set(pdf_files)))

        # 将PDF文件路径添加到队列中
        added_count = 0
        for pdf_file in pdf_files:
            try:
                self.preProcessQueue.put(pdf_file, block=False)
                added_count += 1
                print(f"已添加到队列: {pdf_file}")
            except queue.Full:
                print("队列已满")
                break

        print(f"总共添加了 {added_count} 个PDF文件")
        return added_count

    def add_pdf_file(self, pdf_path: str) -> bool:
        """
        添加单个PDF文件到队列

        Args:
            pdf_path: PDF文件路径

        Returns:
            bool: 是否成功添加
        """
        if not os.path.exists(pdf_path):
            print(f"文件不存在: {pdf_path}")
            return False

        if not pdf_path.lower().endswith('.pdf'):
            print(f"不是PDF文件: {pdf_path}")
            return False

        try:
            self.preProcessQueue.put(pdf_path, block=False)
            print(f"已添加到队列: {pdf_path}")
            return True
        except queue.Full:
            print("队列已满")
            return False

    def worker(self, pdf_path: str) -> Dict[str, Any]:
        """
        Worker函数 - 处理单个PDF文件，实现你提供的核心逻辑

        Args:
            pdf_path: PDF文件路径

        Returns:
            Dict: 处理结果
        """
        try:
            print(f"开始处理: {pdf_path}")
            start_time = time.time()

            # 1. 读取PDF文件
            pdf_bytes = read_fn(pdf_path)
            print(f"读取PDF文件完成: {len(pdf_bytes)} 字节")

            # 2. 转换PDF字节格式
            pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)
            print(f"PDF字节转换完成")

            # 3. 生成PDF文件名和本地图像目录
            pdf_name = os.path.basename(pdf_path)
            local_image_dir = f"/mnt/data/mineru_ocr_local_image_dir/{pdf_name}"

            # 4. 创建本地图像目录
            if not os.path.exists(local_image_dir):
                os.makedirs(local_image_dir, exist_ok=True)
                print(f"创建本地图像目录: {local_image_dir}")

            # 5. 创建图像写入器
            image_writer = FileBasedDataWriter(local_image_dir)

            processing_time = time.time() - start_time

            result = {
                'status': 'success',
                'pdf_path': pdf_path,
                'pdf_name': pdf_name,
                'local_image_dir': local_image_dir,
                'pdf_bytes_size': len(pdf_bytes),
                'processing_time': processing_time,
                'timestamp': time.time(),
                'error': None
            }

            print(f"处理完成: {pdf_name}, 耗时: {processing_time:.2f}秒")
            return result

        except Exception as e:
            print(f"处理失败 {pdf_path}: {e}")
            return {
                'status': 'failed',
                'pdf_path': pdf_path,
                'pdf_name': os.path.basename(pdf_path),
                'local_image_dir': None,
                'pdf_bytes_size': 0,
                'processing_time': 0,
                'timestamp': time.time(),
                'error': str(e)
            }

    def process_all(self) -> Dict[str, Any]:
        """
        处理队列中的所有PDF文件

        Returns:
            Dict: 处理结果统计
        """
        if self.preProcessQueue.empty():
            print("队列为空，没有文件需要处理")
            return {'statistics': {'total_processed': 0, 'total_failed': 0}, 'results': []}

        start_time = time.time()
        tasks = []
        while not self.preProcessQueue.empty():
            try:
                pdf_path = self.preProcessQueue.get(block=False)
                tasks.append(pdf_path)
            except queue.Empty:
                break

        print(f"开始处理 {len(tasks)} 个PDF文件")

        # 提交任务到线程池
        future_to_pdf = {self.preProcessPool.submit(self.worker, pdf_path): pdf_path
                        for pdf_path in tasks}

        # 收集结果
        results = []
        processed = 0
        failed = 0

        for future in as_completed(future_to_pdf):
            pdf_path = future_to_pdf[future]
            try:
                result = future.result()
                results.append(result)

                with self.lock:
                    self.results.append(result)

                if result['status'] == 'success':
                    processed += 1
                else:
                    failed += 1

            except Exception as e:
                print(f"任务执行异常 {pdf_path}: {e}")
                failed += 1
                error_result = {
                    'status': 'failed',
                    'pdf_path': pdf_path,
                    'error': str(e),
                    'timestamp': time.time()
                }
                results.append(error_result)
                with self.lock:
                    self.results.append(error_result)

        total_time = time.time() - start_time
        print(f"处理完成: 成功 {processed}, 失败 {failed}, 总耗时: {total_time:.2f}秒")

        return {
            'statistics': {
                'total_processed': processed,
                'total_failed': failed,
                'total_tasks': len(tasks),
                'total_time': total_time
            },
            'results': results
        }

    def process_one(self, pdf_path: str) -> Dict[str, Any]:
        """
        处理单个PDF文件

        Args:
            pdf_path: PDF文件路径

        Returns:
            Dict: 处理结果
        """
        if not os.path.exists(pdf_path):
            return {
                'status': 'failed',
                'pdf_path': pdf_path,
                'error': 'File not found',
                'timestamp': time.time()
            }

        result = self.worker(pdf_path)

        with self.lock:
            self.results.append(result)

        return result

    def get_queue_status(self) -> Dict[str, Any]:
        """
        获取队列状态

        Returns:
            Dict: 队列状态信息
        """
        return {
            'queue_size': self.preProcessQueue.qsize(),
            'max_queue_size': self.max_queue_size,
            'num_workers': self.num_workers,
            'total_processed': len(self.results),
            'successful_processed': len([r for r in self.results if r['status'] == 'success']),
            'failed_processed': len([r for r in self.results if r['status'] == 'failed'])
        }

    def get_results(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        获取处理结果

        Args:
            limit: 限制返回结果数量
            offset: 偏移量

        Returns:
            Dict: 处理结果
        """
        with self.lock:
            total = len(self.results)
            results_slice = self.results[offset:offset + limit]

            return {
                'total': total,
                'offset': offset,
                'limit': limit,
                'results': results_slice
            }

    def clear_queue(self) -> Dict[str, Any]:
        """
        清空队列

        Returns:
            Dict: 清空操作结果
        """
        cleared_count = 0
        while not self.preProcessQueue.empty():
            try:
                self.preProcessQueue.get(block=False)
                cleared_count += 1
            except queue.Empty:
                break

        return {
            'cleared_count': cleared_count,
            'message': f'已清空 {cleared_count} 个任务'
        }

    def clear_results(self) -> Dict[str, Any]:
        """
        清空结果历史

        Returns:
            Dict: 清空操作结果
        """
        with self.lock:
            cleared_count = len(self.results)
            self.results = []

        return {
            'cleared_count': cleared_count,
            'message': f'已清空 {cleared_count} 条结果记录'
        }

    def save_results_to_file(self, output_file: str = "pdf_results.json") -> Dict[str, Any]:
        """
        保存结果到JSON文件

        Args:
            output_file: 输出文件路径

        Returns:
            Dict: 保存操作结果
        """
        try:
            with self.lock:
                results_to_save = {
                    'statistics': {
                        'total_processed': len(self.results),
                        'successful_processed': len([r for r in self.results if r['status'] == 'success']),
                        'failed_processed': len([r for r in self.results if r['status'] == 'failed']),
                    },
                    'results': self.results,
                    'queue_status': self.get_queue_status()
                }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results_to_save, f, ensure_ascii=False, indent=2)

            print(f"结果已保存到: {output_file}")
            return {
                'status': 'success',
                'output_file': output_file,
                'results_count': len(self.results)
            }

        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }

    def shutdown(self):
        """关闭服务器"""
        self.preProcessPool.shutdown(wait=True)
        print("PDF服务器已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()