# 智学路径（Smart Learning Path）

面向学生的 AI 自适应学习平台。本仓库当前提供 Vue 3 + FastAPI 的前后端项目骨架和健康检查联调示例。

## 技术栈

- 前端：Vue 3、Vite、Element Plus、ECharts、D3.js
- 后端：FastAPI、SQLAlchemy、SQLite
- AI：DeepSeek / 通义千问（OpenAI 兼容接口）
- 向量库：ChromaDB
- 认证：JWT

## 项目结构

```text
smart-learning-path/
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── styles/
│   │   ├── App.vue
│   │   └── main.js
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── backend/
│   ├── app/
│   │   ├── core/
│   │   ├── data/
│   │   ├── models/
│   │   ├── routers/
│   │   ├── services/
│   │   └── main.py
│   ├── .env.example
│   └── requirements.txt
└── README.md
```

## 本地启动

### 1. 启动后端

需要 Python 3.11 或更高版本。

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

健康检查地址：`http://127.0.0.1:8000/api/health`

### 2. 启动前端

需要 Node.js 20 或更高版本。

```powershell
cd frontend
npm install
npm run dev
```

访问：`http://127.0.0.1:5173`

前端开发服务器会将 `/api` 请求代理到 `http://127.0.0.1:8000`。

## 统一响应格式

所有业务接口统一返回：

```json
{
  "code": 0,
  "message": "请求成功",
  "data": {}
}
```

`code = 0` 表示成功，非零值表示失败。
