# run_pipeline.ps1
# Executado pelo Windows Task Scheduler (1x/dia as 08h).
# Ativa o venv, roda pipeline.py, grava log em state/pipeline_logs/AAAA-MM-DD_HH.log.

$ErrorActionPreference = "Continue"

# Resolve diretorio do projeto a partir da localizacao deste script
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$LogDir     = Join-Path $ProjectDir "state\pipeline_logs"
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

$Stamp   = Get-Date -Format "yyyy-MM-dd_HH"
$LogFile = Join-Path $LogDir "$Stamp.log"

# Cabecalho do log
$Inicio = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"=== Edital.IA pipeline ===" | Out-File -FilePath $LogFile -Encoding utf8
"Iniciado em: $Inicio"       | Out-File -FilePath $LogFile -Encoding utf8 -Append
"ProjectDir : $ProjectDir"   | Out-File -FilePath $LogFile -Encoding utf8 -Append
"Python     : $VenvPython"   | Out-File -FilePath $LogFile -Encoding utf8 -Append
"---"                        | Out-File -FilePath $LogFile -Encoding utf8 -Append

# Sanidade: venv existe?
if (-not (Test-Path $VenvPython)) {
    "ERRO: venv nao encontrado em $VenvPython" | Out-File -FilePath $LogFile -Encoding utf8 -Append
    exit 1
}

# Executa pipeline. PYTHONIOENCODING para evitar erro de cp1252 com chars utf-8.
$env:PYTHONIOENCODING = "utf-8"
Set-Location $ProjectDir

try {
    & $VenvPython -X utf8 -u "pipeline.py" 2>&1 | Out-File -FilePath $LogFile -Encoding utf8 -Append
    $ExitCode = $LASTEXITCODE
} catch {
    "EXCECAO no PowerShell: $_" | Out-File -FilePath $LogFile -Encoding utf8 -Append
    $ExitCode = 1
}

$Fim = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"---"                       | Out-File -FilePath $LogFile -Encoding utf8 -Append
"Finalizado em: $Fim"       | Out-File -FilePath $LogFile -Encoding utf8 -Append
"ExitCode: $ExitCode"       | Out-File -FilePath $LogFile -Encoding utf8 -Append

exit $ExitCode
