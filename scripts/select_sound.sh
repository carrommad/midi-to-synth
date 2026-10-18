#!/usr/bin/env bash
# ==============================================================================
# Sound & Drum Kit Selector for FluidSynth on Raspberry Pi
# ==============================================================================

PORT=9800

send_cmd() {
    echo "$1" | nc -w 1 localhost $PORT > /dev/null 2>&1
}

show_status() {
    echo ""
    echo "=== Estado Actual del Sintetizador ==="
    echo "channels" | nc -w 1 localhost $PORT | grep -E 'chan 0,|chan 9,' | sed 's/chan 0,/  [TECLAS (Canal 1)] :/; s/chan 9,/  [PADS   (Canal 10)]: /'
    echo "======================================"
    echo ""
}

case "$1" in
    # --- PRESETS DE BATERÍA (PADS / Canal 10) ---
    808|tr808|"drums 808")
        send_cmd "prog 9 25"
        echo "[+] Batería cambiada a: Roland TR-808"
        ;;
    electronic|"drums electronic"|909)
        send_cmd "prog 9 24"
        echo "[+] Batería cambiada a: Electronic Kit (909 / Techno)"
        ;;
    standard|"drums standard")
        send_cmd "prog 9 0"
        echo "[+] Batería cambiada a: Standard Acoustic Drum Kit"
        ;;
    room|"drums room")
        send_cmd "prog 9 8"
        echo "[+] Batería cambiada a: Room / Rock Drum Kit"
        ;;
    power|"drums power")
        send_cmd "prog 9 16"
        echo "[+] Batería cambiada a: Power Heavy Drum Kit"
        ;;
    jazz|"drums jazz")
        send_cmd "prog 9 32"
        echo "[+] Batería cambiada a: Jazz Drum Kit"
        ;;
    brush|"drums brush")
        send_cmd "prog 9 40"
        echo "[+] Batería cambiada a: Brush Drum Kit"
        ;;

    # --- PRESETS DE TECLADO (TECLAS / Canal 1) ---
    piano)
        send_cmd "prog 0 0"
        echo "[+] Teclado cambiado a: Yamaha Grand Piano"
        ;;
    rhodes|epiano)
        send_cmd "prog 0 2"
        echo "[+] Teclado cambiado a: Electric Piano (Rhodes / Wurlitzer)"
        ;;
    organ|hammond)
        send_cmd "prog 0 16"
        echo "[+] Teclado cambiado a: Drawbar Organ (Hammond B3)"
        ;;
    synthbass|bass)
        send_cmd "prog 0 38"
        echo "[+] Teclado cambiado a: Synth Bass 1 (Sub Bass)"
        ;;
    fingerbass)
        send_cmd "prog 0 33"
        echo "[+] Teclado cambiado a: Fingered Electric Bass"
        ;;
    strings)
        send_cmd "prog 0 50"
        echo "[+] Teclado cambiado a: Synth Strings"
        ;;
    lead|saw)
        send_cmd "prog 0 81"
        echo "[+] Teclado cambiado a: Lead 2 (Sawtooth Synth)"
        ;;
    square)
        send_cmd "prog 0 80"
        echo "[+] Teclado cambiado a: Lead 1 (Square Synth)"
        ;;
    pad|warm)
        send_cmd "prog 0 88"
        echo "[+] Teclado cambiado a: Warm Synth Pad"
        ;;

    # --- COMANDO GENÉRICO POR NÚMERO ---
    # Ej: select-sound prog 0 4
    prog)
        if [ -n "$2" ] && [ -n "$3" ]; then
            send_cmd "prog $2 $3"
            echo "[+] Enviado: prog $2 $3"
        else
            echo "Uso: select-sound prog <canal_0_o_9> <numero_instrumento>"
        fi
        ;;

    list)
        echo "=== Baterías Disponibles (Pads): ==="
        echo "  select-sound 808         -> Roland TR-808 Drum Machine"
        echo "  select-sound electronic  -> Electronic Kit (Dance / 909)"
        echo "  select-sound standard    -> Standard Acoustic Kit"
        echo "  select-sound power       -> Power Rock Kit"
        echo "  select-sound jazz        -> Jazz Kit"
        echo "  select-sound brush       -> Brush Kit"
        echo ""
        echo "=== Instrumentos Disponibles (Teclas): ==="
        echo "  select-sound piano       -> Yamaha Grand Piano"
        echo "  select-sound rhodes      -> Rhodes Electric Piano"
        echo "  select-sound synthbass   -> Deep Synth Bass (808 Bass)"
        echo "  select-sound fingerbass  -> Bajo Eléctrico tocado con dedos"
        echo "  select-sound organ       -> Órgano Hammond"
        echo "  select-sound strings     -> Cuerdas / Strings"
        echo "  select-sound lead        -> Sintetizador Lead Sawtooth"
        echo "  select-sound square      -> Sintetizador Lead Square"
        echo "  select-sound pad         -> Warm Synth Pad"
        ;;

    status|"")
        ;;

    *)
        echo "Comando no reconocido. Ejecuta 'select-sound list' para ver las opciones."
        ;;
esac

show_status
