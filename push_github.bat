@echo off
REM ====================================================================
REM  推送到 GitHub 的辅助脚本
REM  使用前：在 https://github.com/new 手动创建一个名为
REM          "resume_auto_filler" 的空仓库（不要勾选 README/license）
REM  然后双击运行本脚本
REM ====================================================================
setlocal

cd /d "%~dp0"

echo.
echo ===============================================
echo  简历自动填写助手 - GitHub 推送脚本
echo ===============================================
echo.

REM 检查是否已有 remote
git remote get-url origin >nul 2>&1
if %errorlevel% == 0 (
    echo [INFO] remote 'origin' 已存在：
    git remote get-url origin
    echo.
    set /p CONFIRM=继续推送到现有 origin 吗？(Y/N)：
    if /I not "%CONFIRM%"=="Y" (
        echo 已取消。
        pause
        exit /b 0
    )
) else (
    echo [STEP 1] 添加 GitHub remote
    set /p REPO_URL=请输入仓库 URL（默认 https://github.com/wangxin/resume_auto_filler.git）：
    if "%REPO_URL%"=="" set REPO_URL=https://github.com/orangefplus/resume_auto_filler.git
    git remote add origin "%REPO_URL%"
    echo [OK] 已添加 origin = %REPO_URL%
)

echo.
echo [STEP 2] 推送 main 分支
git push -u origin master:main

if %errorlevel% == 0 (
    echo.
    echo ===============================================
    echo  推送成功！
    echo  访问 https://github.com/orangefplus/resume_auto_filler 查看
    echo ===============================================
) else (
    echo.
    echo [ERROR] 推送失败。请检查：
    echo  1. 仓库 https://github.com/orangefplus/resume_auto_filler 是否已创建
    echo  2. 你的 GitHub 账号是否有写权限
    echo  3. 网络是否可达 github.com
    echo.
    echo 也可以手动运行：
    echo   git push -u origin master:main
)

echo.
pause
