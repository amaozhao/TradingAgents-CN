# Start Test Database (MongoDB + Redis only)
# This script starts test database containers for local code testing

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Start Test Database (MongoDB + Redis)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Check if production database containers are running
Write-Host "[INFO] Checking production database containers..." -ForegroundColor Yellow

$ProdMongoDB = docker ps --format "{{.Names}}" | Select-String "^trading-agents-mongodb$"
$ProdRedis = docker ps --format "{{.Names}}" | Select-String "^trading-agents-redis$"

if ($ProdMongoDB -or $ProdRedis) {
    Write-Host ""
    Write-Host "[WARN] Production database containers are running:" -ForegroundColor Yellow
    if ($ProdMongoDB) {
        Write-Host "  - trading-agents-mongodb (port 27017)" -ForegroundColor White
    }
    if ($ProdRedis) {
        Write-Host "  - trading-agents-redis (port 6379)" -ForegroundColor White
    }
    Write-Host ""
    Write-Host "[WARN] Test database uses the same ports, need to stop production database first." -ForegroundColor Yellow
    Write-Host ""

    $Confirmation = Read-Host "Stop production database containers? (yes/no)"
    if ($Confirmation -eq "yes") {
        Write-Host ""
        Write-Host "[INFO] Stopping production database containers..." -ForegroundColor Yellow

        if ($ProdMongoDB) {
            docker stop trading-agents-mongodb | Out-Null
            Write-Host "  [OK] Stopped: trading-agents-mongodb" -ForegroundColor Green
        }
        if ($ProdRedis) {
            docker stop trading-agents-redis | Out-Null
            Write-Host "  [OK] Stopped: trading-agents-redis" -ForegroundColor Green
        }
    } else {
        Write-Host ""
        Write-Host "[INFO] Cancelled. Please stop production database manually:" -ForegroundColor Yellow
        Write-Host "  docker stop trading-agents-mongodb trading-agents-redis" -ForegroundColor Gray
        Write-Host ""
        exit 0
    }
}

Write-Host ""

# Start test database containers
Write-Host "[INFO] Starting test database containers..." -ForegroundColor Green
docker-compose -f docker-compose.hub.test.db-only.yml up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to start test database containers" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Wait for containers to be healthy
Write-Host "[INFO] Waiting for containers to be healthy..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "[OK] Test database started!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "[INFO] Test database containers:" -ForegroundColor Cyan
Write-Host "  - trading-agents-mongodb-test (port 27017)" -ForegroundColor White
Write-Host "  - trading-agents-redis-test (port 6379)" -ForegroundColor White
Write-Host ""
Write-Host "[INFO] Test data volumes:" -ForegroundColor Cyan
Write-Host "  - trading_agents_test_mongodb_data" -ForegroundColor White
Write-Host "  - trading_agents_test_redis_data" -ForegroundColor White
Write-Host ""
Write-Host "[INFO] Connection strings:" -ForegroundColor Cyan
Write-Host "  MongoDB: mongodb://admin:trading_agents123@localhost:27017/trading_agents?authSource=admin" -ForegroundColor White
Write-Host "  Redis:   redis://:trading_agents123@localhost:6379/0" -ForegroundColor White
Write-Host ""
Write-Host "[INFO] Check container status:" -ForegroundColor Yellow
Write-Host "  docker ps | Select-String 'test'" -ForegroundColor Gray
Write-Host ""
Write-Host "[INFO] Check logs:" -ForegroundColor Yellow
Write-Host "  docker logs -f trading-agents-mongodb-test" -ForegroundColor Gray
Write-Host "  docker logs -f trading-agents-redis-test" -ForegroundColor Gray
Write-Host ""
Write-Host "[INFO] Run local backend:" -ForegroundColor Yellow
Write-Host "  .\.venv\Scripts\python -m uvicorn app.appmain:app --reload --host 0.0.0.0 --port 8000" -ForegroundColor Gray
Write-Host ""
Write-Host "[INFO] Stop test database:" -ForegroundColor Yellow
Write-Host "  .\scripts\stop_test_db.ps1" -ForegroundColor Gray
Write-Host ""
