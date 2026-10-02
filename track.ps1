$Host.UI.RawUI.WindowTitle = "AMMC - Live Status & Logs"
$dir = "C:\Users\arhou\OneDrive\Bureau\projet omar\colab\chatbot-ammc"
Set-Location $dir

while ($true) {
    Clear-Host
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "===== AMMC LIVE - $now =====" -ForegroundColor Cyan
    Write-Host ""

    Write-Host "URLs" -ForegroundColor Yellow
    Write-Host "  App (React)  : http://localhost:5173"
    Write-Host "  API docs     : http://127.0.0.1:8000/docs"
    Write-Host "  Health       : http://127.0.0.1:8000/api/health"
    Write-Host ""

    try {
        $h = Invoke-RestMethod http://127.0.0.1:8000/api/health -TimeoutSec 5
        Write-Host ("Status : OK  reports={0}  chunks={1}  model={2}" -f $h.rapports, $h.chunks, $h.model) -ForegroundColor Green
    } catch {
        Write-Host "Status : BACKEND DOWN" -ForegroundColor Red
    }

    try {
        $f = Invoke-WebRequest http://localhost:5173 -UseBasicParsing -TimeoutSec 5
        Write-Host ("Frontend : UP ({0})" -f $f.StatusCode) -ForegroundColor Green
    } catch {
        Write-Host "Frontend : DOWN" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "--- last 30 lines: backend_run.log ---" -ForegroundColor Yellow
    if (Test-Path backend_run.log) { Get-Content backend_run.log -Tail 30 } else { Write-Host "(none)" }

    Write-Host ""
    Write-Host "--- last 15 lines: backend_run_err.log ---" -ForegroundColor DarkYellow
    if (Test-Path backend_run_err.log) { Get-Content backend_run_err.log -Tail 15 } else { Write-Host "(none)" }

    Write-Host ""
    Write-Host "--- index errors ---" -ForegroundColor Yellow
    if ((Test-Path data\index_errors.json) -and (Get-Item data\index_errors.json).Length -gt 3) {
        Get-Content data\index_errors.json
    } else {
        Write-Host "none" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "Press C to clear screen, Q to close this window" -ForegroundColor DarkGray
    $k = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    if ($k.Key -eq "C") { Clear-Host }
    if ($k.Key -eq "Q") { break }
}
