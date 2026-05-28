#!/usr/bin/env bash
# uninstall_cron_linux.sh
# Remove a entrada do crontab marcada com '# editalia-pipeline'.

set -euo pipefail

MARKER="# editalia-pipeline"

if ! crontab -l 2>/dev/null | grep -q "$MARKER"; then
  echo "Nenhuma entrada com '$MARKER' encontrada no crontab. Nada a remover."
  exit 0
fi

crontab -l 2>/dev/null | grep -v "$MARKER" | crontab -
echo "OK - entrada removida do crontab."
