@echo off
chcp 65001 >nul
title 复习计划管理系统

cd /d "%~dp0"

echo ==============================
echo   复习计划管理系统
echo ==============================

:: 检查是否有 Python
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo 未找到 Python，请先安装 Python 3.9 或更高版本：
    echo https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

:: 检查 Python 版本
python -c "import sys; exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo Python 版本过低，需要 3.9 或更高版本
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 创建虚拟环境（首次运行）
if not exist ".venv" (
    echo.
    echo 首次运行，正在初始化虚拟环境...
    python -m venv .venv
    echo 虚拟环境创建完成
)

:: 安装 / 更新依赖
echo 正在检查依赖...
.venv\Scripts\pip install -q --upgrade pip
.venv\Scripts\pip install -q -r requirements.txt
echo 依赖检查完成

:: 初始化数据库
.venv\Scripts\python -c "import sys; sys.path.insert(0,'.'); from lesson_manager import init_db; init_db()" 2>nul

echo.
echo 系统启动中，浏览器即将打开...
echo 关闭此窗口可停止服务
echo ==============================
echo.

:: 延迟打开浏览器
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"

:: 启动 Flask
.venv\Scripts\python app.py
