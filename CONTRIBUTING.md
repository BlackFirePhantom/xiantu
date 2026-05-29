# 贡献指南

感谢你对仙途项目的关注！

## 如何贡献

### 提交 Bug
使用 [Bug Report](https://github.com/BlackFirePhantom/xiantu/issues/new?template=bug_report.yml) 模板。

### 提出功能
使用 [Feature Request](https://github.com/BlackFirePhantom/xiantu/issues/new?template=feature_request.yml) 模板。

### 提交代码

1. Fork 本仓库
2. 创建分支：`git checkout -b feature/你的功能名`
3. 提交改动：`git commit -m "feat: 描述你的改动"`
4. 推送分支：`git push origin feature/你的功能名`
5. 创建 Pull Request

### Commit 规范

使用语义化前缀：

| 前缀 | 说明 |
|------|------|
| `feat:` | 新功能 |
| `fix:` | Bug 修复 |
| `docs:` | 文档 |
| `style:` | 样式/格式 |
| `refactor:` | 重构 |
| `perf:` | 性能优化 |
| `test:` | 测试 |

### 项目结构

| 文件 | 说明 |
|------|------|
| `app.py` | 主程序，所有游戏逻辑和 WebSocket 事件 |
| `models.py` | SQLite 数据库模型 |
| `game_data.py` | 游戏数据（境界/灵根/功法/物品/妖兽/地点/炼器） |
| `events.py` | 事件集（奇遇 + 突发事件） |
| `templates/` | HTML 模板 |
| `static/` | CSS 和 JS |
