import os
import base64
import requests
import threading
from pathlib import Path
import queue
import time

# 配置参数
BASE_URL = "http://localhost:8000/predict"
INPUT_DIR = "/home/ubuntu/pdfs"
OUTPUT_DIR = "./output"
MAX_WORKERS = 16

# 请求参数 - 注意：现在在options中
REQUEST_OPTIONS = {
    "backend": "pipeline",  # 使用pipeline而不是vlm-vllm-async-engine
    "lang": "ch",
    "method": "auto",
    "formula_enable": True,
    "table_enable": True,
}

class PDFProcessor:
    def __init__(self):
        self.lock = threading.Lock()
        self.processed = 0
        self.successful = 0
        self.failed = 0
        self.total_files = 0

    def worker(self, file_queue):
        """工作线程函数"""
        while True:
            try:
                pdf_path = file_queue.get_nowait()
            except queue.Empty:
                break

            try:
                self.process_file(pdf_path)
            finally:
                file_queue.task_done()

    def process_file(self, pdf_path):
        """处理单个PDF文件"""
        try:
            with self.lock:
                self.processed += 1
                print(f"[{self.processed}/{self.total_files}] 处理: {os.path.basename(pdf_path)}")

            # 读取并base64编码PDF文件
            with open(pdf_path, 'rb') as f:
                file_b64 = base64.b64encode(f.read()).decode('utf-8')

            # 构建请求负载
            payload = {
                'file': file_b64,
                'options': REQUEST_OPTIONS.copy()
            }

            # 发送JSON请求
            response = requests.post(
                BASE_URL,
                json=payload,
                timeout=300
            )

            if response.status_code == 200:
                with self.lock:
                    self.successful += 1
                    print(f"✓ 成功: {os.path.basename(pdf_path)}")
            else:
                with self.lock:
                    self.failed += 1
                    print(f"✗ 失败: {os.path.basename(pdf_path)} - 状态码: {response.status_code}")
                    print(f"  响应: {response.text[:200]}")

        except Exception as e:
            with self.lock:
                self.failed += 1
                print(f"✗ 错误: {os.path.basename(pdf_path)} - {str(e)}")

    def process_directory(self, input_dir):
        """处理整个目录"""
        pdf_files = list(Path(input_dir).glob("*.pdf"))
        self.total_files = len(pdf_files)

        if not pdf_files:
            print("没有找到PDF文件")
            return

        print(f"找到 {self.total_files} 个PDF文件")
        print(f"启动 {MAX_WORKERS} 个工作线程...")

        # 创建文件队列
        file_queue = queue.Queue()
        for pdf_file in pdf_files:
            file_queue.put(str(pdf_file))

        # 创建并启动工作线程
        threads = []
        for i in range(MAX_WORKERS):
            thread = threading.Thread(target=self.worker, args=(file_queue,))
            thread.daemon = True
            thread.start()
            threads.append(thread)

        # 等待所有任务完成
        file_queue.join()

        print(f"\n处理完成!")
        print(f"成功: {self.successful}")
        print(f"失败: {self.failed}")
        print(f"总计: {self.total_files}")

def main():
    processor = PDFProcessor()
    processor.process_directory(INPUT_DIR)

if __name__ == "__main__":
    main()
