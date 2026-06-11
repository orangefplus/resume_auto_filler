@echo off
REM 启动简历自动填写助手后端
setlocal

cd /d "%~dp0"

if not exist "config.yml" (
    echo [WARN] config.yml 不存在，将从 config.yml.example 复制...
    copy /Y "config.yml.example" "config.yml" >nul
    echo [WARN] 请编辑 config.yml 填入 dashscope_api_key
    pause
    exit /b 1
)

REM 激活项目 venv（如果存在）
if exist "..\\.venv\\Scripts\\activate.bat" (
    call "..\\.venv\\Scripts\\activate.bat"
)

echo ============================================
echo  简历自动填写助手 - 后端启动
echo  地址: http://127.0.0.1:8765
echo  按 Ctrl+C 停止
echo ============================================

python -m backend.main

pause
