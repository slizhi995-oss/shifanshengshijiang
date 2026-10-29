# 智讲：师范生试讲训练系统

前端使用 Vue 3、TypeScript、Vite 和 Element Plus，后端使用 FastAPI。
本仓库用于团队继续开发，教材、听力、实际数据库和用户上传文件另行交接，不包含真实 API 密钥。

## 队友只开发前端

安装 Node.js 20 或更新的 LTS 版本，在 `frontend` 目录执行：

```powershell
cd frontend
npm ci
```

在 `frontend/.env.development.local` 中填写可访问的后端地址：

```dotenv
VITE_API_TARGET=https://your-backend.example.com
```

地址填写后端服务根地址，不要附加 `/api/v1`。本地后端的默认地址是 `http://localhost:8001`。
Vite 会代理 `/api` 和 `/uploads` 请求；修改配置后需要重启前端开发服务。
向项目负责人获取可用后端地址及专用测试账号。

```powershell
npm run dev
```

按终端输出的地址打开页面，默认端口为 5173。
只使用远程后端时，本地不需要数据库、教材或听力文件。

检查并构建前端：

```powershell
npm run build
```

## 需要本地运行后端时

在项目根目录创建后端环境并安装依赖：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

根据实际情况编辑 `backend/.env`，配置数据库、JWT 密钥及模型接口。
视频功能另外需要 ffmpeg；完整服务器部署可参考 Dockerfile 和 `docker-compose.yml`。
启动命令在项目根目录执行：

```powershell
powershell -File scripts/start-backend.ps1
```

新环境可创建空数据库；要使用现有资源，需要项目负责人提供数据库备份和配套文件，恢复时保留原来的目录结构：

- `backend/app.db`：当前本地 SQLite 数据库，或使用单独配置的 MySQL。
- `backend/private_textbooks/`：已入库教材及配图。
- `音频源文件/`：听力文件和检索元数据。
- `backend/uploads/`、`backend/private_trial_videos/`：需要保留的上传文件和试讲视频。

原始 `教材/` 目录仅在重新导入和整理教材时需要。
数据库与文件配套恢复后无需重新导入。SQLite 备份不能直接作为 MySQL 数据库使用。

## 目录与协作

- `frontend/src/`：页面、组件、状态管理与接口请求。
- `frontend/public/`：前端静态文件和实时评测使用的 MediaPipe 模型。
- `backend/app/`：后端接口、模型和业务逻辑。
- `backend/scripts/`、`scripts/`：启动、维护及验证脚本。
- `backend/tests/`：后端回归测试。
- `docs/`：开发说明、功能文档和比赛资料，历史方案请对照当前代码使用。

克隆项目后，在自己的功能分支开发，再通过 Pull Request 合并。
不要提交 `.env`、数据库、资源包、依赖目录或用户数据。
现有 `deploy.sh`、`deploy.ps1` 包含特定环境的部署设置，使用前须按自己的服务器修改。
部署脚本不执行 Git 提交或推送；需要同步代码时由开发者手动操作。
前端 Dockerfile 使用预先构建的 `frontend/dist/`，构建镜像前先执行 `npm run build`。
