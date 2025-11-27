#!/bin/bash

# PDF解析性能分析工具依赖安装脚本

echo "🚀 安装MinerU PDF解析性能分析工具依赖"
echo "=========================================="

# 检查Python版本
echo "📋 检查Python版本..."
python3 --version

if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装，请先安装Python3"
    exit 1
fi

# 检查pip
echo ""
echo "📋 检查pip..."
python3 -m pip --version

if ! command -v python3 -m pip &> /dev/null; then
    echo "❌ pip 未安装，请先安装pip"
    echo "   Ubuntu/Debian: sudo apt-get install python3-pip"
    echo "   CentOS/RHEL: sudo yum install python3-pip"
    exit 1
fi

# 升级pip
echo ""
echo "📋 升级pip..."
python3 -m pip install --upgrade pip

# 安装依赖包
echo ""
echo "📦 安装依赖包..."
echo "这可能需要几分钟时间..."

# 创建虚拟环境
VENV_DIR="venv_profile"
if [ ! -d "$VENV_DIR" ]; then
    echo "🔧 创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
    echo "✅ 虚拟环境创建完成: $VENV_DIR"
else
    echo "✅ 虚拟环境已存在: $VENV_DIR"
fi

# 激活虚拟环境并安装依赖
echo "🔧 激活虚拟环境并安装依赖..."
source "$VENV_DIR/bin/activate"

if [ -f "requirements.txt" ]; then
    echo "从 requirements.txt 安装..."
    pip install -r requirements.txt
else
    echo "requirements.txt 不存在，手动安装核心依赖..."
    pip install pypdfium2 Pillow numpy loguru
fi

# 验证安装
echo ""
echo "🔍 验证安装..."
source "$VENV_DIR/bin/activate"
python -c "
import sys

# 检查核心依赖
packages = [
    ('pypdfium2', 'PDF处理'),
    ('PIL', '图像处理'),
    ('numpy', '数值计算'),
    ('loguru', '日志记录')
]

success_count = 0
for package, description in packages:
    try:
        if package == 'PIL':
            import PIL
        else:
            __import__(package)
        print(f'✅ {package} ({description}) - 安装成功')
        success_count += 1
    except ImportError as e:
        print(f'❌ {package} ({description}) - 安装失败: {e}')

print(f'\\n📊 安装结果: {success_count}/{len(packages)} 成功')

if success_count == len(packages):
    print('🎉 所有依赖包安装成功！')
else:
    print('⚠️  部分依赖包安装失败，可能影响工具使用')
    print('   请手动安装失败的包')
"

# 测试MinerU导入
echo ""
echo "🧪 测试MinerU模块导入..."
source "$VENV_DIR/bin/activate"
python -c "
import sys
import os

# 添加项目路径
project_path = os.path.dirname(os.path.abspath('.'))
sys.path.insert(0, project_path)

try:
    from mineru.utils.pdf_image_tools import load_images_from_pdf
    print('✅ MinerU load_images_from_pdf 导入成功')
except ImportError as e:
    print(f'❌ MinerU模块导入失败: {e}')
    print('   请确保在MinerU项目根目录下运行此脚本')
"

echo ""
echo "✅ 依赖安装完成！"
echo ""
echo "🚀 现在可以使用性能分析工具了:"
echo "   # 激活虚拟环境"
echo "   source $VENV_DIR/bin/activate"
echo ""
echo "   # 使用分析工具"
echo "   python pdf_profile_demo.py <pdf文件>"
echo "   python simple_test.py <pdf文件>"
echo ""
echo "   # 或者直接使用（会自动激活虚拟环境）"
echo "   ./run_with_venv.sh <pdf文件>"
echo ""
echo "📖 更多信息请查看 README.md"