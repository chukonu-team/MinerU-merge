#!/bin/bash

# MinerU PDF解析性能分析工具 - 虚拟环境运行脚本

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv_profile"

# 检查虚拟环境是否存在
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ 虚拟环境不存在，请先运行: ./install_dependencies.sh"
    exit 1
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source "$VENV_DIR/bin/activate"

# 检查是否有参数
if [ $# -eq 0 ]; then
    echo "🎯 MinerU PDF解析性能分析工具"
    echo "=================================="
    echo ""
    echo "用法:"
    echo "  1. 分析单个PDF文件:"
    echo "     $0 <pdf文件路径> [工具选项]"
    echo ""
    echo "  2. 批量分析PDF目录:"
    echo "     $0 --directory <pdf目录> [选项]"
    echo ""
    echo "  3. 分析多个PDF文件:"
    echo "     $0 file1.pdf file2.pdf file3.pdf [工具选项]"
    echo ""
    echo "工具选项:"
    echo "  --demo              运行详细性能分析"
    echo "  --simple            运行快速测试（默认）"
    echo "  --dpi-compare       进行DPI性能对比"
    echo "  --dpi-list <list>   自定义DPI列表，如 \"150,200,300\""
    echo "  --max-files <num>   限制处理文件数"
    echo "  --help              显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 /path/to/sample.pdf --demo"
    echo "  $0 --directory /path/to/pdfs/ --max-files 10"
    echo "  $0 --directory /path/to/pdfs/ --dpi-compare"
    echo "  $0 --directory /path/to/pdfs/ --dpi-list \"150,200,300\""
    echo "  $0 file1.pdf file2.pdf --simple"
    echo ""
    echo "如果没有安装依赖，请先运行: ./install_dependencies.sh"
    exit 0
fi

# 检查是否为目录模式
if [ "$1" = "--directory" ]; then
    if [ $# -lt 2 ]; then
        echo "❌ --directory 需要指定目录路径"
        exit 1
    fi

    PDF_DIR="$2"
    TOOL_OPTION="${3:---simple}"

    # 解析其他选项
    MAX_FILES=""
    DPI_COMPARE=false
    DPI_LIST="200"

    shift 2

    while [ $# -gt 0 ]; do
        case "$1" in
            --max-files)
                if [ $# -lt 2 ]; then
                    echo "❌ --max-files 需要指定文件数量"
                    exit 1
                fi
                MAX_FILES="$2"
                shift 2
                ;;
            --dpi-compare)
                DPI_COMPARE=true
                shift 1
                ;;
            --dpi-list)
                if [ $# -lt 2 ]; then
                    echo "❌ --dpi-list 需要指定DPI列表"
                    exit 1
                fi
                DPI_LIST="$2"
                shift 2
                ;;
            --demo)
                TOOL_OPTION="--demo"
                shift 1
                ;;
            --simple)
                TOOL_OPTION="--simple"
                shift 1
                ;;
            *)
                shift 1
                ;;
        esac
    done

    # 检查目录是否存在
    if [ ! -d "$PDF_DIR" ]; then
        echo "❌ PDF目录不存在: $PDF_DIR"
        exit 1
    fi

    echo "📁 批量分析PDF目录: $PDF_DIR"
    echo "🔧 工具选项: $TOOL_OPTION"
    if [ -n "$MAX_FILES" ]; then
        echo "🔢 限制文件数: $MAX_FILES"
    fi
    if [ "$DPI_COMPARE" = true ]; then
        echo "🎯 DPI对比: 150,200,300"
    elif [ "$DPI_LIST" != "200" ]; then
        echo "🎯 DPI列表: $DPI_LIST"
    fi
    echo "=================================="

    # 根据选项运行不同的工具
    case "$TOOL_OPTION" in
        --demo)
            if [ "$DPI_COMPARE" = true ]; then
                echo "🔬 批量详细性能分析 + DPI对比..."
                python "$SCRIPT_DIR/pdf_profile_demo.py" --directory "$PDF_DIR" --max-files $MAX_FILES
            elif [ "$DPI_LIST" != "200" ]; then
                echo "🔬 批量详细性能分析 + 自定义DPI..."
                python "$SCRIPT_DIR/pdf_profile_demo.py" --directory "$PDF_DIR" --max-files $MAX_FILES
            else
                echo "🔬 批量详细性能分析..."
                python "$SCRIPT_DIR/pdf_profile_demo.py" --directory "$PDF_DIR" --max-files $MAX_FILES
            fi
            ;;
        --simple)
            if [ "$DPI_COMPARE" = true ]; then
                echo "⚡ 批量快速测试 + DPI对比..."
                python "$SCRIPT_DIR/simple_test.py" --directory "$PDF_DIR" --dpi-compare --max-files $MAX_FILES
            elif [ "$DPI_LIST" != "200" ]; then
                echo "⚡ 批量快速测试 + 自定义DPI..."
                python "$SCRIPT_DIR/simple_test.py" --directory "$PDF_DIR" --dpi-list "$DPI_LIST" --max-files $MAX_FILES
            else
                echo "⚡ 批量快速测试..."
                python "$SCRIPT_DIR/simple_test.py" --directory "$PDF_DIR" --max-files $MAX_FILES
            fi
            ;;
        *)
            echo "❌ 未知选项: $TOOL_OPTION"
            echo "使用 --help 查看可用选项"
            exit 1
            ;;
    esac

    exit 0
fi

# 单文件模式
PDF_FILE="$1"
TOOL_OPTION="${2:---simple}"

# 检查PDF文件是否存在
if [ ! -f "$PDF_FILE" ]; then
    echo "❌ PDF文件不存在: $PDF_FILE"
    exit 1
fi

echo "📄 分析PDF文件: $PDF_FILE"
echo "🔧 工具选项: $TOOL_OPTION"
echo "=================================="

# 根据选项运行不同的工具
case "$TOOL_OPTION" in
    --demo)
        echo "🔬 运行详细性能分析..."
        python "$SCRIPT_DIR/pdf_profile_demo.py" "$PDF_FILE"
        ;;
    --simple)
        echo "⚡ 运行快速性能测试..."
        python "$SCRIPT_DIR/simple_test.py" "$PDF_FILE"
        ;;
    --dpi-compare)
        echo "🎯 运行DPI性能对比..."
        python "$SCRIPT_DIR/simple_test.py" "$PDF_FILE" --dpi-compare
        ;;
    --help)
        echo "📖 帮助信息:"
        echo ""
        echo "  --demo      : 使用 pdf_profile_demo.py 进行详细的cProfile分析"
        echo "  --simple    : 使用 simple_test.py 进行快速性能测试"
        echo "  --dpi-compare : 对比不同DPI设置下的性能表现"
        echo "  --help      : 显示此帮助信息"
        echo ""
        echo "输出文件将保存在 $SCRIPT_DIR/profile_outputs/ 目录中"
        ;;
    *)
        echo "❌ 未知选项: $TOOL_OPTION"
        echo "使用 --help 查看可用选项"
        exit 1
        ;;
esac

echo ""
echo "✅ 分析完成！"
echo "📁 详细结果保存在: $SCRIPT_DIR/profile_outputs/"