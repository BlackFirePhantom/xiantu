# 仙途 (XianTu) — 项目指南

> 本文档供 AI 和开发者快速了解项目全貌。每次开新窗口时 AI 会自动读取此文件。

---

## 项目简介

仙途是一款轻量级多人在线修仙文字 RPG，基于 Flask + Flask-SocketIO + SQLite 构建。玩家从青云镇出发，历经九大险地，通过斩妖、修炼、炼丹、锻造等玩法，最终渡劫飞升。

**定位**：2 核 1G 低配服务器部署，支持 50+ 人同时在线。
**GitHub**：`BlackFirePhantom/xiantu`，MIT 许可证。

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端 | Flask 3.1 + Flask-SocketIO 5.5 | WebSocket 实时通信，threading 模式 |
| 数据库 | SQLite WAL 模式 | 零配置，文件位于 `data/game.db` |
| 前端 | 原生 HTML/CSS/JS | 无框架，Socket.IO 客户端本地加载 |
| 部署 | Docker + docker-compose | 端口 8500→5000，含健康检查 |
| 测试 | pytest | 60 个单元测试覆盖核心逻辑 |
| CI | GitHub Actions | 语法检查 + pytest + Docker 构建 |

---

## 项目结构

```
xiantu/
├── app.py                 # Flask + SocketIO 主程序（HTTP路由 + 启动引导，约197行）
├── config.py              # 配置管理（环境变量、密钥持久化、端口）
├── models.py              # SQLite 数据库层（CRUD + 版本化迁移）
├── game_state.py          # 共享内存状态（在线用户/Write-Back缓存/AFK惰性结算）
├── game_data.py           # 游戏数据常量（境界/灵根/功法/经脉/物品/妖兽/地点，约740行）
├── events.py              # 事件数据（20个奇遇 + 16个突发事件）
├── npc_data.py            # NPC 数据（7个NPC、19个任务、宗门系统）
├── game/                  # 游戏逻辑层（纯业务逻辑，无Flask/SocketIO依赖）
│   ├── utils.py           # 工具函数（属性计算、熟练度、修炼倍率）
│   ├── combat.py          # 战斗文案（攻击描述模板）
│   ├── cultivation.py     # 修炼/突破/离线挂机系统
│   ├── crafting.py        # 炼丹 + 炼器锻造
│   ├── pet.py             # 灵宠系统（孵化、喂养、出战）
│   ├── treasure.py        # 藏宝图 + 残卷合成
│   ├── npc.py             # NPC交互 + 好感度 + 任务系统
│   ├── events.py          # 奇遇/突发事件处理
│   └── auction.py         # 拍卖行系统
├── handlers/              # SocketIO 事件处理层（9个子模块）
│   ├── __init__.py        # init_handlers() 注册所有子处理器
│   ├── base.py            # 连接/断开/get_state/chat/排行榜
│   ├── gameplay.py        # 移动/奇遇选择
│   ├── combat.py          # 斩妖战斗
│   ├── cultivation.py     # 打坐/突破/功法/经脉
│   ├── items.py           # 道具使用/卸装/炼丹/炼器/坊市
│   ├── pets.py            # 灵宠孵化/喂养/出战
│   ├── adventure.py       # 藏宝图/残卷合成
│   ├── npc.py             # NPC交互/赠礼/任务
│   └── auction.py         # 拍卖行竞价
├── tests/                 # 单元测试
│   ├── conftest.py        # 共享 fixtures（make_char/make_inv）
│   ├── test_utils.py      # 工具函数测试
│   ├── test_cultivation.py# 修炼系统测试
│   ├── test_pet.py        # 灵宠系统测试
│   ├── test_npc.py        # NPC系统测试
│   ├── test_combat.py     # 战斗文案测试
│   └── test_crafting.py   # 炼丹/锻造测试
├── templates/
│   ├── index.html         # 登录/注册/创建角色页
│   └── game.html          # 游戏主界面（三栏布局）
├── static/
│   ├── css/style.css      # 暗绿修仙主题样式（含移动端响应式 + 战斗动画）
│   └── js/
│       ├── socket.io.min.js
│       ├── socket.js      # Socket.IO 连接与事件绑定
│       ├── ui.js          # 所有渲染函数与面板控制
│       └── main.js        # 入口、键盘快捷键、PWA注册
│   ├── manifest.json      # PWA 配置
│   ├── sw.js              # Service Worker（静态资源缓存）
│   └── icon.svg           # SVG 图标
├── backup.sh              # SQLite 数据库备份脚本
├── .env.example           # 环境变量配置示例
├── PLAN.md                # 工程计划与项目规划（含完成状态）
├── Dockerfile             # 含 HEALTHCHECK
├── docker-compose.yml     # 支持环境变量
├── requirements.txt       # Flask + pytest
└── .github/workflows/ci.yml
```

---

## 核心游戏系统

| 系统 | 说明 | 关键文件 |
|------|------|----------|
| 境界修炼 | 15级，8大境界，突破有失败风险 | `game_data.py` (REALMS, BREAKTHROUGH_CHANCE) |
| 灵根系统 | 10种灵根，五行相克 (+30%/-20% 攻击) | `game_data.py` (SPIRIT_ROOTS, ELEMENT_COUNTER) |
| 战斗系统 | 回合制PvE，21种怪物，9个地点 | `game/combat.py` |
| 功法系统 | 23本功法，4品阶，熟练度系统 | `game_data.py` (TECHNIQUES) |
| 经脉系统 | 8条经脉，消耗修为打通 | `game_data.py` (MERIDIANS) |
| 炼丹系统 | 8个丹药配方 | `game/crafting.py` |
| 炼器锻造 | 18个配方，7品阶，随机属性生成 | `game/crafting.py`, `game_data.py` (generate_equip) |
| 灵宠系统 | 15种灵宠，3品质，孵化/喂养/战斗 | `game/pet.py` |
| 奇遇事件 | 20个小说级剧情，有选择分支 | `events.py` (FORTUNE_EVENTS) |
| 突发事件 | 16个战斗/移动突发事件 | `events.py` (SURPRISE_EVENTS) |
| NPC任务 | 7个NPC，19个任务，好感度系统 | `game/npc.py`, `npc_data.py` |
| 宝图系统 | 3品质藏宝图 + 功法残卷合成 | `game/treasure.py` |
| 拍卖行 | NPC竞拍，每4小时刷新 | `game/auction.py` |
| 挂机修炼 | 离线24h + 在线AFK（10min无操作触发） | `game/cultivation.py` |
| 多人互动 | 实时聊天 + 天骄榜 + 在线人数 | `app.py` |

---

## 运行与测试

```bash
# 直接运行
pip install -r requirements.txt
python app.py
# 访问 http://localhost:5000

# Docker 运行
docker-compose up -d --build
# 访问 http://localhost:8500

# 运行测试
python -m pytest tests/ -v

# 数据库备份
./backup.sh
```

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `XIANTU_SECRET_KEY` | 服务器密钥 | 自动生成并持久化到 `data/.secret_key` |
| `XIANTU_CORS` | CORS 来源 | `*` |
| `XIANTU_PORT` | 端口 | `5000` |
| `XIANTU_HOST` | 监听地址 | `0.0.0.0` |

---

## 架构设计原则

1. **game/ 层纯业务逻辑**：不依赖 Flask/SocketIO/session/emit，方便单元测试
2. **handlers/ 为事件处理层**：接收 socket 事件，调用 game/ 函数，emit 结果
3. **app.py 为 HTTP 路由层**：用户认证、页面渲染、启动引导与后台任务
4. **数据与逻辑分离**：`game_data.py`/`events.py`/`npc_data.py` 纯数据，`game/` 纯逻辑
5. **向后兼容**：密码哈希升级时自动迁移旧 SHA-256 密码
6. **数据库迁移版本化**：`schema_version` 表记录已执行的迁移版本

---

## 工程改造完成状态

Phase 1-4 已全部完成（详见 PLAN.md）：

| 阶段 | 内容 | 状态 |
|------|------|------|
| Phase 1 | 安全修复 + 日志 + 数据库迁移 | ✅ |
| Phase 2 | 代码重构（game/模块） + 单元测试 | ✅ |
| Phase 3 | 前端优化（JS模块化 + 快捷键 + 动画 + PWA） | ✅ |
| Phase 4 | 运维改进（配置管理 + 备份 + CI + Docker） | ✅ |

**待开发功能**（PLAN.md 第四章）：
- v1.1 社交增强：好友、组队、交易
- v1.2 战斗深化：PvP竞技场、Boss战、技能系统
- v1.3 世界扩展：新地图/怪物/功法、天气系统
- v1.4 深度玩法：宗门系统、渡劫飞升、成就系统

---

## 键盘快捷键（桌面端）

| 按键 | 功能 | 按键 | 功能 |
|------|------|------|------|
| F | 斩妖 | T | 功法面板 |
| M | 打坐修炼 | J | 经脉面板 |
| B | 境界突破 | L | 天骄榜 |
| 1-9 | 快速移动 | ESC | 关闭弹窗 |

---

## Commit 规范

```
@ feat:     新功能
@ fix:      Bug修复
@ balance:  平衡性调整
@ refactor: 重构
@ chore:    杂务（CI/Docker/文档）
@ docs:     文档更新
```

---

## 服务器部署信息

- **平台**：Azure VM
- **部署方式**：Docker Compose V2 + sudo
- **更新命令**：`cd ~/xiantu && sudo git pull origin main && sudo docker compose up -d --build`
- **项目路径**：`~/xiantu`
- **外部端口**：8500
