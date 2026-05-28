#!/usr/bin/env bash
# install_cron_macos.sh
# Instala o agente launchd que roda pipeline.py 1x/dia as 08:00 no macOS.

set -euo pipefail

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$( dirname "$SCRIPT_DIR" )"
RUN_SCRIPT="$SCRIPT_DIR/run_pipeline.sh"
TEMPLATE="$SCRIPT_DIR/com.editalia.pipeline.plist"
TARGET="$HOME/Library/LaunchAgents/com.editalia.pipeline.plist"
LABEL="com.editalia.pipeline"

if [ ! -f "$TEMPLATE" ]; then
  echo "ERRO: template $TEMPLATE nao encontrado" >&2
  exit 1
fi

if [ ! -f "$RUN_SCRIPT" ]; then
  echo "ERRO: $RUN_SCRIPT nao encontrado" >&2
  exit 1
fi

chmod +x "$RUN_SCRIPT"
mkdir -p "$(dirname "$TARGET")"
mkdir -p "$PROJECT_DIR/state/pipeline_logs"

# Substitui placeholders e copia para LaunchAgents
sed -e "s|__RUN_SCRIPT__|$RUN_SCRIPT|g" \
    -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" \
    "$TEMPLATE" > "$TARGET"

# Se o agente ja estava carregado, descarrega antes (idempotente)
if launchctl print "gui/$UID/$LABEL" &>/dev/null; then
  launchctl bootout "gui/$UID/$LABEL" || true
fi

launchctl bootstrap "gui/$UID" "$TARGET"

echo ""
echo "OK - agente launchd instalado."
echo "    Label    : $LABEL"
echo "    Plist    : $TARGET"
echo "    Horario  : todos os dias as 08:00"
echo "    Logs     : $PROJECT_DIR/state/pipeline_logs/"
echo ""
echo "Rodar AGORA     : launchctl kickstart -k gui/\$UID/$LABEL"
echo "Ver status      : launchctl print gui/\$UID/$LABEL"
echo "Remover         : ./scripts/uninstall_cron_macos.sh"
