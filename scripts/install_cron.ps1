# install_cron.ps1
# Registra a tarefa "EditalIA-Pipeline" no Windows Task Scheduler.
# Executa run_pipeline.ps1 todos os dias as 08:00.
#
# Uso:  .\scripts\install_cron.ps1
# Para remover:  .\scripts\uninstall_cron.ps1

$TaskName  = "EditalIA-Pipeline"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunScript = Join-Path $ScriptDir "run_pipeline.ps1"

if (-not (Test-Path $RunScript)) {
    Write-Host "ERRO: nao encontrei $RunScript" -ForegroundColor Red
    exit 1
}

# Se ja existe uma tarefa com esse nome, remove antes de recriar
$existente = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existente) {
    Write-Host "Tarefa '$TaskName' ja existe - removendo antes de recriar." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Action: powershell.exe -NoProfile -ExecutionPolicy Bypass -File <run_pipeline.ps1>
$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RunScript`""

# Trigger: diario as 08:00
$Trigger = New-ScheduledTaskTrigger -Daily -At 08:00

# Settings: roda mesmo em bateria; refaz se a maquina estava off no horario
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# Roda como o usuario logado, sem precisar de senha
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName    $TaskName `
    -Description "Edital.IA - pipeline diario de coleta e extracao de editais (TCC)" `
    -Action      $Action `
    -Trigger     $Trigger `
    -Settings    $Settings `
    -Principal   $Principal | Out-Null

Write-Host ""
Write-Host "OK - tarefa '$TaskName' registrada no Task Scheduler." -ForegroundColor Green
Write-Host "    Horario: todos os dias as 08:00"
Write-Host "    Script : $RunScript"
Write-Host "    Logs   : state/pipeline_logs/AAAA-MM-DD_HH.log"
Write-Host ""
Write-Host "Para rodar AGORA (manual):  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Para verificar status     :  Get-ScheduledTaskInfo -TaskName '$TaskName'"
Write-Host "Para remover              :  .\scripts\uninstall_cron.ps1"
