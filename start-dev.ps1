Write-Host "Starting Airwave Development Environment..." -ForegroundColor Cyan

# Check for backend dependencies (Poetry environment)
Write-Host "Checking backend environment..." -ForegroundColor Gray
$poetryPath = "C:\Users\lance\AppData\Local\Programs\Python\Python313\Scripts\poetry.exe"
$envCheck = & $poetryPath -C backend env info --path 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: Backend environment not found. Run 'cd backend; poetry install' first." -ForegroundColor Yellow
}
else {
    Write-Host "Backend environment: OK" -ForegroundColor Green
}

# Start Backend
Write-Host "Starting Backend (Port 8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; `$env:PYTHONPATH='src'; & '$poetryPath' run uvicorn airwave.api.main:app --reload --port 8000"

# Start Frontend
Write-Host "Starting Frontend (Port 5173)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Write-Host "Services started in new windows!" -ForegroundColor Cyan
Write-Host "--------------------------------"
Write-Host "Backend API: http://localhost:8000/docs"
Write-Host "Frontend UI: http://localhost:5173"
