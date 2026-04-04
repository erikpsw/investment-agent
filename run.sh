#!/bin/bash
# 启动 Investment Agent Web 应用

cd "$(dirname "$0")/.."
export PYTHONPATH="$(pwd)"
python3 -m streamlit run investment/app.py --server.port ${PORT:-8501} --browser.gatherUsageStats false
