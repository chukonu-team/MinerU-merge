import subprocess
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('transfer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RCloneTransfer:
    def __init__(self, input_file, done_file, error_file, max_workers,target_path):
        self.input_file = input_file
        self.done_file = done_file
        self.error_file = error_file
        self.max_workers = max_workers
        self.completed_files = set()
        self.error_files = set()
        self.target_path = target_path
        
        # 加载已完成和错误的文件列表
        self._load_existing_records()
    
    def _load_existing_records(self):
        """加载已完成和错误的文件记录"""
        # 加载已完成文件
        if os.path.exists(self.done_file):
            with open(self.done_file, 'r') as f:
                self.completed_files = set(line.strip() for line in f if line.strip())
            logger.info(f"Loaded {len(self.completed_files)} completed files from {self.done_file}")
        
        # 加载错误文件
        if os.path.exists(self.error_file):
            with open(self.error_file, 'r') as f:
                self.error_files = set(line.strip() for line in f if line.strip())
            logger.info(f"Loaded {len(self.error_files)} error files from {self.error_file}")
    
    def _record_success(self, filename):
        """记录成功传输的文件"""
        with open(self.done_file, 'a') as f:
            f.write(f"{filename}\n")
        self.completed_files.add(filename)
    
    def _record_error(self, filename, error_msg):
        """记录传输失败的文件"""
        with open(self.error_file, 'a') as f:
            f.write(f"{filename}\t{error_msg}\n")
        self.error_files.add(filename)
    
    def process_line(self, line):
        """处理单行数据并执行rclone复制"""
        line = line.strip()
        if not line:
            return None, "Empty line"
        
        try:
            # 解析文件名
            filename = line.split('/')[-1]
            
            # 检查是否已完成或已在错误列表中
            if filename in self.completed_files:
                return filename, "Already completed"
            if filename in self.error_files:
                return filename, "Previously failed"
            
            # 构建目标路径
            target_path = f"{self.target_path}/{filename}"
            
        
            # 构建rclone命令（启用checksum）
            cmd = [
                "rclone", "copyto",
                "--checksum",  # 启用checksum验证
                "--progress",  # 显示进度
                "--verbose",   # 详细输出
                line, 
                target_path
            ]
        
            # 执行命令
            start_time = time.time()
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=600,  # 10分钟超时
                encoding='utf-8',
                errors='ignore'
            )
            end_time = time.time()
            duration = end_time - start_time
            
            if result.returncode == 0:
                self._record_success(filename)
                logger.info(f"Successfully copied {filename} in {duration:.2f}s")
                return filename, "Success"
            else:
                error_msg = f"Exit code {result.returncode}: {result.stderr[:200]}"
                self._record_error(filename, error_msg)
                logger.error(f"Failed to copy {filename}: {error_msg}")
                return filename, f"Failed: {error_msg}"
                
        except subprocess.TimeoutExpired:
            error_msg = "Timeout after 600 seconds"
            self._record_error(filename, error_msg)
            logger.error(f"Timeout copying {filename}")
            return filename, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._record_error(filename, error_msg)
            logger.error(f"Error processing {line}: {error_msg}")
            return filename, error_msg
    
    def run(self):
        """运行传输任务"""
        if not os.path.exists(self.input_file):
            logger.error(f"Input file {self.input_file} not found")
            return
        
        # 读取所有行
        with open(self.input_file, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
        
        logger.info(f"Found {len(lines)} files to process")
        logger.info(f"Skipping {len(self.completed_files)} already completed files")
        logger.info(f"Skipping {len(self.error_files)} previously failed files")
        
        # 过滤掉已完成和错误的文件
        filtered_lines = []
        for line in lines:
            filename = line.split('/')[-1]
            if filename not in self.completed_files and filename not in self.error_files:
                filtered_lines.append(line)
        
        logger.info(f"Remaining files to process: {len(filtered_lines)}")
        
        if not filtered_lines:
            logger.info("No files to process")
            return
        
        # 使用线程池并行处理
        successful = 0
        failed = 0
        skipped = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_line = {executor.submit(self.process_line, line): line for line in filtered_lines}
            
            # 处理完成的任务
            for future in as_completed(future_to_line):
                line = future_to_line[future]
                try:
                    filename, result = future.result()
                    if "Success" in result:
                        successful += 1
                    elif "Failed" in result or "Timeout" in result or "Unexpected" in result:
                        failed += 1
                    else:
                        skipped += 1
                        
                    # 每100个文件输出一次进度
                    total_processed = successful + failed + skipped
                    if total_processed % 100 == 0:
                        logger.info(f"Progress: {total_processed}/{len(filtered_lines)} "
                                  f"(Success: {successful}, Failed: {failed}, Skipped: {skipped})")
                        
                except Exception as e:
                    logger.error(f"Exception processing {line}: {str(e)}")
                    failed += 1
        
        # 最终统计
        logger.info(f"Transfer completed. Total: {len(filtered_lines)}")
        logger.info(f"Successful: {successful}, Failed: {failed}, Skipped: {skipped}")
        logger.info(f"Results saved to: {self.done_file} (success) and {self.error_file} (errors)")

def main():
    # 配置参数
    input_file = "/root/wangshd/batch6/batch6_keys.txt"
    done_file = "/root/wangshd/batch6/download/upload_done.txt"
    error_file = "/root/wangshd/batch6/download/upload_error.txt"
    max_workers = 50  # 并行传输数量
    target_path = "houdutech:batch2/batch6/pdf"
    
    # 创建传输器并运行
    transfer = RCloneTransfer(
        input_file=input_file,
        done_file=done_file,
        error_file=error_file,
        max_workers=max_workers,
        target_path=target_path
    )
    
    transfer.run()

if __name__ == "__main__":
    main()
