import multiprocessing as mp
import time
import os
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass
from queue import Empty, Full


def _preprocessing_worker(worker_id: int, preprocessing_queue: mp.Queue,
                          gpu_task_queue: mp.Queue,
                          max_gpu_queue_size: int,
                          shutdown_event: mp.Event):
    """单个预处理工作进程函数 - 真实场景"""
    processed_count = 0

    print(f"Preprocessing worker {worker_id} started with PID {os.getpid()}")

    while not shutdown_event.is_set():
        try:
            # 从预处理队列获取原始任务
            task = preprocessing_queue.get(timeout=1.0)
            if task is None:
                break

            task_id, func, args, kwargs = task

            print(f"Preprocessing worker {worker_id} processing task {task_id}...")

            # 执行真实的预处理工作
            try:
                preprocessed_result = func(*args, **kwargs)
                processed_count += 1
                print(f"Preprocessing worker {worker_id} completed task {task_id}")
            except Exception as preprocess_error:
                print(f"Preprocessing worker {worker_id} failed task {task_id}: {preprocess_error}")
                # 如果预处理失败，仍然将错误信息传递给GPU队列处理
                preprocessed_result = {
                    'success': False,
                    'error': str(preprocess_error),
                    'preprocessing_failed': True,
                    'batch_info': args[0] if args else {}
                }

            # 检查GPU任务队列是否已满
            while gpu_task_queue.qsize() >= max_gpu_queue_size and not shutdown_event.is_set():
                print(f"Preprocessing worker {worker_id}: GPU task queue is full ({gpu_task_queue.qsize()}/{max_gpu_queue_size}), waiting...")
                time.sleep(1)

            if shutdown_event.is_set():
                break

            # 将预处理后的任务放入GPU任务队列
            # 现在使用gpu_processing_task作为GPU函数
            from ocr_pdf_batch import gpu_processing_task
            preprocessed_task = (task_id, gpu_processing_task, (preprocessed_result,), kwargs)
            gpu_task_queue.put(preprocessed_task)
            print(f"Preprocessing worker {worker_id} queued task {task_id} for GPU processing")

        except Empty:
            continue
        except Exception as e:
            print(f"Preprocessing worker {worker_id} error: {e}")
            break

    print(f"Preprocessing worker {worker_id} exiting, processed {processed_count} tasks")


def _preprocessing_process_manager(num_workers: int, preprocessing_queue: mp.Queue,
                                 gpu_task_queue: mp.Queue,
                                 max_gpu_queue_size: int,
                                 shutdown_event: mp.Event):
    """预处理进程管理器 - 启动多个预处理工作进程"""
    workers = []

    print(f"Starting preprocessing process manager with {num_workers} workers")

    # 启动多个预处理工作进程
    for i in range(num_workers):
        worker = mp.Process(
            target=_preprocessing_worker,
            args=(i, preprocessing_queue, gpu_task_queue, max_gpu_queue_size, shutdown_event)
        )
        worker.start()
        workers.append(worker)
        print(f"Started preprocessing worker {i} with PID {worker.pid}")

    # 等待所有工作进程完成
    for worker in workers:
        worker.join()

    print("All preprocessing workers have completed")


@dataclass
class WorkerInfo:
    """工作进程信息"""
    worker_id: int
    process: mp.Process
    gpu_id: int
    pid: Optional[int] = None
    status: str = "running"


def _worker_process(worker_id: int, gpu_id: int, task_queue: mp.Queue,
                    result_queue: mp.Queue, shutdown_event: mp.Event):
    """工作进程主循环函数"""
    task_count = 0
    os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu_id)

    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.set_device(0)
            torch.cuda.empty_cache()
            gpu_name = torch.cuda.get_device_name(0)
            total_memory = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
            print(f"Worker {worker_id} (GPU {gpu_id}) initialized: {gpu_name} ({total_memory:.1f}GB)")
    except ImportError:
        pass

    while not shutdown_event.is_set():
        try:
            task = task_queue.get(timeout=1.0)
            if task is None:
                break

            task_id, func, args, kwargs = task
            try:
                kwargs_with_gpu = kwargs.copy()
                kwargs_with_gpu['gpu_id'] = gpu_id
                result = func(*args, **kwargs_with_gpu)
                result_queue.put((task_id, 'success', result))
                task_count += 1
            except Exception as e:
                print(f"Worker {worker_id} task error: {e}")
                result_queue.put((task_id, 'error', str(e)))
        except Empty:
            continue
        except Exception as e:
            print(f"Worker {worker_id} unexpected error: {e}")
            break

    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except:
        pass

    print(f"Worker {worker_id} (GPU {gpu_id}) exiting, processed {task_count} tasks")


class SimpleProcessPool:
    """简化进程池类 - 支持双缓冲队列"""

    def __init__(self, gpu_ids: list = None, workers_per_gpu: int = 2,
                 enable_preprocessing: bool = True, max_gpu_queue_size: int = 100,
                 preprocessing_workers: int = 4):
        if gpu_ids is None:
            gpu_ids = [0]

        self.gpu_ids = gpu_ids
        self.workers_per_gpu = workers_per_gpu
        self.max_workers = len(gpu_ids) * workers_per_gpu
        self.workers: Dict[int, WorkerInfo] = {}
        self.next_worker_id = 0

        # 双缓冲队列系统
        self.enable_preprocessing = enable_preprocessing
        self.max_gpu_queue_size = max_gpu_queue_size
        self.preprocessing_workers = preprocessing_workers

        # 原始任务队列（用于预处理）
        self.preprocessing_queue = mp.Queue()
        # GPU任务队列（预处理后的任务）
        self.gpu_task_queue = mp.Queue()

        self.result_queue = mp.Queue()
        self.shutdown_event = mp.Event()
        self.preprocessing_manager: Optional[mp.Process] = None

        # 启动多进程预处理管理器
        if self.enable_preprocessing:
            self.preprocessing_manager = mp.Process(
                target=_preprocessing_process_manager,
                args=(self.preprocessing_workers, self.preprocessing_queue,
                      self.gpu_task_queue, self.max_gpu_queue_size, self.shutdown_event)
            )
            self.preprocessing_manager.start()
            print(f"Started preprocessing manager with {preprocessing_workers} workers, PID {self.preprocessing_manager.pid}")

        for gpu_id in self.gpu_ids:
            for _ in range(self.workers_per_gpu):
                self._create_worker(gpu_id)

    def _create_worker(self, gpu_id: int) -> int:
        if len(self.workers) >= self.max_workers:
            raise RuntimeError(f"Maximum workers reached")

        worker_id = self.next_worker_id
        self.next_worker_id += 1

        # 根据是否启用预处理选择队列
        task_queue_for_worker = self.gpu_task_queue if self.enable_preprocessing else self.preprocessing_queue

        process = mp.Process(
            target=_worker_process,
            args=(worker_id, gpu_id, task_queue_for_worker, self.result_queue, self.shutdown_event)
        )

        worker_info = WorkerInfo(
            worker_id=worker_id,
            process=process,
            gpu_id=gpu_id
        )

        process.start()
        worker_info.pid = process.pid
        self.workers[worker_id] = worker_info

        print(f"Created worker {worker_id} on GPU {gpu_id} with PID {process.pid}")
        return worker_id

    def submit_task(self, func: Callable, *args, **kwargs) -> int:
        task_id = int(time.time() * 1000000)
        task = (task_id, func, args, kwargs)

        # 根据是否启用预处理选择提交队列
        if self.enable_preprocessing:
            self.preprocessing_queue.put(task)
            print(f"Submitted task {task_id} to preprocessing queue")
        else:
            self.gpu_task_queue.put(task)
            print(f"Submitted task {task_id} directly to GPU task queue")

        return task_id

    def get_result(self, timeout: float = None) -> Optional[tuple]:
        try:
            return self.result_queue.get(timeout=timeout)
        except Empty:
            return None

    def is_task_queue_empty(self) -> bool:
        if self.enable_preprocessing:
            return self.preprocessing_queue.empty() and self.gpu_task_queue.empty()
        else:
            return self.gpu_task_queue.empty()

    def get_queue_size(self) -> int:
        if self.enable_preprocessing:
            return self.preprocessing_queue.qsize() + self.gpu_task_queue.qsize()
        else:
            return self.gpu_task_queue.qsize()

    def get_preprocessing_queue_size(self) -> int:
        """获取预处理队列大小"""
        if self.enable_preprocessing:
            return self.preprocessing_queue.qsize()
        return 0

    def get_gpu_queue_size(self) -> int:
        """获取GPU任务队列大小"""
        return self.gpu_task_queue.qsize()

    def set_complete_signal(self):
        task_queue_for_signal = self.gpu_task_queue if self.enable_preprocessing else self.preprocessing_queue
        for _ in range(len(self.workers)):
            task_queue_for_signal.put(None)

    def all_tasks_completed(self) -> bool:
        return self.is_task_queue_empty() and len(self.workers) == 0

    def shutdown(self, timeout: float = 10.0):
        print("Shutting down process pool...")
        self.shutdown_event.set()

        # 关闭多进程预处理管理器
        if self.enable_preprocessing and self.preprocessing_manager:
            print("Shutting down preprocessing manager...")
            # 为每个预处理工作进程发送停止信号
            for _ in range(self.preprocessing_workers):
                self.preprocessing_queue.put(None)

            self.preprocessing_manager.join(timeout=10.0)
            if self.preprocessing_manager.is_alive():
                self.preprocessing_manager.terminate()
                self.preprocessing_manager.join(timeout=5.0)
                if self.preprocessing_manager.is_alive():
                    self.preprocessing_manager.kill()
                    self.preprocessing_manager.join()

        # 关闭工作进程
        task_queue_for_shutdown = self.gpu_task_queue if self.enable_preprocessing else self.preprocessing_queue
        for _ in range(len(self.workers)):
            task_queue_for_shutdown.put(None)

        dead_workers = []
        start_time = time.time()

        while time.time() - start_time < timeout and self.workers:
            for worker_id, worker_info in list(self.workers.items()):
                if not worker_info.process.is_alive():
                    dead_workers.append(worker_id)
                else:
                    worker_info.process.join(timeout=1.0)

            for worker_id in dead_workers:
                if worker_id in self.workers:
                    del self.workers[worker_id]
            dead_workers.clear()

        for worker_info in self.workers.values():
            if worker_info.process.is_alive():
                worker_info.process.terminate()
                worker_info.process.join(timeout=2.0)
                if worker_info.process.is_alive():
                    worker_info.process.kill()
                    worker_info.process.join()

        self.workers.clear()
        print("Process pool shutdown complete")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()