# MinerU PDF处理系统架构文档

## 系统概述

MinerU PDF处理系统是一个基于多进程和多GPU的高性能PDF文档分析和处理平台。系统采用双缓冲队列架构，实现了CPU预处理和GPU推理的并行处理，支持大规模PDF文档的批量处理。

## 整体架构图

```mermaid
graph TB
    subgraph "输入层"
        PDF[PDF文件] --> Bucket[bucket目录]
        Bucket --> Scanner[目录扫描器]
    end

    subgraph "控制层 main.py"
        Scanner --> Env[环境变量读取]
        Env --> Config[配置参数]
        Config --> ProcessEntry[process_pdfs入口]
    end

    subgraph "业务层 ocr_pdf_batch.py"
        ProcessEntry --> SimpleMinerUPool[SimpleMinerUPool]
        SimpleMinerUPool --> BatchCreator[批次创建器]
        BatchCreator --> TaskSubmitter[任务提交器]
    end

    subgraph "进程池层 process_pool.py"
        TaskSubmitter --> PreprocessingQueue[预处理队列]
        PreprocessingQueue --> PreprocessingWorkers[预处理工作进程]
        PreprocessingWorkers --> GPUQueue[GPU任务队列]
        GPUQueue --> GPUWorkers[GPU工作进程]
        GPUWorkers --> ResultQueue[结果队列]
    end

    subgraph "输出层"
        ResultQueue --> CompressedJSON[压缩JSON结果]
        ResultQueue --> PageResult[页面结果信息]
        CompressedJSON --> OutputDir[输出目录]
        PageResult --> OutputDir
    end

    style PreprocessingQueue fill:#e1f5fe
    style GPUQueue fill:#f3e5f5
    style ResultQueue fill:#e8f5e8
```

## 数据流程图

```mermaid
sequenceDiagram
    participant Main as main.py
    participant MinerUPool as SimpleMinerUPool
    participant ProcPool as ProcessPool
    participant PreWorker as Preprocessing Worker
    participant GPUWorker as GPU Worker
    participant Storage as 文件系统

    Main->>MinerUPool: process_pdf_files(pdf_list, output_dir)
    MinerUPool->>ProcPool: submit_task(gpu_worker_task, batch_data)

    par 并行预处理
        ProcPool->>PreWorker: 预处理队列任务
        PreWorker->>PreWorker: 读取PDF文件
        PreWorker->>PreWorker: 转换PDF字节
        PreWorker->>PreWorker: 加载图像(Base64)
        PreWorker->>ProcPool: 提交到GPU队列
    and 并行GPU处理
        ProcPool->>GPUWorker: GPU队列任务
        GPUWorker->>GPUWorker: 模型推理
        GPUWorker->>GPUWorker: 生成middle_json
        GPUWorker->>Storage: 保存压缩结果
        GPUWorker->>ProcPool: 返回处理结果
    end

    ProcPool->>MinerUPool: get_result()
    MinerUPool->>Main: 返回所有结果
```

## 核心组件架构

### 1. 双缓冲队列系统

```mermaid
graph LR
    subgraph "双缓冲架构"
        A[原始任务] --> B[预处理队列]
        B --> C[CPU预处理]
        C --> D[GPU任务队列]
        D --> E[GPU推理处理]
        E --> F[结果队列]

        style B fill:#ffcdd2
        style D fill:#c5e1a5
        style F fill:#bbdefb
    end

    subgraph "流控机制"
        G[max_gpu_queue_size<br/>控制内存使用]
        H[preprocessing_workers<br/>CPU并行度]
        I[gpu_workers<br/>GPU并行度]
    end
```

### 2. 进程池内部结构

```mermaid
graph TB
    subgraph "SimpleProcessPool"
        PM[进程管理器]

        subgraph "预处理层"
            PQ[预处理队列]
            PW1[预处理工作进程1]
            PW2[预处理工作进程2]
            PW3[预处理工作进程...]
        end

        subgraph "GPU处理层"
            GQ[GPU任务队列]
            GW1[GPU工作进程1]
            GW2[GPU工作进程2]
            GW3[GPU工作进程...]
        end

        RQ[结果队列]
        SE[关闭事件]

        PM --> PQ
        PQ --> PW1
        PQ --> PW2
        PQ --> PW3
        PW1 --> GQ
        PW2 --> GQ
        PW3 --> GQ
        GQ --> GW1
        GQ --> GW2
        GQ --> GW3
        GW1 --> RQ
        GW2 --> RQ
        GW3 --> RQ
        PM --> SE
    end
```

## 处理管道流程

```mermaid
flowchart TD
    Start([开始处理]) --> Input[读取PDF文件]
    Input --> Validate{文件验证}
    Validate -->|有效| PDFBytes[转换为PDF字节]
    Validate -->|无效| Skip[跳过文件]

    PDFBytes --> ImageLoad[加载PDF页面图像]
    ImageLoad --> Base64[转换为Base64格式]
    Base64 --> PreprocessResult[预处理完成]

    PreprocessResult --> GPUModel[GPU模型推理]
    GPUModel --> MiddleJSON[生成middle_json]
    MiddleJSON --> Compress[压缩为ZIP]
    Compress --> SaveResult[保存结果文件]

    Skip --> NextBatch{下一批次?}
    SaveResult --> NextBatch
    NextBatch -->|是| Input
    NextBatch -->|否| End([处理完成])

    style Start fill:#4caf50,color:#fff
    style End fill:#f44336,color:#fff
    style GPUModel fill:#2196f3,color:#fff
```

## 文件结构映射

```mermaid
graph TD
    subgraph "源码结构"
        MainPy[main.py<br/>系统入口]
        BatchPy[ocr_pdf_batch.py<br/>批处理逻辑]
        PoolPy[process_pool.py<br/>进程池管理]
    end

    subgraph "目录结构"
        InputDir[/mnt/data/pdf/<br/>输入PDF目录]
        OutputDir[/mnt/data/output/<br/>输出结果目录]
        TempDir[/mnt/data/mineru_ocr_local_image_dir/<br/>临时图像目录]
    end

    MainPy --> BatchPy
    BatchPy --> PoolPy
    BatchPy --> InputDir
    BatchPy --> OutputDir
    BatchPy --> TempDir
```

## 性能优化策略

### 1. 并行处理优化

```mermaid
graph LR
    subgraph "时间线优化"
        T1[时间阶段1<br/>文件I/O]
        T2[时间阶段2<br/>CPU预处理]
        T3[时间阶段3<br/>GPU推理]
        T4[时间阶段4<br/>结果保存]

        T1 -.-> T2
        T2 -.-> T3
        T3 -.-> T4

        style T2 fill:#ffecb3
        style T3 fill:#e1bee7
    end

    subgraph "并行度配置"
        PreWorkers[预处理工作进程数]
        GPUWorkers[GPU工作进程数]
        GPUCount[GPU设备数量]
    end
```

### 2. 内存管理策略

```mermaid
graph TB
    subgraph "内存控制"
        QueueSize[队列大小限制]
        BatchControl[批次大小控制]
        MemoryUtil[GPU内存利用率]
        VRAMSize[显存大小配置]
    end

    subgraph "清理机制"
        AutoClean[自动清理缓存]
        ProcessExit[进程退出清理]
        ErrorHandle[错误情况清理]
    end
```

## 关键配置参数

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `GPU_IDS` | string | "0,1,2,3,4,5,6,7" | GPU设备ID列表 |
| `WORKERS_PER_GPU` | int | 2 | 每个GPU的工作进程数 |
| `VRAM_SIZE_GB` | int | 24 | GPU显存大小(GB) |
| `MAX_PAGES` | int | None | 单个PDF最大页数限制 |
| `BATCH_SIZE` | int | 384 | 批处理大小(页数) |
| `GPU_MEMORY_UTILIZATION` | float | 0.5 | GPU内存使用率 |
| `SHUFFLE` | boolean | false | 是否随机打乱文件顺序 |
| `PROPORTION` | float | 0 | 处理比例阈值 |

## 监控指标

```mermaid
graph LR
    subgraph "性能指标"
        Throughput[吞吐量<br/>文件/秒]
        Latency[延迟<br/>平均处理时间]
        Utilization[资源利用率<br/>CPU/GPU/内存]
        ErrorRate[错误率<br/>失败/总数]
    end

    subgraph "队列指标"
        PreQueueSize[预处理队列大小]
        GPUQueueSize[GPU队列大小]
        ResultQueueSize[结果队列大小]
        ProcessedCount[已处理任务数]
    end
```

## 扩展性设计

系统支持以下扩展能力：

1. **水平扩展**: 通过增加GPU设备数量扩展处理能力
2. **垂直扩展**: 调整每GPU工作进程数优化资源利用
3. **模块化**: 各组件独立，便于替换和升级
4. **配置驱动**: 通过环境变量灵活调整系统行为

这个架构设计实现了高效、可扩展、可维护的PDF处理系统，适用于大规模文档处理场景。