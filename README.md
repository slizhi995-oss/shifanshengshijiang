# 智讲 · 师范生试讲训练系统

面向师范生、指导教师和管理员的试讲训练平台，支持教学资源管理、教案生成、试讲视频分析、作业提交与教师评价，连接备课、练习、提交和反馈流程。

## 主要功能

| 使用角色 | 功能 |
| --- | --- |
| 学生 | 查看训练任务、生成教案、使用教材与听力资源、上传试讲视频、查看分析和教师反馈 |
| 指导教师 | 查看学生训练情况、批阅作业、评分与反馈、管理指导工作 |
| 管理员 | 管理用户、学期批次、任务、公告、教材、试讲资源和 AI 模型配置 |

平台还提供 AI 助手、实时评测、通知消息和数据统计。AI、视频检索及教材相关功能需要相应接口配置或资源数据。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Element Plus、Pinia、Vue Router、ECharts。
- 后端：Python、FastAPI、SQLAlchemy 异步 ORM、JWT 认证。
- 数据库：本地默认 SQLite，支持 MySQL；Docker Compose 配置使用 MySQL。
- 文档与媒体：PyMuPDF、python-docx、FFmpeg，支持教案导出与视频处理。
- AI：支持配置通义千问、OpenAI 兼容接口等模型服务。

## 目录结构

```text
.
├── backend/
│   ├── app/                 # 后端接口、模型、业务服务及资源目录元数据
│   ├── scripts/             # 数据导入、维护和检查脚本
│   ├── tests/               # 后端测试
│   ├── .env.example         # 本地后端环境变量模板
│   └── requirements.txt     # 后端依赖
├── frontend/
│   ├── src/                 # 页面、组件、接口与状态管理
│   ├── public/              # 静态资源及前端评测模型
│   └── package.json         # 前端依赖与运行命令
├── scripts/                 # 本地启动及项目检查脚本
├── docs/                    # 功能说明与开发资料
├── .env.example             # Docker Compose 环境变量模板
├── docker-compose.yml      # 容器编排配置
├── deploy.ps1               # Windows 部署脚本
└── deploy.sh                # Linux 部署脚本
```

## 本地运行

准备 Python 3.11、Node.js 20 和 npm。下面以 Windows PowerShell 为例，分别打开两个终端运行后端和前端。

### 1. 获取代码

```powershell
git clone https://github.com/slizhi995-oss/shifanshengshijiang.git
cd shifanshengshijiang
```

### 2. 启动后端

在项目根目录执行：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `backend/.env`，将 `JWT_SECRET_KEY` 替换为自己的随机字符串。初次体验可保留默认 SQLite 配置和 `AI_ENABLED=false`，无需先安装 MySQL 或配置模型密钥。

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./app.db
JWT_SECRET_KEY=replace-with-your-own-random-secret
AI_ENABLED=false
```

然后在 `backend` 目录启动：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

首次启动会自动创建数据库表、默认账号及演示数据，无需手动创建 SQLite 文件。

- 接口文档：<http://127.0.0.1:8001/api/docs>
- 健康检查：<http://127.0.0.1:8001/health>

Linux/macOS 可使用 `python3 -m venv .venv` 创建环境，并将上述 `.\.venv\Scripts\python.exe` 换为 `.venv/bin/python`。

### 3. 启动前端

另开一个终端，在项目根目录执行：

```powershell
cd frontend
npm ci
npm run dev
```

浏览器打开终端显示的地址，默认是 <http://localhost:5173>。前端开发服务默认将 `/api` 和 `/uploads` 转发到 `http://localhost:8001`。

如果使用远程后端，在 `frontend/.env.development.local` 中设置：

```dotenv
VITE_API_TARGET=https://your-backend.example.com
```

这里填写后端根地址，不加 `/api/v1`；保存后重启前端开发服务。远程后端还需允许前端地址的 CORS 请求。

### 4. 默认体验账号

新数据库初始化后可使用：

| 角色 | 账号 | 密码 |
| --- | --- | --- |
| 管理员 | `admin` | `admin123` |
| 指导教师 | `teacher` | `teacher123` |
| 学生 | `student` | `student123` |

这些是代码创建的演示账号。正式使用前请修改默认密码。

## AI 与资源配置

本地后端使用 `backend/.env`。常用配置如下，完整字段见模板和 `backend/app/core/config.py`。

| 配置项 | 作用 |
| --- | --- |
| `DATABASE_URL` | SQLite 或 MySQL 数据库连接 |
| `JWT_SECRET_KEY` | 登录令牌签名密钥 |
| `CORS_ORIGINS` | 允许访问后端的前端地址，使用 JSON 数组 |
| `AI_ENABLED`、`AI_PROVIDER` | AI 开关与服务提供方 |
| `DASHSCOPE_API_KEY` | 通义千问模型接口密钥 |
| `BOCHA_API_KEY` | 教学视频检索接口密钥 |
| `TEXTBOOK_STORAGE_DIR` | 教材 PDF 和配图的私有存储目录 |
| `AUDIO_SOURCE_DIR` | 听力资源目录；留空时使用项目根目录的音频源文件目录 |
| `TRIAL_VIDEO_STORAGE_DIR` | 试讲视频私有存储目录 |
| `UPLOAD_DIR` | 作业、附件等上传文件目录 |

启用 AI 后需要填写实际可用的模型配置，管理员也可在模型管理页面维护配置。视频处理使用 FFmpeg；如果系统提示找不到 FFmpeg，请安装并加入系统 PATH。OCR 扩展依赖见 `backend/requirements-ocr.txt`。

GitHub 仓库提供源码、依赖声明和配置模板，不包含实际数据库、教材资源包、听力文件及用户上传数据。首次运行可体验基础流程；完整复现已有资源需要自行导入教材或恢复配套数据：

- `backend/app.db`：本地 SQLite 数据库。
- `backend/private_textbooks/`：教材原文与配图。
- `音频源文件/`：听力文件与检索元数据。
- `backend/uploads/`、`backend/private_trial_videos/`：附件与试讲视频。

迁移已有系统时，应同时备份数据库和对应文件目录。资源导入及维护说明见 `docs/`。

## 构建与部署

前端类型检查及生产构建：

```powershell
cd frontend
npm run build
```

构建结果位于 `frontend/dist/`。项目提供前后端 Dockerfile 与 `docker-compose.yml`；前端镜像使用预先构建的 `dist/`，构建镜像前需先完成上述命令。

容器部署使用项目根目录的 `.env.example` 作为模板，填写数据库密码、JWT 密钥及实际服务配置。部署脚本内包含特定服务器地址，使用前需要按自己的环境修改。已有 SQLite 数据库不能直接作为 MySQL 数据库使用。

## 开发说明

- 前后端分开安装依赖，在 `frontend` 中使用 `npm ci`，在后端虚拟环境中安装 `requirements.txt`。
- 本地后端需从 `backend` 目录启动，确保环境变量、SQLite 和资源路径按预期解析。
- `.env`、数据库、用户数据、资源包、依赖目录及构建产物不提交到 Git。
- 编辑器配置、工具报告、独立示例图片和 demo 视频不参与系统运行。
