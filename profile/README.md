# MinerU PDF解析性能分析工具

## 🎯 功能特点

- 🔍 **深度性能分析**：使用cProfile进行函数级CPU瓶颈分析
- 📊 **批量目录处理**：支持整个PDF目录的批量性能测试
- ⚡ **快速性能测试**：轻量级工具，快速获得关键性能指标
- 🎛️ **参数优化**：支持不同DPI、线程数、页面范围测试
- 📈 **DPI性能对比**：自动对比不同分辨率下的性能表现
- 🔄 **性能回归测试**：适合持续监控和基准测试
- 📁 **详细报告生成**：生成可读性强的性能分析报告

## 🚀 快速开始

### 1. 环境准备

```bash
cd /home/ubuntu/MinerU-merge/profile
./install_dependencies.sh
```

### 2. 基本使用

#### 单文件分析
```bash
# 快速性能测试（推荐初学者）
./run_with_venv.sh <PDF文件路径> --simple

# 详细性能分析（推荐深度分析）
./run_with_venv.sh <PDF文件路径> --demo

# DPI性能对比
./run_with_venv.sh <PDF文件路径> --dpi-compare
```

#### 🆕 批量目录分析（解决单文件测试时间过短问题）
```bash
# 批量快速测试整个PDF目录
./run_with_venv.sh --directory <PDF目录路径> --simple

# 批量详细分析整个PDF目录
./run_with_venv.sh --directory <PDF目录路径> --demo

# 批量DPI性能对比整个目录
./run_with_venv.sh --directory <PDF目录路径> --dpi-compare

# 自定义DPI对比批量测试
./run_with_venv.sh --directory <PDF目录路径> --dpi-list "150,200,300"

# 限制处理的文件数量
./run_with_venv.sh --directory <PDF目录路径> --max-files 10 --simple
```

### 3. 高级使用

#### 程序化使用
```python
# 激活虚拟环境
source venv_profile/bin/activate

# 批量分析
python pdf_profile_demo.py --directory /path/to/pdf/files/

# 单个文件分析
python pdf_profile_demo.py /path/to/file.pdf

# 限制文件数和自定义DPI
python pdf_profile_demo.py --directory /path/to/files/ --max-files 5

# 自定义DPI对比
python simple_test.py --directory /path/to/files/ --dpi-list "150,200,300"
```

#### 简化批量工具
```python
# 使用简化批量脚本（推荐快速测试）
python batch_test_simple.py /path/to/pdf/files/ --max-files 10

# 分析整个目录
python batch_demo.py /path/to/pdf/files/
```

## 📊 性能分析输出

### 关键性能指标

1. **基础指标**
   - **文件大小**：PDF文件的物理大小（MB）
   - **处理页数**：PDF文档的页面数量
   - **生成图像数**：转换后的图像数量

2. **时间指标**
   - **文件读取时间**：从磁盘读取PDF的耗时
   - **信息获取时间**：获取PDF基本信息的耗时
   - **图像解析时间**：`load_images_from_pdf`函数总执行时间
   - **平均每页耗时**：单页平均处理时间

3. **性能指标**
   - **处理速度**：每秒处理的页面数量（页/秒）
   - **数据吞吐量**：每秒处理的数据量（MB/s）
   - **处理效率**：根据文件大小和时间的综合效率评估

### 函数级分析（详细模式）

- **cProfile统计**：按累计时间排序的函数调用列表
- **调用次数统计**：每个函数被调用的次数
- **自身耗时**：函数本身执行时间（不含子函数）
- **性能热点**：自动识别最耗时的函数调用

### 批量分析报告

- **总体统计**：处理文件数、总页数、总大小、总耗时
- **平均指标**：平均文件大小、平均处理速度、平均耗时
- **性能极值**：最快和最慢文件的性能数据
- **详细排序列表**：按处理速度排序的所有文件结果

## 🎯 使用场景

### 1. 性能瓶颈分析
- **目标**：识别`load_images_from_pdf`函数中最耗时的操作
- **方法**：使用详细性能分析模式（`--demo`）
- **输出**：函数级调用统计和热点分析

### 2. 参数优化测试
- **目标**：找到最优的DPI和线程数配置
- **方法**：使用DPI对比功能（`--dpi-compare`）
- **测试配置**：
  ```bash
  # 测试不同DPI
  ./run_with_venv.sh --directory ./test_files/ --dpi-list "150,200,300,400"

  # 测试不同线程数（修改代码中的threads参数）
  # 编辑pdf_profile_demo.py中的threads配置
  ```

### 3. 批量性能评估
- **目标**：评估大量PDF文件的总体性能表现
- **方法**：使用批量目录处理功能
- **优势**：
  - **解决单文件测试时间过短**：批量处理总时间更长，结果更可靠
  - **统计意义更强**：基于多文件的统计数据更准确
  - **异常检测更有效**：可以快速识别性能异常文件
  - **回归测试更方便**：适合代码变更前的基准测试

### 4. 性能监控和回归测试
- **目标**：持续监控PDF解析性能变化
- **方法**：
  ```bash
  # 建立性能基准
  ./run_with_venv.sh --directory ./benchmark_set/ --demo

  # 代码变更后的回归测试
  ./run_with_venv.sh --directory ./test_set/ --demo

  # 比较两次测试结果
  diff profile_outputs/batch_summary_*.txt
  ```

## 📁 输出文件说明

### 自动生成的文件
- **位置**：`./profile_outputs/`目录
- **详细分析报告**：`[filename]_profile_[timestamp].txt`
- **批量汇总报告**：`batch_summary_[timestamp].txt`
- **性能数据文件**：`[filename]_profile_[timestamp].prof`（cProfile原始数据）

### 报告文件结构
```
PDF解析性能分析报告
==================================================

文件路径: /path/to/sample.pdf
分析时间: 2025-11-27 06:41:50

性能指标:
  文件大小: 0.12 MB
  处理页数: 1
  生成图像数: 1
  总耗时: 0.138s
  平均每页耗时: 0.138s
  处理速度: 7.26 页/秒

详细性能分析 (按累计时间排序):
--------------------------------------------------
         2183 function calls (2150 primitive calls) in 0.138 seconds

   Ordered by: cumulative time
   List reduced from 399 to 30 due to restriction <30>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    0.138    0.138 /home/ubuntu/MinerU-merge/mineru/utils/pdf_image_tools.py:49(load_images_from_pdf)
        ...
```

## 🔧 高级用法

### 自定义性能分析脚本
```python
from profile.pdf_profile_demo import PDFProfiler

# 创建分析器
profiler = PDFProfiler()

# 批量分析目录
results = profiler.profile_pdf_directory(
    pdf_directory="/path/to/pdfs/",
    dpi=300,        # 自定义DPI
    start_page_id=0,
    end_page_id=None,  # 处理所有页面
    threads=8,        # 自定义线程数
    max_files=20,     # 限制处理数量
    output_dir="./custom_output"
)

# 打印汇总
profiler.print_summary()
```

### 结合其他工具
```python
# 与日志分析结合
import logging
logging.basicConfig(level=logging.DEBUG)

# 与内存监控结合
import memory_profiler

@memory_profiler.profile
def your_function():
    # 你的代码
    pass
```

## 🔍 故障排除

### 常见问题

1. **模块导入错误**
   ```bash
   # 重新安装依赖
   ./install_dependencies.sh
   ```

2. **虚拟环境问题**
   ```bash
   # 删除并重新创建虚拟环境
   rm -rf venv_profile
   ./install_dependencies.sh
   ```

3. **权限问题**
   ```bash
   # 确保脚本有执行权限
   chmod +x *.sh
   chmod +x *.py
   ```

4. **性能分析结果不可靠**
   ```bash
   # 增加处理文件数量
   ./run_with_venv.sh --directory ./more_files/ --max-files 50

   # 或者专注于特定类型的文件
   find ./test_files/ -name "*.pdf" -size +1M  # 只分析大于1MB的文件
   ```

5. **内存不足错误**
   ```bash
   # 减少并发数或分批处理
   ./run_with_venv.sh --directory ./files/ --max-files 5
   ```

## 📚 扩展阅读

- **详细使用指南**：查看 `QUICK_START.md`
- **批量处理指南**：查看 `BATCH_PROCESSING_GUIDE.md`
- **项目总结**：查看 `SUMMARY.md`
- **快速入门**：查看本README的快速开始部分
- **源码分析**：直接查看 `pdf_profile_demo.py` 和 `simple_test.py`

## 🎉 开始使用

现在您的MinerU PDF解析性能分析工具已经完全支持批量处理，可以有效地分析`load_images_from_pdf`函数的CPU瓶颈问题！

**推荐工作流程**：
1. 先用批量快速测试了解整体性能水平
2. 用详细分析识别具体的性能瓶颈
3. 用DPI对比找到最优参数配置
4. 建立性能基准线用于持续监控

立即开始：
```bash
cd /home/ubuntu/MinerU-merge/profile
./install_dependencies.sh
./run_with_venv.sh --directory /path/to/your/pdf/files/ --simple
```