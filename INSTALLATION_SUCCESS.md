# MinerU 安装和Demo运行成功总结

## 安装过程总结

### 1. 环境检查
- ✅ Python 3.13.9
- ✅ pip 25.2
- ✅ 使用 conda 环境

### 2. 从源码安装
- ✅ 安装 uv 包管理器
- ✅ 使用 `uv pip install -e .[core] --system` 安装成功
- ✅ 安装了所有必要的依赖包（包括torch, transformers等）

### 3. 模型下载
- ✅ 使用 `mineru-models-download` 下载所有模型
- ✅ 下载了pipeline和VLM模型
- ✅ 模型存储在 `/home/ubuntu/.cache/huggingface/hub/`

### 4. Demo运行成功
- ✅ 命令行方式：`mineru -p demo/pdfs/demo1.pdf -o output_demo`
- ✅ Python API方式：通过 `demo/demo.py` 中的 `parse_doc` 函数
- ✅ 成功处理PDF文档并生成Markdown格式输出

## 生成的输出文件

每个处理的PDF会生成以下文件：
- `{filename}.md` - Markdown格式的文档内容
- `{filename}_content_list.json` - 内容列表（结构化数据）
- `{filename}_middle.json` - 中间处理结果
- `{filename}_model.json` - 模型输出
- `{filename}_layout.pdf` - 布局可视化
- `{filename}_span.pdf` - 跨度可视化
- `{filename}_origin.pdf` - 原始PDF
- `images/` - 提取的图片文件夹

## 功能验证

✅ **文本提取**：成功提取PDF中的文本内容
✅ **公式识别**：数学公式转换为LaTeX格式
✅ **表格处理**：表格内容正确识别和转换
✅ **图片提取**：PDF中的图片被提取并保存
✅ **结构保持**：文档的层次结构（标题、段落等）得以保持
✅ **多语言支持**：支持中英文混合文档

## 使用示例

### 命令行使用
```bash
mineru -p input.pdf -o output_directory
```

### Python API使用
```python
from demo.demo import parse_doc
from pathlib import Path

# 处理PDF
parse_doc(
    path_list=[Path("input.pdf")],
    output_dir=Path("output"),
    lang="ch",  # 中文
    backend="pipeline",  # 使用pipeline后端
    method="auto"  # 自动选择处理方法
)
```

## 安装完成

MinerU已成功从源码安装并验证可用！🎉