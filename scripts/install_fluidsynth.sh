#!/bin/bash
# ==============================================================================
# Script de Instalación y Optimización: FluidSynth + Akai MPK Mini MK2
# ==============================================================================

set -e

echo "=== [1/4] Actualizando repositorios e instalando paquetes ==="
sudo apt update
sudo apt install -y fluidsynth fluid-soundfont-gm alsa-utils

echo "=== [2/4] Configurando permisos de audio y límites en tiempo real ==="
sudo usermod -a -G audio "$USER"

sudo tee /etc/security/limits.d/audio-rt.conf > /dev/null << 'EOF'
@audio - rtprio 95
@audio - memlock unlimited
@audio - nice -19
EOF

echo "=== [3/4] Deshabilitando entorno gráfico para liberar CPU y RAM ==="
sudo systemctl set-default multi-user.target

echo "=== [4/4] Instalando servicio de arranque automático (Systemd) ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
chmod +x "$SCRIPT_DIR/start-synth.sh"

SERVICE_SRC="$SCRIPT_DIR/synth.service"
sudo cp "$SERVICE_SRC" /etc/systemd/system/synth.service
sudo systemctl daemon-reload
sudo systemctl enable synth.service

echo ""
echo "=================================================================="
echo " [OK] Instalación completada con éxito."
echo " Para iniciar el sintetizador inmediatamente ejecuta:"
echo "   sudo systemctl start synth.service"
echo ""
echo " Para ver el estado o logs en tiempo real:"
echo "   sudo journalctl -u synth.service -f"
echo "=================================================================="
