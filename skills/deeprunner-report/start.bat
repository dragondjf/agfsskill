@echo off
chcp 65001 >nul
cd /d "%~dp0"
start /B python scripts\app.py
ping -n 3 127.0.0.1 >nul
start http://127.0.0.1:8866
echo.
echo DeepRunner 报告生成器已启动
echo 访问地址: http://127.0.0.1:8866
echo.
pause
