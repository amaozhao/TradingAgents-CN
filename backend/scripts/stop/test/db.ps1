# Stop Test Database (PostgreSQL + Redis only)
# This script stops test database containers

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Stop Test Database (PostgreSQL + Redis)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Stop test database containers
Write-Host "[INFO] Stopping test database containers..." -ForegroundColor Yellow
docker-compose -f docker-compose.hub.test.db-only.yml down

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host "[OK] Test database stopped!" -ForegroundColor Green
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "[INFO] Test data volumes are preserved:" -ForegroundColor Cyan
    Write-Host "  - trading_agents_test_postgres_data" -ForegroundColor White
    Write-Host "  - trading_agents_test_redis_data" -ForegroundColor White
    Write-Host ""
    Write-Host "[INFO] To remove test data volumes:" -ForegroundColor Yellow
    Write-Host "  docker volume rm trading_agents_test_postgres_data trading_agents_test_redis_data" -ForegroundColor Gray
    Write-Host ""
    Write-Host "[INFO] To start production database:" -ForegroundColor Yellow
    Write-Host "  docker start trading-agents-postgres trading-agents-redis" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "[ERROR] Failed to stop test database containers" -ForegroundColor Red
    exit 1
}
