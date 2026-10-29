# 高校师范生试讲智慧管理系统 - 后端

基于 FastAPI 的全异步后端服务。

## 技术栈

- **框架:** FastAPI (全异步模式)
- **数据库:** MySQL 8.0+ (SQLAlchemy AsyncSession)
- **验证:** Pydantic V2
- **认证:** JWT
- **文件处理:** aiofiles (异步文件操作)

## 目录结构

```
backend/
├── app/
│   ├── api/                    # API 路由
│   │   ├── routes/
│   │   │   ├── auth.py         # 认证接口
│   │   │   ├── users.py        # 用户管理
│   │   │   ├── semesters.py    # 批次管理
│   │   │   ├── assignments.py  # 分组分配
│   │   │   ├── tasks.py        # 任务管理
│   │   │   ├── submissions.py  # 作业提交
│   │   │   ├── notices.py      # 通知公告
│   │   │   └── messages.py     # 消息留言
│   │   └── __init__.py
│   ├── core/                   # 核心配置
│   │   ├── config.py           # 应用配置
│   │   ├── database.py         # 数据库连接
│   │   ├── security.py         # 安全相关
│   │   └── deps.py             # 依赖注入
│   ├── models/                 # 数据库模型
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── semester.py
│   │   ├── group.py
│   │   ├── task.py
│   │   ├── submission.py
│   │   ├── notice.py
│   │   └── message.py
│   ├── schemas/                # Pydantic 模型
│   │   ├── common.py
│   │   ├── user.py
│   │   ├── semester.py
│   │   ├── group.py
│   │   ├── task.py
│   │   ├── submission.py
│   │   ├── notice.py
│   │   └── message.py
│   ├── utils/                  # 工具函数
│   │   └── file_handler.py
│   └── main.py                 # 应用入口
├── scripts/                    # 脚本
│   ├── init_db.py              # 数据库初始化
│   └── seed_test_data.py       # 测试数据
├── uploads/                    # 上传文件目录
├── requirements.txt
├── .env.example
└── README.md
```

## 快速开始

### 1. 创建虚拟环境

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置数据库连接等
```

### 4. 创建 MySQL 数据库

```sql
CREATE DATABASE shijang CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 5. 初始化数据库

```bash
python -m scripts.init_db
```

### 6. (可选) 添加测试数据

```bash
python -m scripts.seed_test_data
```

### 7. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

本地前端默认代理到 `http://localhost:8001`，后端端口需与 `frontend/.env.development` 中的 `VITE_API_TARGET` 一致。

Windows 已有 `backend/.venv` 时，也可在项目根目录运行：

```powershell
.\scripts\start-backend.ps1
```

脚本自动切换到 `backend` 目录并使用现有虚拟环境，以保证 `.env`、SQLite 数据库及文件存储路径正确。前后端需同时运行；另一个终端进入 `frontend` 后执行 `npm run dev`。

## API 文档

启动服务后访问：
- Swagger UI: http://localhost:8001/api/docs
- ReDoc: http://localhost:8001/api/redoc

## 核心功能

### 用户角色

| 角色 | 权限 |
|------|------|
| Admin | 管理用户、批次、分组，发布通知 |
| Instructor | 发布任务，批改作业，查看学生 |
| Student | 查看任务，提交作业，与导师互动 |

### 主要 API

| 模块 | 路径前缀 | 说明 |
|------|----------|------|
| 认证 | `/api/v1/auth` | 登录、修改密码 |
| 用户 | `/api/v1/users` | 用户 CRUD、Excel导入 |
| 批次 | `/api/v1/semesters` | 试讲周期管理 |
| 分配 | `/api/v1/assignments` | 学生-老师分组 |
| 任务 | `/api/v1/tasks` | 试讲要求发布 |
| 提交 | `/api/v1/submissions` | 作业上传与批改 |
| 通知 | `/api/v1/notices` | 系统公告 |
| 消息 | `/api/v1/messages` | 师生留言 |

## 默认账号

初始化后的默认管理员账号：
- 用户名: `admin`
- 密码: `admin123`

⚠️ 首次登录后请立即修改密码！

AI 资源中心的B 站教学视频检索、API 与验收方式见 [B 站教学视频检索](../docs/B站教学视频检索.md)。
