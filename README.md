# 中国象棋 - Chinese Chess Game

一个基于 Python + Flask + SocketIO 的中国象棋 Web 应用，支持**本地双人对战**、**人机对战**和**在线联机对战**三种模式。所有模式均需先注册/登录后使用，每位用户拥有独立的棋局状态。

---

## 功能特性

- 完整的中国象棋规则实现（各棋子走法、将军/绝杀检测、和棋请求等）
- 本地双人同屏对战模式
- **人机对战模式**（Minimax + Alpha-Beta 剪枝，三档难度可调）
- 在线联机对战模式（房间系统、匹配对局）
- 悔棋、认输、求和、棋盘翻转、摆棋模式
- **走子高亮提示**（最近一步起点/终点的视觉标记）
- 实时状态同步与断线重连支持
- **用户注册与登录系统**（基于 Flask Session + SQLite，密码经 werkzeug 哈希）
- **每位用户独立棋局状态**（不同账号互不干扰，关闭页面后下次登录仍在）

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python, Flask, Flask-SocketIO |
| 前端 | HTML5, CSS3, JavaScript (Vanilla) |
| 数据库 | SQLite |
| 实时通信 | WebSocket (Socket.IO) |
| AI 引擎 | 纯 Python（Minimax + Alpha-Beta，无额外依赖） |
| 身份认证 | Flask Session（Cookie-based） |

---

## 项目结构

```
chinese-chess-game/
├── app.py                  # 应用入口
├── db.py                   # SQLite 数据库层
├── logging_config.py       # 日志配置
├── requirements.txt        # Python 依赖
│
├── game/                   # 核心象棋逻辑
│   ├── constants.py        # 棋盘常量、初始布局
│   ├── core.py             # ChessGame 类（走法验证、状态管理）
│   ├── ai.py               # ChessAI 类（轻量 AI 引擎）
│   └── game_session_manager.py  # 按用户管理游戏实例（per-user session）
│
├── online/                 # 联机模块
│   ├── message.py          # 消息结构与验证
│   ├── connection_registry.py  # 连接身份映射
│   └── room_manager.py     # 房间管理与状态同步
│
├── routes/                 # 路由与接口
│   ├── game_routes.py      # 本地游戏 HTTP API（需登录）
│   ├── ai_routes.py        # 人机对战 HTTP API（需登录）
│   ├── auth_routes.py      # 认证接口（注册/登录/登出/me）
│   ├── room_routes.py      # 房间控制 HTTP API（需登录）
│   └── ws_routes.py        # WebSocket 事件处理（需登录）
│
├── static/                 # 静态资源
│   ├── assets/pieces/      # 棋子图片
│   ├── css/style.css       # 样式表
│   └── js/                 # 前端脚本
│       ├── game.js         # 本地对战入口
│       ├── ai_game.js      # 人机对战入口
│       └── modules/
│           ├── board.js    # 棋盘渲染（含走子高亮、防抖动）
│           ├── ui.js       # 本地对战逻辑
│           ├── ai_battle.js# 人机对战逻辑
│           ├── api.js      # HTTP 通信封装
│           ├── auth_ui.js  # 登录状态检查 + 导航栏用户信息
│           └── online.js   # 联机对战逻辑
│
├── templates/              # HTML 模板
│   ├── index.html          # 本地对战页
│   ├── ai_battle.html      # 人机对战页
│   ├── login.html          # 登录/注册页
│   ├── lobby.html          # 联机大厅
│   └── play.html           # 联机对战页
│
└── tests/                  # 测试
    ├── test_game_logic.py  # 象棋规则单元测试
    ├── test_ai_logic.py    # AI 引擎单元测试
    └── test_online_smoke.py # 联机协议冒烟测试
```

---

## 快速开始

### 1. 克隆/下载项目

```bash
cd chinese-chess-game
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv .venv
```

在 Windows 上激活：
```bash
.venv\Scripts\activate
```

在 macOS/Linux 上激活：
```bash
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 运行应用

```bash
python app.py
```

服务启动后，打开浏览器访问：

```
http://127.0.0.1:5004
```

首次使用请先点击右上角「登录」→ 切换到「注册」→ 创建账号。登录后即可使用全部功能。

顶部导航栏可在三种模式间切换：**本地双人** / **人机对战** / **联机大厅**。

---

## 用户认证

所有对战功能均需登录。未登录访问游戏页面会自动跳转至 `/login`，登录成功后跳回原页面（通过 `redirect` 查询参数）。

### 认证方式

- **Flask Session + Cookie**：登录成功后服务端设置 session cookie（httponly），后续请求自动携带
- **密码安全**：使用 werkzeug `generate_password_hash` / `check_password_hash`（PBKDF2）
- **用户存储**：SQLite `users` 表（`id` / `username` / `password_hash` / `created_at`）

### 认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/auth/me`   | 获取当前登录用户，未登录返回 401 |
| POST | `/auth/login`    | 登录（body: `username`, `password`, `redirect?`） |
| POST | `/auth/register` | 注册并自动登录 |
| POST | `/auth/logout`   | 登出，清除 session |

### 按用户隔离游戏状态

之前本地双人 / 人机对战使用全局单例 `ChessGame`，导致所有访问者看到同一个棋盘（"一进去就到上一次的位置"）。现已改为 [game/game_session_manager.py](game/game_session_manager.py) 按 `user_id` 管理每位用户的独立实例：

- 内存字典存储 `{ user_id: { game, game_ai, ai, last_touch } }`
- 每位用户各有一份本地双人和人机对战棋局，互不干扰
- 空闲 1 小时的会话会被自动清理（LRU 式清理）
- 联机对战沿用原有房间系统（按房间 ID 隔离），不在此管理器内

---

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `CHESS_SECRET_KEY` | Flask Session 密钥 | `dev-secret-change-me` |
| `CHESS_DEBUG` | 是否开启调试模式 | `false` |
| `CHESS_LOG_LEVEL` | 日志级别 | `INFO` |
| `CHESS_LOG_FILE` | 日志文件路径 | 无（仅控制台） |

---

## 运行测试

### 单元测试（象棋规则）

```bash
python -m unittest tests.test_game_logic
```

### 冒烟测试（联机协议）

需要先启动服务，再执行测试：

```bash
# 终端 1：启动服务
python app.py

# 终端 2：运行冒烟测试
python tests/test_online_smoke.py
```

---

## 联机通信协议

在线对战使用自定义的三步同步协议：

1. **请求（Request）**：客户端发送带 `msg_id`、`seq`、`payload` 的消息
2. **确认（ACK/NACK）**：服务端校验后返回确认或拒绝
3. **广播（Broadcast）**：服务端将完整状态快照广播给房间内所有玩家

关键设计：
- `seq` 在房间内单调递增，用于保证操作顺序
- `msg_id` 用于消息去重
- 服务端从 WebSocket 连接读取用户身份，**不依赖消息中的 `sender` 字段**

---

## 开源协议

MIT License
