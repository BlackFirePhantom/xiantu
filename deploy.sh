#!/bin/bash
# 暗域传说 - 一键部署脚本
# 适用于 Ubuntu/Debian 服务器 (2核1G)

set -e

echo "=============================="
echo "  暗域传说 - 文字在线RPG部署"
echo "=============================="

# 检测并安装 Python3
if ! command -v python3 &> /dev/null; then
    echo "[*] 安装 Python3..."
    apt-get update -qq
    apt-get install -y python3 python3-pip python3-venv
fi

# 创建虚拟环境
echo "[*] 创建 Python 虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 安装依赖
echo "[*] 安装依赖..."
pip install -r requirements.txt

echo ""
echo "[OK] 部署完成！"
echo ""
echo "启动方式："
echo "  source venv/bin/activate"
echo "  python app.py"
echo ""
echo "然后访问: http://你的服务器IP:5000"
echo ""
echo "后台运行："
echo "  nohup python app.py > game.log 2>&1 &"
echo ""
