#!/usr/bin/env bash
# install_cron_linux.sh
# Adiciona uma entrada no crontab do usuario para rodar pipeline.py 1x/dia as 08:00.
# Idempotente: se ja existir entrada marcada com '# editalia-pipeline', e' substituida.

set -euo pipefail

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
RUN_SCRIPT="$SCRIPT_DIR/run_pipeline.sh"
MARKER="# editalia-pipeline"

if [ ! -f "$RUN_SCRIPT" ]; then
  echo "ERRO: nao encontrei $RUN_SCRIPT" >&2
  exit 1
fi

chmod +x "$RUN_SCRIPT"

# Remove entradas antigas marcadas (idempotente)
NEW_CRONTAB=$(crontab -l 2>/dev/null | grep -v "$MARKER" || true)

# Adiciona nova entrada
NEW_CRONTAB="${NEW_CRONTAB}
0 8 * * * $RUN_SCRIPT  $MARKER"

echo "$NEW_CRONTAB" | crontab -

echo ""
echo "OK - entrada adicionada ao crontab."
echo "    Horario: todos os dias as 08:00"
echo "    Script : $RUN_SCRIPT"
echo "    Logs   : $(dirname "$SCRIPT_DIR")/state/pipeline_logs/"
echo ""
echo "Para verificar : crontab -l"
echo "Para rodar AGORA: $RUN_SCRIPT"
echo "Para remover    : ./scripts/uninstall_cron_linux.sh"
