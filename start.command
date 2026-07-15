#!/bin/bash
# 复习计划管理系统 — macOS 后端快捷启动器
# 双击此文件即可准备依赖并启动后端；前端仍需单独运行

# 进入脚本所在目录
cd "$(dirname "$0")"

echo "=============================="
echo "  📚 复习计划管理系统"
echo "=============================="

# 检查 Python 3.12
PYTHON_BIN="${XR_PYTHON_BIN:-python3}"

python_version() {
    "$1" --version 2>&1 | sed 's/^Python //'
}

if ! command -v "$PYTHON_BIN" &>/dev/null; then
    echo ""
    echo "未找到 Python: $PYTHON_BIN"
    echo "请安装 Python 3.12, 或用 XR_PYTHON_BIN 指定 Python 3.12 可执行文件:"
    echo "https://www.python.org/downloads/"
    echo ""
    read -p "按回车键退出..."
    exit 1
fi

if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))'; then
    echo "Python 3.12.x is required. Current interpreter: Python $(python_version "$PYTHON_BIN")"
    echo "请安装 Python 3.12, 或用 XR_PYTHON_BIN 指定正确的解释器."
    read -p "按回车键退出..."
    exit 1
fi

if [ -d ".venv" ]; then
    if [ ! -x ".venv/bin/python" ]; then
        echo "现有 .venv 缺少可执行的 Python 解释器. 请删除 .venv 后重试."
        read -p "按回车键退出..."
        exit 1
    fi
    if ! .venv/bin/python -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))'; then
        echo "Existing .venv uses Python $(python_version .venv/bin/python); Python 3.12.x is required."
        echo "请删除 .venv, 再使用 Python 3.12 重新运行."
        read -p "按回车键退出..."
        exit 1
    fi
fi

# 创建虚拟环境（首次运行）
if [ ! -d ".venv" ]; then
    echo ""
    echo "首次运行，正在初始化虚拟环境..."
    "$PYTHON_BIN" -m venv .venv
    if ! .venv/bin/python -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))'; then
        echo "新建的 .venv 不是 Python 3.12.x. 请删除 .venv 并检查 XR_PYTHON_BIN."
        read -p "按回车键退出..."
        exit 1
    fi
    echo "✅ 虚拟环境创建完成"
fi

# 安装 / 更新依赖
echo "正在检查依赖..."
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt
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
echo "此脚本仅启动后端 API：http://127.0.0.1:5001"
echo "前端需要单独启动：http://127.0.0.1:3000"
echo "3000 才是开发态页面入口；如前端未启动，请不要直接打开 5001"
echo ""
echo "关闭此窗口或按 Ctrl+C 可停止服务"
echo "=============================="
echo ""

# 启动后端（默认不自动打开浏览器，避免把用户带到错误入口）
XR_OPEN_BROWSER=0 ./scripts/run_backend.sh
