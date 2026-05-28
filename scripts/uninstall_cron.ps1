# uninstall_cron.ps1
# Remove a tarefa "EditalIA-Pipeline" do Windows Task Scheduler.

$TaskName = "EditalIA-Pipeline"

$existente = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $existente) {
    Write-Host "Tarefa '$TaskName' nao encontrada. Nada a remover." -ForegroundColor Yellow
    exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "OK — tarefa '$TaskName' removida do Task Scheduler." -ForegroundColor Green
