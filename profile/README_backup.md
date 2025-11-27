# PDF解析CPU性能分析工具

这个工具用于分析MinerU项目中PDF解析过程的CPU性能瓶颈，特别是`load_images_from_pdf`函数。

## 功能特点

- 📊 **详细性能分析**: 使用cProfile进行函数级别的CPU性能分析
- 📈 **多维度指标**: 文件大小、处理页数、耗时、处理速度等
- 🔧 **灵活配置**: 支持不同DPI、线程数、页面范围测试
- 📝 **报告生成**: 自动生成详细的性能分析报告
- 🎯 **瓶颈定位**: 精确识别最耗时的函数调用

## 文件结构

```
profile/
├── pdf_profile_demo.py    # 主要的性能分析脚本
├── README.md             # 使用说明文档
├── simple_test.py        # 简化的测试脚本
└── profile_outputs/      # 输出目录（自动创建）
    ├── *.txt             # 详细分析报告
    └── *.prof            # 性能数据文件
```

## 使用方法

### 1. 基本用法

```bash
# 分析单个PDF文件
python profile/pdf_profile_demo.py /path/to/your/sample.pdf

# 分析多个PDF文件
python profile/pdf_profile_demo.py file1.pdf file2.pdf file3.pdf
```

### 2. 程序化使用

```python
from profile.pdf_profile_demo import PDFProfiler

# 创建分析器
profiler = PDFProfiler()

# 分析PDF文件
result = profiler.profile_pdf_parsing(
    pdf_path="path/to/your/file.pdf",
    dpi=200,           # 图像分辨率
    start_page_id=0,   # 起始页码
    end_page_id=None,  # 结束页码，None表示全部
    threads=4          # 线程数
)

# 打印结果
print(f"处理速度: {result.pdf_pages / result.total_time:.2f} 页/秒")
```

### 3. 简化测试

如果你想快速测试，可以使用简化脚本：

```bash
python profile/simple_test.py
```

## 性能分析流程

工具会按以下步骤进行性能分析：

1. **文件读取分析**
   - 测量PDF文件读取时间
   - 记录文件大小

2. **PDF预览**
   - 使用pypdfium2快速预览PDF信息
   - 获取总页数和页面范围

3. **CPU性能分析**
   - 使用cProfile监控`load_images_from_pdf`函数
   - 记录每个函数的调用次数和耗时
   - 支持多进程并行处理分析

4. **结果处理**
   - 按累计时间排序显示最耗时的函数
   - 生成详细的性能分析报告

## 关键性能指标

分析报告会包含以下关键指标：

- **文件大小**: PDF文件的物理大小
- **处理页数**: 实际处理的页面数量
- **总耗时**: `load_images_from_pdf`函数的总执行时间
- **平均每页耗时**: 单页平均处理时间
- **处理速度**: 每秒处理的页面数量
- **函数调用统计**: 最耗时的函数调用列表

## 测试建议

### 测试不同参数的影响

```python
# 测试不同DPI的影响
for dpi in [150, 200, 300]:
    result = profiler.profile_pdf_pdfs(pdf_path, dpi=dpi)
    print(f"DPI {dpi}: {result.total_time:.3f}s")

# 测试不同线程数的影响
for threads in [1, 2, 4, 8]:
    result = profiler.profile_pdf_pdfs(pdf_path, threads=threads)
    print(f"Threads {threads}: {result.total_time:.3f}s")
```

### 分析不同类型的PDF

建议测试不同特征的PDF文件：

- **页数**: 1页 vs 10页 vs 100页
- **内容**: 纯文本 vs 图像丰富 vs 混合内容
- **大小**: 小文件(<1MB) vs 大文件(>10MB)
- **复杂度**: 简单布局 vs 复杂布局

## 输出文件说明

### 详细分析报告 (*.txt)

包含完整的性能分析结果，包括：
- 基本信息（文件路径、大小等）
- 性能指标（耗时、速度等）
- 函数调用统计（按耗时排序）

### Profile数据文件 (*.prof)

保存原始的性能分析数据，可以用于：
- 使用Python的pstats库进行进一步分析
- 可视化工具展示
- 与其他分析结果对比

## 性能优化建议

根据分析结果，通常可以关注以下几个方面：

1. **I/O瓶颈**: 如果文件读取时间过长，考虑优化I/O操作
2. **图像处理**: 如果图像转换耗时最多，考虑：
   - 调整DPI参数
   - 优化图像处理算法
   - 使用硬件加速
3. **多线程优化**: 分析不同线程数下的性能表现
4. **内存使用**: 监控内存占用，避免内存泄漏

## 故障排除

### 常见问题

1. **ImportError**: 确保已安装所有依赖包
   ```bash
   pip install pypdfium2 pillow loguru numpy
   ```

2. **FileNotFoundError**: 检查PDF文件路径是否正确

3. **权限错误**: 确保对PDF文件有读取权限

4. **内存不足**: 对于大文件，考虑减少页面范围或降低DPI

### 调试模式

在分析过程中遇到问题时，可以查看详细的错误信息：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 扩展功能

你可以基于这个工具进行扩展：

- 添加内存使用监控
- 集成GPU性能分析
- 添加性能回归测试
- 生成性能趋势图表
- 与CI/CD集成进行自动化测试

## 联系方式

如有问题或建议，请通过项目的Issue系统反馈。