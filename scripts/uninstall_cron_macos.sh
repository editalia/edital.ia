#!/usr/bin/env bash
# uninstall_cron_macos.sh
# Descarrega e remove o agente launchd com.editalia.pipeline.

set -euo pipefail

LABEL="com.editalia.pipeline"
TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"

if launchctl print "gui/$UID/$LABEL" &>/dev/null; then
  launchctl bootout "gui/$UID/$LABEL"
  echo "OK - agente $LABEL descarregado."
else
  echo "Agente $LABEL nao estava carregado."
fi

if [ -f "$TARGET" ]; then
  rm "$TARGET"
  echo "OK - $TARGET removido."
else
  echo "$TARGET nao existia."
fi
