#!/bin/bash
cd "$(dirname "$0")"
python scripts/app.py &
sleep 2
if command -v xdg-open &> /dev/null; then
    xdg-open http://127.0.0.1:8866
elif command -v open &> /dev/null; then
    open http://127.0.0.1:8866
fi
echo "DeepRunner 报告生成器已启动"
echo "访问地址: http://127.0.0.1:8866"
