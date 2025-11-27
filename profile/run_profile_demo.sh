#!/bin/bash

# MinerU PDF解析性能分析演示脚本

echo "🎯 MinerU PDF解析性能分析演示"
echo "======================================="

# 检查Python环境
echo "📋 检查Python环境..."
python3 --version
echo ""

# 检查依赖包
echo "📋 检查关键依赖包..."
python3 -c "
import sys
required_packages = ['pypdfium2', 'PIL', 'numpy', 'loguru']
missing = []
for pkg in required_packages:
    try:
        __import__(pkg)
        print(f'✅ {pkg}')
    except ImportError:
        print(f'❌ {pkg}')
        missing.append(pkg)

if missing:
    print(f'\\n❌ 缺少依赖包: {missing}')
    print('请安装: pip install ' + ' '.join(missing))
    sys.exit(1)
else:
    print('\\n✅ 所有依赖包已安装')
"
echo ""

# 设置权限
echo "📋 设置脚本权限..."
chmod +x pdf_profile_demo.py
chmod +x simple_test.py
echo "✅ 权限设置完成"
echo ""

# 创建输出目录
echo "📋 创建输出目录..."
mkdir -p profile_outputs
echo "✅ 输出目录已创建: profile_outputs/"
echo ""

# 显示使用方法
echo "🚀 使用方法演示:"
echo "======================================="

echo ""
echo "1️⃣ 详细性能分析 (推荐):"
echo "   python pdf_profile_demo.py <pdf文件路径>"
echo ""
echo "   示例:"
echo "   python pdf_profile_demo.py /path/to/your/sample.pdf"
echo "   python pdf_profile_demo.py file1.pdf file2.pdf file3.pdf"
echo ""

echo "2️⃣ 快速性能测试:"
echo "   python simple_test.py <pdf文件路径>"
echo ""
echo "   示例:"
echo "   python simple_test.py /path/to/your/sample.pdf"
echo ""
echo "   进行DPI性能对比:"
echo "   python simple_test.py /path/to/your/sample.pdf --dpi-compare"
echo ""

echo "3️⃣ 批量测试示例:"
echo ""
echo "# 测试单个文件的不同配置"
echo "python pdf_profile_demo.py your_file.pdf"
echo ""
echo "# 测试多个文件"
echo "python pdf_profile_demo.py file1.pdf file2.pdf file3.pdf"
echo ""
echo "# 快速测试 + DPI对比"
echo "python simple_test.py your_file.pdf --dpi-compare"
echo ""

echo "4️⃣ 查看结果:"
echo "   详细报告: profile_outputs/*.txt"
echo "   性能数据: profile_outputs/*.prof"
echo ""

# 提示用户开始测试
echo "💡 提示:"
echo "   - 建议先用 simple_test.py 进行快速测试"
echo "   - 使用 pdf_profile_demo.py 获得详细的函数级性能分析"
echo "   - 可以通过修改脚本中的 dpi, threads 参数测试不同配置"
echo ""
echo "📁 输出文件将保存在 profile_outputs/ 目录中"
echo ""

# 询问是否要进行测试
read -p "是否要进行测试? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "请提供PDF文件路径进行测试:"
    read -p "PDF文件路径: " pdf_path

    if [ -f "$pdf_path" ]; then
        echo ""
        echo "🚀 开始快速测试..."
        python simple_test.py "$pdf_path"

        echo ""
        read -p "是否要进行详细的性能分析? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "🔬 开始详细性能分析..."
            python pdf_profile_demo.py "$pdf_path"
        fi
    else
        echo "❌ 文件不存在: $pdf_path"
    fi
fi

echo ""
echo "✅ 演示完成!"
echo "如有问题，请查看 README.md 文件获取详细说明。"