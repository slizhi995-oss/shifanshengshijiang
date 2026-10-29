#!/usr/bin/env bash
# =========================================================
# deploy.sh — 师江系统极速部署脚本（v2，无 QEMU 版）
# =========================================================
# 策略：
#   - 后端：rsync 源码 → 服务器原生 docker build（amd64 直接编译，无 QEMU）
#   - 前端：本地 npm run build → rsync dist/ → 服务器构建超轻量 nginx 镜像
#   - 不再使用 docker save / scp tar / docker load（节省 3-10 分钟）
#   - 部署不执行 Git 操作，代码提交和推送由开发者手动完成
#
# 用法：
#   ./deploy.sh                  # 全量部署（后端+前端，默认）
#   ./deploy.sh --backend-only   # 只部署后端
#   ./deploy.sh --frontend-only  # 只部署前端
#   ./deploy.sh --first-deploy   # 首次部署（顺带在服务器拉取 mysql:8.0）
#   ./deploy.sh --restart-only   # 不构建，仅 docker compose up -d 重启
#   ./deploy.sh --no-cache       # 远端 docker build 加 --no-cache
# =========================================================

set -euo pipefail

# ── 配置 ────────────────────────────────────────────────
SERVER="root@8.137.168.68"
SERVER_DIR="/opt/shijiang"
SSH_OPTS="-o StrictHostKeyChecking=no -o BatchMode=yes -o ServerAliveInterval=30"
SSH="ssh $SSH_OPTS $SERVER"

# 公共 rsync 参数：压缩 + 删除多余文件 + 保留权限/时间
RSYNC_OPTS=(-az --delete --progress -e "ssh $SSH_OPTS")

# ── 参数解析 ─────────────────────────────────────────────
BACKEND_ONLY=false
FRONTEND_ONLY=false
FIRST_DEPLOY=false
RESTART_ONLY=false
NO_CACHE=false
for arg in "$@"; do
  case $arg in
    --backend-only)  BACKEND_ONLY=true ;;
    --frontend-only) FRONTEND_ONLY=true ;;
    --first-deploy)  FIRST_DEPLOY=true ;;
    --restart-only)  RESTART_ONLY=true ;;
    --no-cache)      NO_CACHE=true ;;
    -h|--help)
      grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "未知参数: $arg" >&2; exit 1 ;;
  esac
done

DO_BACKEND=true
DO_FRONTEND=true
if [ "$BACKEND_ONLY"  = true ]; then DO_FRONTEND=false; fi
if [ "$FRONTEND_ONLY" = true ]; then DO_BACKEND=false;  fi

# ── 颜色输出 ─────────────────────────────────────────────
CYAN='\033[1;36m'; YELLOW='\033[1;33m'; GREEN='\033[1;32m'
RED='\033[1;31m';  GRAY='\033[0;90m';   NC='\033[0m'
step()  { echo; echo -e "${CYAN}▶ $1${NC}"; }
ok()    { echo -e "${GREEN}✓ $1${NC}"; }
warn()  { echo -e "${YELLOW}! $1${NC}"; }
die()   { echo -e "${RED}✗ $1${NC}" >&2; exit 1; }

cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"

# ── 环境检查 ─────────────────────────────────────────────
command -v rsync >/dev/null || die "缺少 rsync"
command -v ssh   >/dev/null || die "缺少 ssh"
$SSH "echo connected" >/dev/null 2>&1 || die "无法 SSH 到 $SERVER（请检查密钥/网络）"
if [ "$DO_FRONTEND" = true ]; then
  command -v npm >/dev/null || die "缺少 npm（前端需要本地构建）"
fi

START_TS=$(date +%s)

# ── Step 1: 准备服务器目录（首次） ───────────────────────
$SSH "mkdir -p $SERVER_DIR/backend $SERVER_DIR/frontend $SERVER_DIR/ssl"

# 同步 docker-compose.yml / .env / production.env / ssl/
step "Step 1: Syncing compose & env files"
rsync "${RSYNC_OPTS[@]}" docker-compose.yml "$SERVER:$SERVER_DIR/" >/dev/null
[ -f production.env ] && rsync "${RSYNC_OPTS[@]}" production.env "$SERVER:$SERVER_DIR/.env" >/dev/null
[ -d ssl ] && rsync "${RSYNC_OPTS[@]}" ssl/ "$SERVER:$SERVER_DIR/ssl/" >/dev/null
ok "compose 与配置已同步"

# ── 首次部署：拉 mysql ───────────────────────────────────
if [ "$FIRST_DEPLOY" = true ]; then
  step "Step 1a: First-deploy — pulling mysql:8.0 on server"
  $SSH "docker pull mysql:8.0 || docker pull docker.m.daocloud.io/library/mysql:8.0 && docker tag docker.m.daocloud.io/library/mysql:8.0 mysql:8.0"
fi

# ── Step 2: 并行同步后端源码 + 本地构建前端 ──────────────
BUILD_FLAG=""
[ "$NO_CACHE" = true ] && BUILD_FLAG="--no-cache"

BACKEND_PID=""
FRONTEND_PID=""

if [ "$RESTART_ONLY" = false ]; then
  if [ "$DO_BACKEND" = true ]; then
    step "Step 2a: Rsync backend source → server"
    (
      rsync "${RSYNC_OPTS[@]}" \
        --exclude '__pycache__' --exclude '*.pyc' \
        --exclude '.venv' --exclude 'venv' --exclude 'env' \
        --exclude '.pytest_cache' --exclude '.mypy_cache' \
        --exclude 'uploads' --exclude '*.log' --exclude '.env' \
        backend/ "$SERVER:$SERVER_DIR/backend/" >/dev/null
      ok "后端源码已同步"
    ) &
    BACKEND_PID=$!
  fi

  if [ "$DO_FRONTEND" = true ]; then
    step "Step 2b: Local npm run build (frontend)"
    (
      cd frontend
      # 优先 npm ci 保证一致性（lock 存在时）；否则 npm install
      if [ ! -d node_modules ]; then
        if [ -f package-lock.json ]; then npm ci; else npm install; fi
      fi
      npm run build
      ok "前端构建完成 → frontend/dist"
    ) &
    FRONTEND_PID=$!
  fi

  # 等待并发任务
  [ -n "$BACKEND_PID" ]  && wait "$BACKEND_PID"
  [ -n "$FRONTEND_PID" ] && wait "$FRONTEND_PID"

  if [ "$DO_FRONTEND" = true ]; then
    step "Step 2c: Rsync frontend (dist + Dockerfile + nginx.conf) → server"
    rsync "${RSYNC_OPTS[@]}" \
      --exclude 'node_modules' --exclude 'src' --exclude 'public' \
      --exclude '*.log' \
      frontend/dist        "$SERVER:$SERVER_DIR/frontend/" >/dev/null
    rsync "${RSYNC_OPTS[@]}" frontend/Dockerfile  "$SERVER:$SERVER_DIR/frontend/" >/dev/null
    rsync "${RSYNC_OPTS[@]}" frontend/nginx.conf  "$SERVER:$SERVER_DIR/frontend/" >/dev/null
    ok "前端产物已同步"
  fi
fi

# ── Step 3: 远端原生 build（amd64，无 QEMU） ─────────────
if [ "$RESTART_ONLY" = false ]; then
  TARGETS=()
  [ "$DO_BACKEND"  = true ] && TARGETS+=("backend")
  [ "$DO_FRONTEND" = true ] && TARGETS+=("frontend")

  step "Step 3: Remote docker build (${TARGETS[*]}) — native amd64"
  # 并行后端 & 前端构建（DOCKER_BUILDKIT 加速）
  $SSH "cd $SERVER_DIR && DOCKER_BUILDKIT=1 docker compose build $BUILD_FLAG ${TARGETS[*]}"
  ok "远端镜像构建完成"
fi

# ── Step 4: 启动 / 重启服务 ─────────────────────────────
step "Step 4: docker compose up -d"
$SSH "cd $SERVER_DIR && docker compose up -d && sleep 3 && docker compose ps"

# ── Step 5: 清理悬空镜像 ─────────────────────────────────
$SSH "docker image prune -f >/dev/null 2>&1 || true"

END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))

# ── 完成 ──────────────────────────────────────────────────
echo
echo -e "${GREEN}=======================================================${NC}"
echo -e "${GREEN}  部署完成！用时 ${ELAPSED}s${NC}"
echo -e "${GREEN}=======================================================${NC}"
echo -e "  访问地址: ${GREEN}https://shijiang.zpa666.top${NC}"
echo -e "  直连 IP : ${GRAY}https://8.137.168.68${NC} (绕过 Cloudflare 用)"
echo
echo -e "${GRAY}  常用命令:${NC}"
echo -e "${GRAY}    日志:   ssh $SERVER 'cd $SERVER_DIR && docker compose logs -f --tail=200'${NC}"
echo -e "${GRAY}    重启:   ./deploy.sh --restart-only${NC}"
echo -e "${GRAY}    仅后端: ./deploy.sh --backend-only${NC}"
echo -e "${GRAY}    仅前端: ./deploy.sh --frontend-only${NC}"
