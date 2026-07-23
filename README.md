# 中国象棋 - Chinese Chess Game

一个基于 Python + Flask + SocketIO 的中国象棋 Web 应用，支持**本地双人对战**、**人机对战**和**在线联机对战**三种模式。所有模式均需先注册/登录后使用，每位用户拥有独立的棋局状态。

---

## 功能特性

- 完整的中国象棋规则实现（各棋子走法、将军/绝杀检测、和棋请求、摆棋模式）
- 本地双人同屏对战模式
- **人机对战模式**（Minimax + Alpha-Beta 剪枝，三档难度可调）
- 在线联机对战模式（房间系统、匹配对局、实时同步）
- 悔棋、认输、求和、棋盘翻转
- **走子高亮提示**（最近一步起点/终点的视觉标记）
- 实时状态同步与断线重连支持
- **用户注册与登录系统**（基于 Flask Session + SQLite，密码经 werkzeug 哈希）
- **每位用户独立棋局状态**（不同账号互不干扰，关闭页面后下次登录仍在）
- **AI 思考指示器**（人机对战时显示 AI 正在计算）
- **推演功能**（在浮动小窗口中基于当前局势自由走子推演，不影响真实棋盘；联机模式下仅自己可见，不发送任何网络消息）

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+, Flask 3.0+, Flask-SocketIO 5.6+ |
| 前端 | HTML5, CSS3, JavaScript (Vanilla ES Modules) |
| 数据库 | SQLite（内置，无需额外安装） |
| 实时通信 | WebSocket (Socket.IO 4.7.x) |
| AI 引擎 | 纯 Python（Minimax + Alpha-Beta，无额外依赖） |
| 身份认证 | Flask Session（Cookie-based, httponly） |
| 密码哈希 | werkzeug.security (PBKDF2) |

---

## 项目结构

```
chinese-chess-game/
├── app.py                      # 应用入口（Flask + SocketIO 初始化）
├── db.py                       # SQLite 数据库层（用户表 CRUD）
├── logging_config.py           # 日志配置
├── requirements.txt            # Python 依赖列表
├── LICENSE                     # MIT 协议
│
├── game/                       # 核心象棋逻辑
│   ├── __init__.py
│   ├── constants.py            # 棋盘常量、初始布局、棋子类型定义
│   ├── core.py                 # ChessGame 类（走法验证、状态管理、规则判断）
│   ├── ai.py                   # ChessAI 类（轻量 AI 引擎）
│   └── game_session_manager.py # 按用户管理游戏实例（per-user session）
│
├── online/                     # 联机模块
│   ├── __init__.py
│   ├── message.py              # 消息结构与验证（三步协议）
│   ├── connection_registry.py  # 连接身份映射（user_id → sid）
│   └── room_manager.py         # 房间管理与状态同步
│
├── routes/                     # 路由与接口
│   ├── __init__.py
│   ├── game_routes.py          # 本地游戏 HTTP API（需登录）
│   ├── ai_routes.py            # 人机对战 HTTP API（需登录）
│   ├── auth_routes.py          # 认证接口（注册/登录/登出/me）
│   ├── room_routes.py          # 房间控制 HTTP API（需登录）
│   └── ws_routes.py            # WebSocket 事件处理（需登录）
│
├── static/                     # 静态资源
│   ├── assets/pieces/          # 棋子 PNG 图片（红/黑双方各 7 种）
│   ├── css/style.css           # 样式表（棋盘、棋子、UI 组件）
│   └── js/                     # 前端脚本
│       ├── game.js             # 本地对战入口（初始化 + 事件绑定）
│       ├── ai_game.js          # 人机对战入口
│       ├── socket.io.min.js    # Socket.IO 客户端（本地副本，4.7.5）
│       └── modules/
│           ├── board.js        # 棋盘渲染（含走子高亮、防抖动、支持自定义容器）
│           ├── game_logic.js   # 客户端象棋规则校验（推演用，含 is_valid_move/get_valid_moves）
│           ├── deduce.js       # 推演功能（浮动小窗口，快照悔棋，不影响真实棋盘）
│           ├── ui.js           # 本地对战逻辑
│           ├── ai_battle.js    # 人机对战逻辑（AI 思考、上一步显示）
│           ├── api.js          # HTTP 通信封装（所有 API 调用）
│           ├── auth_ui.js      # 登录状态检查 + 导航栏用户信息
│           └── online.js       # 联机对战逻辑（SocketIO 客户端）
│
├── templates/                  # HTML 模板
│   ├── index.html              # 本地对战页
│   ├── ai_battle.html          # 人机对战页（含难度选择器）
│   ├── login.html              # 登录/注册页（支持 redirect 回跳）
│   ├── lobby.html              # 联机大厅（房间列表、创建/加入）
│   └── play.html               # 联机对战页
│
└── tests/                      # 测试
    ├── __init__.py
    ├── test_game_logic.py      # 象棋规则单元测试（走法验证、将军、和棋）
    ├── test_ai_logic.py        # AI 引擎单元测试（走法选择、难度级别）
    └── test_online_smoke.py    # 联机协议冒烟测试
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

## AI 引擎说明

### 算法设计

AI 引擎基于 **Minimax 算法 + Alpha-Beta 剪枝**，纯 Python 实现，无需额外依赖。

- **搜索深度**：根据难度动态调整
- **估值函数**：基于棋子价值 + 位置因素
- **走法生成**：递归搜索时使用伪合法走法（跳过国王安全检查）以提升性能；根节点使用完整合法走法确保正确性

### 难度级别

| 难度 | 搜索深度 | 特点 |
|------|----------|------|
| 简单 | 1 | 贪心策略，偶尔随机，容易击败 |
| 普通 | 2 | 考虑一步应对，具有一定挑战性 |
| 困难 | 3 | 深度搜索，较强的棋力 |

### 棋子估值

```python
PIECE_VALUES = {
    '帅': 10000, '将': 10000,
    '車': 900,
    '马': 450,
    '炮': 450,
    '相': 200, '象': 200,
    '仕': 200, '士': 200,
    '兵': 100, '卒': 100,
}
```

AI 始终执黑方，玩家始终执红方。玩家走一步后，AI 自动计算并执行回应。

---

## 推演功能说明

**推演**（Deduce）是一个辅助思考工具，让玩家在不影响真实棋盘的情况下，基于当前局势自由走子、预演后续变化。三种对战模式（本地双人、人机对战、联机对战）均已集成。

### 使用方式

1. 在任意对战页面的工具栏点击「推演」按钮
2. 页面右下角展开一个浮动小窗口，显示当前真实局势的副本棋盘
3. 在小棋盘上点击棋子选中，再点击目标位置即可走子（遵循象棋规则校验）
4. 可连续推演多步，推演记录显示在侧边栏
5. 点击「推演悔棋」回退一步，点击「回到当前」将推演棋盘重置为最新真实局势
6. 点击右上角「×」关闭推演面板

### 设计要点

| 特性 | 说明 |
|------|------|
| 独立棋盘 | 推演使用独立的 `ChessGame` 实例，与真实棋盘完全隔离 |
| 局部进行 | 推演完全在浏览器本地完成，不调用任何后端 API，不发送任何 socket 消息 |
| 联机可见性 | 联机模式下推演仅自己可见，对手无感知 |
| 走法校验 | 基于客户端 `game_logic.js` 实现完整棋子走法规则校验（将/士/象/马/车/炮/兵） |
| 快照悔棋 | 每次走子前深拷贝棋盘+回合+历史，悔棋时恢复完整状态（包括被吃棋子） |
| 回到当前 | 通过自定义事件 `deduce:reset-request` 通知宿主页面提供最新真实局势 |
| 翻转同步 | 推演棋盘沿用真实棋盘的翻转状态 |

### 模块依赖

```
deduce.js
  ├── board.js       (renderPieces / renderClickAreas，支持自定义容器渲染)
  └── game_logic.js  (ChessGame 类，提供 is_valid_move / get_valid_moves / make_validated_move)
```

`board.js` 的 `renderPieces` 和 `renderClickAreas` 函数支持传入 `container` 参数（元素 ID 或 DOM 节点），使推演棋盘可复用主棋盘的渲染逻辑，渲染到 `deducePiecesLayer` / `deduceClickAreas` 容器中。

---

## API 接口文档

### 认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/auth/me`   | 获取当前登录用户，未登录返回 401 |
| POST | `/auth/login`    | 登录（body: `username`, `password`, `redirect?`） |
| POST | `/auth/register` | 注册并自动登录 |
| POST | `/auth/logout`   | 登出，清除 session |

### 本地对战接口（需登录）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/state`       | 获取当前棋局状态 |
| POST | `/api/move`        | 走棋（from_x, from_y, to_x, to_y） |
| POST | `/api/valid_moves` | 获取某位置的合法走法 |
| POST | `/api/undo`        | 悔棋一步 |
| POST | `/api/flip`        | 翻转棋盘 |
| POST | `/api/resign`      | 认输 |
| POST | `/api/draw`        | 求和/接受求和/拒绝求和 |
| POST | `/api/reset`       | 重置棋局 |
| POST | `/api/adjust`      | 摆棋模式调整棋子位置 |

### 人机对战接口（需登录）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/ai/state`       | 获取 AI 对战状态 |
| POST | `/api/ai/move`        | 玩家走棋，AI 自动回应 |
| POST | `/api/ai/valid_moves` | 获取红方棋子合法走法 |
| POST | `/api/ai/undo`        | 悔棋（玩家 + AI 各一步） |
| POST | `/api/ai/flip`        | 翻转棋盘 |
| POST | `/api/ai/resign`      | 认输 |
| POST | `/api/ai/reset`       | 重置棋局（可选难度参数） |
| POST | `/api/ai/difficulty`  | 切换难度（重置棋局） |

### 联机对战接口（需登录）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/online/my-room` | 获取当前房间信息 |
| POST | `/api/online/create`  | 创建房间 |
| POST | `/api/online/join`    | 加入房间 |
| POST | `/api/online/leave`   | 离开房间 |

---

## 用户认证与隔离

### 认证机制

所有对战功能均需登录。未登录访问游戏页面会自动跳转至 `/login`，登录成功后跳回原页面（通过 `redirect` 查询参数）。

- **Flask Session + Cookie**：登录成功后服务端设置 session cookie（httponly），后续请求自动携带
- **密码安全**：使用 werkzeug `generate_password_hash` / `check_password_hash`（PBKDF2）
- **用户存储**：SQLite `users` 表（`id` / `username` / `password_hash` / `created_at`）

### 按用户隔离游戏状态

之前本地双人 / 人机对战使用全局单例 `ChessGame`，导致所有访问者看到同一个棋盘（"一进去就到上一次的位置"）。现已改为按 `user_id` 管理每位用户的独立实例：

- 内存字典存储 `{ user_id: { game, game_ai, ai, last_touch } }`
- 每位用户各有一份本地双人和人机对战棋局，互不干扰
- 空闲 1 小时的会话会被自动清理（LRU 式清理）
- 联机对战沿用原有房间系统（按房间 ID 隔离），不在此管理器内

---

## 联机通信协议

在线对战使用自定义的三步同步协议：

1. **请求（Request）**：客户端发送带 `msg_id`、`seq`、`payload` 的消息
2. **确认（ACK/NACK）**：服务端校验后返回确认或拒绝
3. **广播（Broadcast）**：服务端将完整状态快照广播给房间内所有玩家

关键设计：
- `seq` 在房间内单调递增，用于保证操作顺序
- `msg_id` 用于消息去重（防止重复处理）
- 服务端从 WebSocket 连接读取用户身份，**不依赖消息中的 `sender` 字段**
- 心跳机制（PING/PONG 每 5 秒），断线后自动重连并追同步

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

### AI 引擎测试

```bash
python -m unittest tests.test_ai_logic
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

## 常见问题与解决方案

### Q: 为什么一进去就到上一次的位置？

**A:** 这是之前的问题。现在已修复，每位登录用户拥有独立的棋局状态。确保已登录，不同账号之间互不干扰。

### Q: AI 对战页面 JavaScript 加载失败？

**A:** 之前的问题已修复。原因是 `online.js` 注释中包含 `*/` 导致多行注释提前结束，引发语法错误。

### Q: 联机对战页面 socket.io.js 加载失败？

**A:** Flask-SocketIO 5.x 不再自动提供客户端 JS。已改为本地副本 `socket.io.min.js`（4.7.5）。

### Q: 修改模板后不生效？

**A:** Flask 默认不自动重载模板。已在 `app.py` 中设置 `TEMPLATES_AUTO_RELOAD = True`，修改模板后刷新页面即可生效。

### Q: 棋盘抖动问题？

**A:** 之前每次渲染棋子时清空 innerHTML 触发 transition 动画导致抖动。已在 `board.js` 中通过 `no-anim` 类禁用过渡，渲染完成后恢复。

---

## 开发注意事项

### 前端模块结构

所有 JS 文件使用 ES Modules（`type="module"`），通过 `import`/`export` 组织：

- **api.js**：所有 HTTP API 调用封装，统一处理 401（自动跳转登录）
- **board.js**：棋盘渲染核心（棋子绘制、点击区域、走子高亮、支持自定义容器）
- **game_logic.js**：客户端象棋规则校验类 `ChessGame`，为推演功能提供独立的走法校验
- **deduce.js**：推演功能模块（浮动面板、快照悔棋、回到当前）
- **ui.js**：本地对战逻辑（状态管理、事件处理）
- **ai_battle.js**：人机对战逻辑（AI 思考状态、难度切换）
- **auth_ui.js**：登录状态检查、导航栏用户信息显示
- **online.js**：联机对战逻辑（SocketIO 客户端、三步协议）

### 代码规范

- Python：遵循 PEP 8，使用类型提示
- JavaScript：使用 ES6+ 语法，模块化组织
- CSS：使用 BEM 命名规范（`.block__element--modifier`）

---

## 安全考虑

- 密码使用 PBKDF2 哈希存储，不存储明文
- Session cookie 使用 httponly 属性，防止 XSS 窃取
- 所有 API 接口均需登录验证，未登录返回 401
- 联机对战身份验证基于服务端 session，不依赖客户端消息
- 输入参数均做类型校验和边界检查

---

## 开源协议

MIT License

---

## 更新日志

### v1.0.0
- 完整的中国象棋规则实现
- 本地双人对战模式
- 用户注册/登录系统

### v1.1.0
- 新增人机对战模式（Minimax + Alpha-Beta）
- 三档难度选择（简单/普通/困难）
- 走子高亮提示
- 按用户隔离棋局状态

### v1.2.0
- 修复 JavaScript 语法错误（`online.js` 注释中的 `*/`）
- 修复 Socket.IO 客户端加载问题（本地副本替代内置路由）
- 启用模板自动重载
- 完善文档

### v1.3.0
- 新增**推演功能**：在浮动小窗口中基于当前局势自由走子推演，不影响真实棋盘
  - 三种对战模式（本地双人、人机、联机）均已集成
  - 联机模式下仅自己可见，不发送任何网络消息
  - 支持推演悔棋（快照栈）和回到当前真实局势
  - 客户端 `game_logic.js` 实现完整棋子走法规则校验
  - `board.js` 渲染函数支持自定义容器，复用主棋盘渲染逻辑
- 修复将帅照面（飞将）、绝杀、困毙等输赢判定问题
