# 智学路径（Smart Learning Path）

智学路径是一个面向学生的 AI 自适应学习平台。系统结合知识图谱、答题记录和大语言模型，为学生提供知识诊断、掌握度追踪、个性化学习路径、自动批改、错题复习和 AI 答疑。

## 项目截图

![智学路径项目截图占位](docs/screenshots/preview-placeholder.svg)

> 实际截图可放入 `docs/screenshots/` 并替换 README 中的占位图片。

## 核心功能

- JWT 用户注册、登录与个人信息
- Python 知识图谱与前置依赖查询
- 基于正确率、效率和近期表现的知识掌握度计算
- 最近发展区推荐与有向无环学习路径生成
- 知识点练习、自动批改和答题记录
- 错题本、复习标记与分页查看
- 每个学习内容独立绑定看板、练习、错题、路径和答疑数据
- 支持删除 AI 生成的学习内容，并级联清理对应题库、学习记录和对话数据
- ChromaDB RAG 检索与 DeepSeek AI 答疑
- 全站可拖拽桌面宠物式 AI 小助手，基于独立模型流式即时回答
- 悬浮助手历史会话按当前学习内容隔离保存
- 直接回答式 AI 答疑，未配置 API Key 时自动使用模拟回答
- 学习看板、能力雷达、学习日历与 30 天趋势图
- 响应式 Vue 前端、亮色/暗色主题

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vite、Element Plus、Pinia、Vue Router、Axios |
| 可视化 | ECharts、vue-echarts、D3.js |
| 对话 | marked、highlight.js、DOMPurify |
| 后端 | FastAPI、SQLAlchemy Async、MySQL 8.0、aiomysql |
| 认证 | JWT、bcrypt |
| AI | DeepSeek `deepseek-v4-flash`（原 AI 答疑与内容生成）、`deepseek-chat`（悬浮 AI 小助手） |
| RAG | ChromaDB、本地哈希向量嵌入 |

## 目录结构

```text
smart-learning-path/
├── backend/
│   ├── app/
│   │   ├── core/              # 配置、数据库、JWT、密码、LLM
│   │   ├── data/
│   │   │   ├── knowledge_graph/
│   │   │   └── questions/
│   │   ├── models/            # SQLAlchemy 数据模型
│   │   ├── routers/           # 认证、图谱、推荐、练习、聊天等路由
│   │   ├── schemas/           # Pydantic 请求与响应模型
│   │   ├── services/          # 推荐、追踪、RAG、练习和聊天服务
│   │   └── main.py
│   ├── data/                  # ChromaDB 与生成内容运行时数据
│   ├── scripts/               # 本地 MySQL 启动脚本
│   ├── .env.example
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── api/               # Axios 与业务接口封装
│   │   ├── components/        # 布局、雷达图、图谱节点、题目卡片
│   │   ├── router/            # 路由和登录守卫
│   │   ├── stores/            # 用户、学习和练习状态
│   │   ├── styles/
│   │   └── views/             # 登录、看板、诊断、图谱、路径等页面
│   ├── package.json
│   └── vite.config.js
├── docs/screenshots/
└── README.md
```

## 快速启动

### 环境要求

- Python 3.11+
- Node.js 20+
- npm 10+
- MySQL 8.0+

### 1. 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
.\scripts\start_mysql.ps1
python run.py
```

macOS / Linux 激活虚拟环境：

```bash
source .venv/bin/activate
```

后端地址：

- API：http://localhost:8000
- 健康检查：http://localhost:8000/api/health
- Swagger：http://localhost:8000/docs

`run.py` 默认监听 `0.0.0.0:8000` 并启用热更新。首次运行
`scripts/start_mysql.ps1` 时，脚本会在 `D:\MySQL\zhixue-data` 初始化一个
仅由本项目使用的 MySQL 8.0 实例，监听 `127.0.0.1:3307`，并创建空的
`smart_learning_path` 数据库与 `zhixue_dev` 应用账号。应用启动时会自动
创建业务表、加载知识图谱和题库，并初始化 ChromaDB。

如果 MySQL 安装在其他位置，可指定可执行文件路径：

```powershell
.\scripts\start_mysql.ps1 -MysqldPath "E:\MySQL\bin\mysqld.exe"
```

### 2. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

访问：http://localhost:5173

Vite 会把 `/api` 请求代理到 `http://localhost:8000`。

首次使用时，请在登录页注册账号，再进入学习看板。

## 环境变量

复制 `backend/.env.example` 为 `backend/.env` 后按需修改：

```env
DATABASE_URL=mysql+aiomysql://zhixue_dev:zhixue_dev_2026@127.0.0.1:3307/smart_learning_path?charset=utf8mb4
JWT_SECRET_KEY=your-secret-key-change-in-production
AI_API_KEY=your-deepseek-api-key
AI_BASE_URL=https://api.deepseek.com/v1
AI_CHAT_BASE_URL=https://api.deepseek.com/v1
AI_CHAT_MODEL_NAME=deepseek-v4-flash
AI_ASSISTANT_API_KEY=
AI_ASSISTANT_BASE_URL=https://api.deepseek.com/v1
AI_ASSISTANT_MODEL_NAME=deepseek-chat
```

- `DATABASE_URL` 必须使用 MySQL，普通 `mysql://` 地址也会自动转换为
  `mysql+aiomysql://`。
- 生产环境必须替换 `JWT_SECRET_KEY`。
- 生产环境必须替换示例数据库账号和密码，并限制数据库只允许应用服务器访问。
- `AI_API_KEY` 留空或保留示例占位值时，AI 答疑使用本地模拟回答。
- AI 答疑与内容生成均使用 `deepseek-v4-flash`，内容生成不再单独配置模型。
- `AI_BASE_URL` 用于内容生成，`AI_CHAT_BASE_URL` 用于 AI 答疑，两者都复用 `AI_API_KEY`。
- 悬浮 AI 小助手默认使用独立的 `deepseek-chat` 模型，可通过
  `AI_ASSISTANT_BASE_URL` 和 `AI_ASSISTANT_MODEL_NAME` 切换其他
  OpenAI 兼容模型；`AI_ASSISTANT_API_KEY` 留空时复用 `AI_API_KEY`。

## 主要接口

| 功能 | 接口 |
| --- | --- |
| 健康检查 | `GET /api/health` |
| 注册 / 登录 | `POST /api/auth/register`、`POST /api/auth/login` |
| 当前用户 | `GET /api/auth/profile` |
| 知识图谱 | `GET /api/knowledge/graph/{subject}` |
| 删除学习内容 | `DELETE /api/knowledge/subjects/{subject}` |
| 掌握度看板 | `GET /api/dashboard/progress/{user_id}` |
| 推荐分析 | `POST /api/recommend/analyze` |
| 练习题 / 提交 | `GET /api/practice/questions/{kp_id}`、`POST /api/practice/submit` |
| 错题本 | `GET /api/practice/error-book/{user_id}?subject={subject}` |
| AI 答疑 | `POST /api/chat/ask`、`GET /api/chat/history/{session_id}` |
| 悬浮 AI 小助手 | `POST /api/assistant/chat/stream`（SSE 流式响应） |

所有业务接口使用统一响应：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

切换顶部“学习内容”后，看板统计、推荐路径、练习记录、错题本和 AI
答疑会同时切换到对应的数据。SQLite 版本的数据不会迁移，首次启动 MySQL
时所有业务表均为空。

## 联调流程

1. 注册并登录账号。
2. 进入学习看板查看掌握度和推荐。
3. 完成智能诊断，确认结果页和雷达图。
4. 进入练习页提交答案，检查错题自动进入错题本。
5. 在 AI 答疑页提问，未配置 Key 时确认模拟回答正常。
6. 查看学习路径，点击节点验证详情与练习跳转。

## 生产构建

```powershell
cd frontend
npm run build
```

构建产物位于 `frontend/dist/`。

部署时建议：

- 使用反向代理把 `/api` 转发到 FastAPI，把其他路径交给前端静态文件。
- 使用独立 MySQL 实例或托管 MySQL，并为 `backend/data/` 配置持久化磁盘。
- 使用强随机 `JWT_SECRET_KEY`、数据库密码和真实 AI Key。
- 将 CORS 限制为实际前端域名。
- 使用生产 ASGI 进程管理器运行 FastAPI。

## 部署检查清单

- [x] 后端可通过 `python run.py` 启动
- [x] 前端可通过 `npm run dev` 启动
- [x] 登录 → 看板 → 诊断 → 练习 → 答疑链路可运行
- [x] MySQL 数据库和表结构可自动创建
- [x] 未配置 AI Key 时模拟回答正常
- [x] 配置兼容 API Key 后可调用真实模型
- [x] 前端生产构建通过
