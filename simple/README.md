# Simple MinerU

基于pool.md设计的简化三级队列架构PDF处理系统。

## 架构特点

### 三级队列系统

按照pool.md设计，系统采用三级队列架构：

- **preprocess_queue**: 不限长度 - 接收原始PDF处理任务
- **gpu_queue**: 定长队列(maxlen 100) - 控制GPU内存使用
- **post_queue**: 不限长度 - 接收GPU推理结果

### 工作进程配置

- **preProcessPool**: 2个预处理工作进程（CPU密集型）
- **gpuPool**: 4个GPU工作进程（GPU推理）
- **postProcessPool**: 2个后处理工作进程（文件保存）

## 文件结构

```
simple/
├── main_demo.py        # 系统入口
├── ocr_pdf_pool.py     # PDF处理逻辑
├── process_pool.py      # 三级队列进程池
├── arch.md             # 详细架构文档
└── README.md           # 本文件
```

## 快速开始

### 环境要求

- Python 3.8+
- PyTorch (GPU支持)
- PyMuPDF (PDF处理)
- 多进程环境支持

### 运行示例

```bash
cd simple/
python main_demo.py
```

### 默认配置

- **输入目录**: `/home/ubuntu/MinerU-merge/demo/pdfs`
- **输出目录**: `/tmp/result`
- **GPU设备**: `0`
- **每GPU工作进程**: `1`
- **批处理大小**: `384`

## 架构流程

```mermaid
graph LR
    A[PDF文件] --> B[preprocess_queue]
    B --> C[预处理CPU x2]
    C --> D[gpu_queue maxlen 100]
    D --> E[GPU推理 x4]
    E --> F[post_queue]
    F --> G[后处理CPU x2]
    G --> H[最终结果]
```

## 核心组件

### SimpleProcessPool (process_pool.py)
三级队列系统的核心管理器，实现：
- 预处理工作进程管理
- GPU工作进程管理
- 后处理工作进程管理
- 队列流控机制

### OCR PDF Pool (ocr_pdf_pool.py)
PDF处理业务逻辑，包含：
- PDF加载和图像转换
- GPU模型推理
- 结果保存和压缩

### Main Demo (main_demo.py)
系统启动和配置管理，负责：
- 环境变量设置
- 参数配置
- 错误处理和日志

## 性能优化

### 内存控制
- GPU队列最大长度限制(100)防止内存溢出
- 进程隔离避免内存泄漏
- 及时释放GPU资源

### 并行处理
- 三级队列实现流水线并行
- 不同阶段可独立扩展
- 错误隔离保证系统稳定性

## 配置参数

### 队列参数
```python
preprocessing_workers = 2    # 预处理工作进程数
max_gpu_queue_size = 100     # GPU队列最大长度
postprocessing_workers = 2   # 后处理工作进程数
```

### 业务参数
```python
gpu_ids = "0"                # GPU设备ID
workers_per_gpu = 1         # 每GPU工作进程数
batch_size = 384            # 批处理大小
max_pages = None            # 最大页数限制
```

## 监控指标

系统提供实时队列状态监控：
- `preprocess_queue_size`: 预处理队列长度
- `gpu_queue_size`: GPU队列长度（应接近100）
- `post_queue_size`: 后处理队列长度

## 扩展性

### 水平扩展
- 增加GPU设备数量
- 调整工作进程配置

### 垂直扩展
- 调整队列大小
- 优化批处理参数

### 模块化
- 各处理函数可独立替换
- 支持自定义业务逻辑

## 故障排除

### 常见问题
1. **GPU内存不足**: 减少`batch_size`或增加`max_gpu_queue_size`限制
2. **处理速度慢**: 增加工作进程数或优化GPU利用率
3. **进程卡死**: 检查队列长度和错误日志

### 日志输出
系统会输出详细的处理日志：
```
=== 启动三级队列PDF处理系统 ===
预处理工作进程 0 启动, PID: 12345
GPU工作进程 0 (GPU 0) 启动, PID: 12346
后处理工作进程 0 启动, PID: 12347
...
```

## 更新日志

### v1.0.0
- 实现基于pool.md的三级队列架构
- 支持2-4-2工作进程配置
- 实现GPU队列流控机制
- 添加完整的错误处理和监控