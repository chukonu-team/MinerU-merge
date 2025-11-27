# MinerU PDF性能分析工具 - 使用示例

## 🎯 现状总结

✅ **已完成功能**:
- 支持单文件PDF分析
- 支持整个PDF目录批量处理
- 支持DPI性能对比 (150/200/300)
- 支持自定义DPI列表
- 支持处理文件数量限制
- 支持快速测试和详细分析
- 生成详细的汇总报告

## 🚀 使用示例

### 1. 快速开始
```bash
cd /home/ubuntu/MinerU-merge/profile
./install_dependencies.sh
```

### 2. 单文件分析
```bash
# 快速测试单个文件
./run_with_venv.sh /path/to/sample.pdf --simple

# 详细性能分析
./run_with_venv.sh /path/to/sample.pdf --demo

# DPI性能对比
./run_with_venv.sh /path/to/sample.pdf --dpi-compare
```

### 3. 批量目录分析（推荐）

#### 快速批量分析
```bash
# 分析整个目录
./run_with_venv.sh --directory /path/to/pdfs/ --simple

# 限制处理文件数
./run_with_venv.sh --directory /path/to/pdfs/ --max-files 10 --simple
```

#### 详细批量分析
```bash
# 分析整个目录并生成详细报告
./run_with_venv.sh --directory /path/to/pdfs/ --demo

# 限制文件数并详细分析
./run_with_venv.sh --directory /path/to/pdfs/ --max-files 5 --demo
```

#### DPI性能对比（批量）
```bash
# 自动DPI对比（150/200/300）
./run_with_venv.sh --directory /path/to/pdfs/ --dpi-compare

# 自定义DPI对比
./run_with_venv.sh --directory /path/to/pdfs/ --dpi-list "150,200,300,400"
```

#### 组合选项
```bash
# 自定义DPI对比并限制文件数
./run_with_venv.sh --directory /path/to/pdfs/ --dpi-list "150,200" --max-files 20

# 快速分析并限制文件数
./run_with_venv.sh --directory /path/to/pdfs/ --max-files 10 --simple
```

### 4. 直接使用Python工具

#### 激活虚拟环境
```bash
source venv_profile/bin/activate
```

#### 使用快速批量工具
```python
# 批量快速测试
python batch_analyzer.py /path/to/pdfs/

# 限制文件数
python batch_analyzer.py /path/to/pdfs/ --max-files 10

# 自定义DPI
python batch_analyzer.py /path/to/pdfs/ --dpi 150
```

#### 使用详细分析工具
```python
# 批量详细分析
python pdf_profile_demo.py --directory /path/to/pdfs/

# 结合选项使用
python pdf_profile_demo.py --directory /path/to/pdfs/ --max-files 5
```

### 5. 实际测试结果示例

#### 测试结果示例（批量分析）
```
📈 批量测试汇总 - 目录: /path/to/pdfs/
================================================================================
📊 总体统计:
   处理文件数: 4
   总页数: 37
   总文件大小: 2.89 MB
   平均处理速度: 17.73 页/秒
   总处理时间: 1.656s

📈 平均指标:
   平均文件大小: 0.72 MB
   平均每文件页数: 9.2
   平均每文件耗时: 0.545s
   平均处理速度: 17.73 页/秒
   平均处理吞吐量: 1.75 MB/s

🏆 性能极值:
   🚀 最快文件: demo1.pdf (37.68 页/秒)
   🐌 最慢文件: demo2.pdf (10.77 页/秒)

📁 批量分析汇总:
   处理文件数: 4
   总页数: 37
   总文件大小: 2.89 MB
   平均处理速度: 17.73 页/秒
   分析耗时: 1.656s
   📊 汇总报告已保存: ./profile_outputs/batch_summary_1764227030.txt
```

#### 测试结果示例（DPI对比）
```
🎯 DPI性能对比 - 目录: /path/to/pdfs/
DPI 100: 平均处理速度: 73.2 页/秒
DPI 150: 平均处理速度: 71.9 页/秒
DPI 200: 平均处理速度: 31.3 页/秒

🎯 性能对比结论:
- ✅ DPI越高，处理速度越慢
- ✅ 建议使用150-200 DPI进行平衡
- ✅ 对于大文件，可考虑100 DPI以提高效率
```

## 💡 使用建议

### 性能分析工作流程
1. **快速评估** → 使用 `--simple` 模式快速了解整体水平
2. **详细分析** → 使用 `--demo` 模式识别具体瓶颈
3. **DPI对比** → 使用 `--dpi-compare` 找到最优参数
4. **基准建立** → 使用 `--max-files` 建立性能基线
5. **持续监控** → 定期运行分析进行回归测试

### 常见问题解决

#### 内存不足错误
```bash
# 减少并发文件数
./run_with_venv.sh --directory ./files/ --max-files 5

# 降低DPI设置
python batch_analyzer.py /path/to/files/ --dpi 150
```

#### 性能分析结果不可靠
```bash
# 增加处理文件数量
./run_with_venv.sh --directory ./files/ --max-files 50

# 专注于大型文件
find ./files/ -name "*.pdf" -size +5M
```

### 最佳实践

1. **从小规模开始**：先测试少量文件，验证工具正确性
2. **逐步扩大规模**：确认工具稳定后，增加处理文件数量
3. **参数组合测试**：测试不同DPI、线程数组合
4. **定期回归测试**：建立性能基线，监控代码变更影响
5. **记录和比较**：保存分析报告，便于长期趋势分析

---

**🎉 现在您的MinerU PDF性能分析工具已经完全就绪，可以有效地进行批量性能分析！**