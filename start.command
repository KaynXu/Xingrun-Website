#!/bin/bash
# 复习计划管理系统 — macOS 启动器
# 双击此文件即可启动，首次运行会自动安装依赖（约 1-2 分钟）

# 进入脚本所在目录
cd "$(dirname "$0")"

echo "=============================="
echo "  📚 复习计划管理系统"
echo "=============================="

# 检查 Python3
if ! command -v python3 &>/dev/null; then
    echo ""
    echo "❌ 未找到 Python3"
    echo "请先安装 Python 3.9 或更高版本："
    echo "https://www.python.org/downloads/"
    echo ""
    read -p "按回车键退出..."
    exit 1
fi

PYTHON_VER=$(python3 -c "import sys; print(sys.version_info.major*10+sys.version_info.minor)")
if [ "$PYTHON_VER" -lt 39 ]; then
    echo "❌ Python 版本过低（需要 3.9+，当前 $(python3 --version)）"
    echo "请升级 Python：https://www.python.org/downloads/"
    read -p "按回车键退出..."
    exit 1
fi

# 创建虚拟环境（首次运行）
if [ ! -d ".venv" ]; then
    echo ""
    echo "首次运行，正在初始化虚拟环境..."
    python3 -m venv .venv
    echo "✅ 虚拟环境创建完成"
fi

# 安装 / 更新依赖
echo "正在检查依赖..."
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
echo "✅ 依赖检查完成"

# 初始化数据库
.venv/bin/python -c "
import sys
sys.path.insert(0, '.')
from lesson_manager import init_db
init_db()
" 2>/dev/null

echo ""
echo "✅ 系统启动中..."
echo "浏览器即将自动打开 http://127.0.0.1:5000"
echo ""
echo "关闭此窗口或按 Ctrl+C 可停止服务"
echo "=============================="
echo ""

# 延迟打开浏览器
(sleep 2 && open "http://127.0.0.1:5000") &

# 启动 Flask
.venv/bin/python app.py
