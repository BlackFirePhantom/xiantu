# 仙途 — 修仙文字在线游戏

> 逆天修仙，证道长生。一款轻量级多人在线修仙文字 RPG，适合 2 核 1G 服务器部署。

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-SocketIO-green?logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-WAL-yellow?logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-brightgreen)

---

## 游戏简介

你是一名初入仙途的修士，从青云镇出发，历经落霞林、妖兽密林、苍云山、天劫峰等九大险地，斩妖除魔、修炼功法、锻造法宝，最终渡劫飞升。

游戏以 **修仙境界** 为核心成长线，融合 **奇遇剧情、炼丹炼器、五行相克、功法经脉** 等系统，支持多人在线实时互动。

---

## 核心系统

| 系统 | 说明 |
|------|------|
| **境界修炼** | 练气 → 筑基 → 结丹 → 元婴 → 化神 → 炼虚 → 合体 → 大乘，共 15 级，突破有失败风险 |
| **灵根系统** | 创建角色随机获得灵根（废灵根/灵根/五行灵根/天灵根/混沌灵根），影响修炼速度和五行相克 |
| **奇遇事件** | 20 个小说级剧情事件（崖底奇缘、古修士洞府、心魔幻境、飞剑残魂等），有选择分支 |
| **突发事件** | 16 个战斗/移动突发事件（妖兽伏击、天雷降世、灵气潮汐等），直接生效 |
| **炼丹系统** | 8 个丹药配方，收集灵草炼制（回气丹、培元丹、破境丹、九转还魂丹等） |
| **炼器锻造** | 18 个锻造配方（凡器→神器），每次锻造随机生成前缀+材料+后缀组合，属性各不相同 |
| **功法系统** | 10 本功法（黄阶→天阶），消耗灵石参悟，永久加气血/攻击/防御/修炼速度 |
| **经脉修炼** | 8 条经脉（任脉→阳跷脉），消耗修为打通，永久加属性 |
| **五行相克** | 金克木→木克土→土克水→水克火→火克金，攻击+30%/-20% |
| **放置修炼** | 离线自动积累修为 + 在线 10 分钟无操作自动进入挂机模式，最多 24 小时 |
| **多人互动** | 实时聊天、天骄榜、在线人数、其他玩家动态 |

---

## 游戏截图

| 登录 | 游戏主界面 | 炼器锻造 |
|------|-----------|---------|
| ![登录](screenshots/login.png) | ![游戏](screenshots/game.png) | ![炼器](screenshots/forge.png) |

> 截图待补充，部署后访问即可体验。

---

## 快速部署

### 方式一：Docker（推荐）

```bash
git clone https://github.com/BlackFirePhantom/xiantu.git
cd xiantu
docker-compose up -d --build
```

访问 `http://你的服务器IP:8500`

### 方式二：直接运行

```bash
git clone https://github.com/BlackFirePhantom/xiantu.git
cd xiantu
pip install -r requirements.txt
python app.py
```

访问 `http://localhost:5000`

### 方式三：服务器 systemd 常驻

```bash
git clone https://github.com/BlackFirePhantom/xiantu.git /opt/xiantu
cd /opt/xiantu
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 创建 systemd 服务
cat > /etc/systemd/system/xiantu.service << 'EOF'
[Unit]
Description=Xiantu Game Server
After=network.target

[Service]
WorkingDirectory=/opt/xiantu
ExecStart=/opt/xiantu/venv/bin/python app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now xiantu
```

---

## 项目结构

```
xiantu/
├── app.py                 # Flask + SocketIO 主程序（路由 + 事件处理）
├── config.py              # 配置管理（环境变量、密钥、端口）
├── models.py              # SQLite 数据库模型（含版本化迁移）
├── game_data.py           # 游戏数据（境界、灵根、功法、经脉、物品、妖兽、地点、炼器）
├── events.py              # 事件数据（20个奇遇 + 16个突发事件，小说级文案）
├── npc_data.py            # NPC 数据（7个NPC、19个任务、宗门系统）
├── game/                  # 游戏逻辑层（纯业务逻辑，无Flask依赖）
│   ├── utils.py           # 工具函数（属性计算、熟练度、修炼倍率）
│   ├── combat.py          # 战斗系统
│   ├── cultivation.py     # 修炼/突破/挂机系统
│   ├── crafting.py        # 炼丹 + 炼器锻造
│   ├── pet.py             # 灵宠系统
│   ├── treasure.py        # 藏宝图 + 残卷合成
│   ├── npc.py             # NPC 交互 + 任务系统
│   ├── events.py          # 奇遇/突发事件处理
│   └── auction.py         # 拍卖行系统
├── tests/                 # 单元测试
│   ├── test_utils.py
│   ├── test_cultivation.py
│   ├── test_pet.py
│   └── test_npc.py
├── templates/
│   ├── index.html         # 登录/注册/创建角色页
│   └── game.html          # 游戏主界面
├── static/
│   ├── css/style.css      # 暗绿修仙主题样式
│   └── js/game.js         # 前端交互逻辑
├── requirements.txt       # Python 依赖
├── Dockerfile             # Docker 镜像（含健康检查）
├── docker-compose.yml     # Docker Compose（支持环境变量配置）
├── backup.sh              # 数据库备份脚本
├── .env.example           # 环境变量配置示例
└── .gitignore
```

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端 | Flask + Flask-SocketIO | WebSocket 实时通信 |
| 数据库 | SQLite (WAL 模式) | 零配置，轻量，适合小规模部署 |
| 异步 | Threading | 线程式并发 |
| 前端 | 原生 HTML/CSS/JS | 无框架依赖，加载快 |
| 部署 | Docker / systemd | 一键部署，自动重启 |
| 测试 | pytest | 单元测试覆盖核心逻辑 |

---

## 资源占用

| 指标 | 数值 |
|------|------|
| 内存 | ~50MB |
| CPU | 几乎无负载（仅请求时消耗） |
| 磁盘 | < 10MB（SQLite 数据库随使用增长） |
| 并发 | 支持 50+ 同时在线 |
| 启动时间 | < 2 秒 |

---

## 自定义修改

### 环境变量配置

复制 `.env.example` 为 `.env`，可配置以下选项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `XIANTU_SECRET_KEY` | 服务器密钥（不设置则自动生成并持久化） | 自动生成 |
| `XIANTU_CORS` | CORS 允许的来源 | `*` |
| `XIANTU_PORT` | 服务器端口 | `5000` |
| `XIANTU_HOST` | 监听地址 | `0.0.0.0` |

### 数据库备份

```bash
# 备份数据库（保存到 backups/ 目录，自动清理 30 天前的备份）
./backup.sh
```

### 修改端口

编辑 `docker-compose.yml`：

```yaml
ports:
  - "你想用的端口:5000"   # 冒号左边改外部端口，右边不动
```

### 修改游戏数据

- **新增怪物/地点/物品**：编辑 `game_data.py`
- **新增事件**：编辑 `events.py`
- **修改境界/经验**：编辑 `game_data.py` 中的 `EXP_PER_LEVEL` 和 `REALMS`
- **调整锻造成功率**：编辑 `game_data.py` 中 `FORGE_RECIPES` 的 `success_rate`

---

## 许可证

[MIT License](LICENSE)

---

## 致谢

灵感来源：觅长生、鬼谷八荒、了不起的修仙模拟器、凡人修仙传
