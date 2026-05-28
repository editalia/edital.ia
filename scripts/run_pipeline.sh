#!/usr/bin/env bash
# run_pipeline.sh
# Executado pelo crontab (Linux) ou launchd (macOS), 1x/dia.
# Ativa o venv, roda pipeline.py, grava log em state/pipeline_logs/AAAA-MM-DD_HH.log.

set -uo pipefail

# Resolve diretorio do projeto a partir da localizacao deste script
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$( dirname "$SCRIPT_DIR" )"
LOG_DIR="$PROJECT_DIR/state/pipeline_logs"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

mkdir -p "$LOG_DIR"

STAMP=$(date +"%Y-%m-%d_%H")
LOG_FILE="$LOG_DIR/$STAMP.log"

# Cabecalho do log
INICIO=$(date +"%Y-%m-%d %H:%M:%S")
{
  echo "=== Edital.IA pipeline ==="
  echo "Iniciado em: $INICIO"
  echo "ProjectDir : $PROJECT_DIR"
  echo "Python     : $VENV_PYTHON"
  echo "---"
} > "$LOG_FILE"

# Sanidade: venv existe?
if [ ! -x "$VENV_PYTHON" ]; then
  echo "ERRO: venv nao encontrado em $VENV_PYTHON" >> "$LOG_FILE"
  exit 1
fi

cd "$PROJECT_DIR"
export PYTHONIOENCODING=utf-8

"$VENV_PYTHON" -X utf8 -u pipeline.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

FIM=$(date +"%Y-%m-%d %H:%M:%S")
{
  echo "---"
  echo "Finalizado em: $FIM"
  echo "ExitCode: $EXIT_CODE"
} >> "$LOG_FILE"

exit $EXIT_CODE
