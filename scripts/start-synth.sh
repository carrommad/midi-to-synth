#!/bin/bash
# ==============================================================================
# FluidSynth Standalone Engine Starter for Akai MPK Mini MK2
# ==============================================================================

# Breve espera para asegurar la enumeración de tarjetas ALSA y puertos USB
sleep 4

SOUNDFONT="/usr/share/sounds/sf2/FluidR3_GM.sf2"

# Si no existe FluidR3_GM, buscar cualquier soundfont SF2 disponible en el sistema
if [ ! -f "$SOUNDFONT" ]; then
    SOUNDFONT=$(find /usr/share/sounds/sf2 -name "*.sf2" 2>/dev/null | head -n 1)
fi

echo "Iniciando FluidSynth con SoundFont: $SOUNDFONT"

# -a alsa: Driver de audio nativo Linux ALSA
# -m alsa_seq: Driver MIDI ALSA Sequencer
# -g 1.25: Ganancia equilibrada por defecto al punto medio (0.0 a 5.0)
# -o midi.autoconnect=0: Desactivado para conectar selectivamente MPK Mini y evitar que APC40 dispare el piano
# -o audio.period-size=128 -o audio.periods=3: Optimización para latencia ultrabaja (<10ms)
fluidsynth -s -i -a alsa -m alsa_seq -g 1.25 \
    -o midi.autoconnect=0 \
    -o audio.period-size=128 \
    -o audio.periods=3 \
    "$SOUNDFONT" &

FLUID_PID=$!
echo "FluidSynth en ejecución (PID: $FLUID_PID)"

# Esperar activamente a que FluidSynth cargue por completo el SoundFont en RAM
echo "Esperando a que FluidSynth cargue el SoundFont en memoria..."
for i in $(seq 1 30); do
    if echo "fonts" | nc -w 1 127.0.0.1 9800 2>/dev/null | grep -qi "\.sf2"; then
        echo "SoundFont cargado correctamente en memoria."
        break
    fi
    sleep 1
done

# Pausa para asegurar que el driver PCM de audio ALSA está completamente abierto
sleep 2

# Conectar explícitamente el MPK Mini a FluidSynth (aislando el APC40 del canal 0)
aconnect 'MPK mini 3':0 'FLUID Synth':0 2>/dev/null || aconnect 'MPK mini':0 'FLUID Synth':0 2>/dev/null || true

# Iniciar el controlador inteligente de teclas y sonidos
python3 -u "$(dirname "$0")/akai_controller.py" &
AKAI_PID=$!
echo "Controlador de teclas y sonidos activo (PID: $AKAI_PID)"

wait $FLUID_PID
