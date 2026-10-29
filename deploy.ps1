# =========================================================
# deploy.ps1 - 师江系统一键部署脚本
# 部署不执行 Git 操作，代码提交和推送由开发者手动完成。
# =========================================================
# 用法：
#   .\deploy.ps1                  # 全量构建并部署
#   .\deploy.ps1 -FirstDeploy     # 首次部署（额外传输 MySQL 镜像）
#   .\deploy.ps1 -BackendOnly     # 只重建并部署后端
#   .\deploy.ps1 -FrontendOnly    # 只重建并部署前端
#   .\deploy.ps1 -SkipBuild       # 跳过构建，直接传已有镜像
# =========================================================

param(
    [switch]$FirstDeploy,
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$SkipBuild
)

$SERVER  = "root@8.137.168.68"
$SERVER_DIR = "/opt/shijiang"
$SSH_OPTS = "-o StrictHostKeyChecking=no -o BatchMode=yes"
$ErrorActionPreference = "Stop"

function Write-Step([string]$msg, [string]$color = "Cyan") {
    Write-Host ""
    Write-Host ("=" * 55) -ForegroundColor $color
    Write-Host "  $msg" -ForegroundColor $color
    Write-Host ("=" * 55) -ForegroundColor $color
}

Set-Location $PSScriptRoot

# ── Determine which images to build ───────────────────────
$imagesToTransfer = @()

if ($FrontendOnly -and -not $SkipBuild) {
    # ── Frontend-only: npm build locally → SCP dist → rebuild on server ──
    Write-Step "Building frontend (npm run build)"
    Set-Location "$PSScriptRoot\frontend"
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed!" }
    Set-Location $PSScriptRoot

    Write-Step "Uploading dist to server"
    $scpDist = "-o StrictHostKeyChecking=no -r `"$PSScriptRoot\frontend\dist`" ${SERVER}:${SERVER_DIR}/frontend/"
    Invoke-Expression "scp $scpDist"
    if ($LASTEXITCODE -ne 0) { throw "SCP dist failed!" }

    Write-Step "Rebuilding frontend image on server"
    $buildCmd = "cd $SERVER_DIR && docker compose build --no-cache frontend && docker compose up -d frontend"
    Invoke-Expression "ssh $SSH_OPTS $SERVER `"$buildCmd`""
    if ($LASTEXITCODE -ne 0) { throw "Server build failed!" }

} elseif (-not $SkipBuild) {
    if ($BackendOnly) {
        Write-Step "Building backend image locally"
        docker compose build backend
        $imagesToTransfer = @("shijiang-backend:latest")
    } else {
        Write-Step "Building all images locally"
        docker compose build backend frontend
        $imagesToTransfer = @("shijiang-backend:latest", "shijiang-frontend:latest")
    }

    # ── Step 3: First deploy - also send MySQL image ──────────
    if ($FirstDeploy) {
        Write-Step "First Deploy: pulling MySQL:8.0 locally" "Yellow"
        docker pull docker.m.daocloud.io/library/mysql:8.0
        docker tag docker.m.daocloud.io/library/mysql:8.0 mysql:8.0
        $imagesToTransfer = @("mysql:8.0") + $imagesToTransfer
    }

    # ── Step 4: Save images to temp tar and SCP to server ────
    Write-Step "Transferring images to server"
    Write-Host "  Images: $($imagesToTransfer -join ', ')"

    $tmpFile = "$env:TEMP\shijiang-$(Get-Date -Format 'yyyyMMddHHmm').tar"
    Write-Host "  Saving images locally to temp file..."
    $saveArgs = @("save", "-o", $tmpFile) + $imagesToTransfer
    & docker @saveArgs
    if ($LASTEXITCODE -ne 0) { throw "docker save failed!" }

    $sizeMB = [math]::Round((Get-Item $tmpFile).Length / 1MB)
    Write-Host "  File size: ${sizeMB}MB - uploading to server..."
    $scpArgs = "-o StrictHostKeyChecking=no $tmpFile ${SERVER}:/tmp/shijiang-images.tar"
    Invoke-Expression "scp $scpArgs"
    if ($LASTEXITCODE -ne 0) { throw "SCP failed!" }

    Remove-Item $tmpFile -Force
    Write-Host "  Local temp file cleaned up."

    # ── Step 5: Load images on server ────────────────────────
    Write-Step "Loading images on server"
    $loadCmd = "docker load -i /tmp/shijiang-images.tar && rm /tmp/shijiang-images.tar"
    Invoke-Expression "ssh $SSH_OPTS $SERVER `"$loadCmd`""
    if ($LASTEXITCODE -ne 0) { throw "docker load failed!" }
} else {
    $imagesToTransfer = @("shijiang-backend:latest", "shijiang-frontend:latest")
}

# ── Step 6: Start / restart services (skipped for FrontendOnly - already done above) ──
if (-not $FrontendOnly) {
    Write-Step "Starting services on server"
    $upCmd = "cd $SERVER_DIR && docker compose up -d --no-build --pull never && sleep 5 && docker compose ps"
    Invoke-Expression "ssh $SSH_OPTS $SERVER `"$upCmd`""
}

# ── Done ──────────────────────────────────────────────────
Write-Step "Deploy Complete!" "Green"
Write-Host "  Access: http://47.109.24.69" -ForegroundColor Green
Write-Host ""
Write-Host "  Useful commands:" -ForegroundColor DarkGray
Write-Host "    View logs  : ssh $SERVER 'cd $SERVER_DIR && docker compose logs -f'" -ForegroundColor DarkGray
Write-Host "    Restart    : ssh $SERVER 'cd $SERVER_DIR && docker compose restart'" -ForegroundColor DarkGray
Write-Host "    Status     : ssh $SERVER 'cd $SERVER_DIR && docker compose ps'" -ForegroundColor DarkGray
