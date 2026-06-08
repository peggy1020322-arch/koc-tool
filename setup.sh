#!/bin/bash
echo "=============================="
echo " 美顏相機 KOC 工具 安裝中..."
echo "=============================="

# 安裝 Python 套件
echo ""
echo "▶ 安裝必要套件..."
pip3 install -r requirements.txt

# 安裝 Playwright 瀏覽器
echo ""
echo "▶ 安裝瀏覽器..."
python3 -m playwright install chromium

echo ""
echo "=============================="
echo " 安裝完成！啟動工具中..."
echo "=============================="
echo ""
echo " 開啟瀏覽器前往：http://127.0.0.1:5001"
echo ""

# 啟動工具
python3 app.py
