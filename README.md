# Sintetizador Autónomo Raspberry Pi 3B + Akai MPK Mini MK3 (FluidSynth Standalone)

> 🌐 **Live Web Waveform Visualizer (Roland S-1 & Synths):** [https://carrommad.github.io/midi-to-synth/](https://carrommad.github.io/midi-to-synth/)

Convierte tu **Raspberry Pi 3 Model B (v1.2)** en una estación de sonido y ritmos independiente, con arranque automático sin monitor ni ratón (*zero-screen*), controlada al 100% desde el teclado, perillas y pads del **Akai MPK Mini MK3** (compatible también con MK2).

---

## 🖥️ Especificaciones del Hardware & Sistema

| Componente | Detalle Verificado |
|---|---|
| **Placa** | Raspberry Pi 3 Model B Rev 1.2 (Quad-Core Cortex-A53 @ 1.2 GHz, 1 GB RAM) |
| **Sistema Operativo** | **Raspberry Pi OS (Debian GNU/Linux 13 "Trixie")** |
| **Arquitectura** | **64-bit (`arm64` / `aarch64`)** |
| **Kernel** | `Linux 6.12.75+rpt-rpi-v8 #1 SMP PREEMPT` |
| **Controlador MIDI** | **Akai MPK Mini MK3 / MK2** (USB Class-Compliant) |
| **Motor de Sonido** | **FluidSynth** (ALSA Audio, baja latencia, procesador de efectos reverb y chorus activos) |
| **Salida de Audio** | Salida Jack 3.5mm estéreo hacia Roland S-1 (MIX IN) / Auriculares / Altavoces |

---

## 🎹 Arquitectura del Sistema

```mermaid
graph TD
    subgraph Controladores & Fuentes
        Akai[Akai MPK Mini MK3] -->|Cable USB MIDI| RPi[Raspberry Pi 3B]
        Power[Fuente 5V 2.5A] -->|Micro-USB| RPi
    end

    subgraph Módulo de Sonido (Pi 3B Headless)
        RPi --> ALSA_SEQ[ALSA Sequencer Driver]
        ALSA_SEQ -->|Autoconexión MIDI| Fluid[FluidSynth Engine]
        Controller[akai_controller.py &bull; Daemon] -->|Socket TCP 9800| Fluid
        SoundFont[FluidR3_GM.sf2 &bull; 128 Instrumentos + Baterías] --> Fluid
        Fluid -->|ALSA Audio| Jack[Jack 3.5mm Out]
    end

    subgraph Salida de Audio
        Jack -->|Cable Jack 3.5mm| Roland[Roland S-1 MIX IN / Altavoz]
    end
```

---

## 📑 Manual de Instrucciones en PDF (2 Páginas A4)

Puedes consultar o imprimir el manual visual maquetado con esquemas vectoriales de las teclas y atajos:
* 📄 **[Manual de Instrucciones Akai MPK Mini (PDF)](docs/Manual_Instrucciones_Akai_MPK_Mini.pdf)**
* 🌐 **[Código fuente del manual (HTML)](docs/manual_akai_mpk.html)**
* 📋 **[Mapeo técnico detallado (Markdown)](docs/MIDI_MAPPING_AKAI.md)**

---

## ⚡ Guía Rápida de Operación en Vivo

### 1. Los 4 Modificadores Sin Pantalla (Extremo Izquierdo)
Las 4 primeras teclas del extremo izquierdo del teclado actúan como selectores ergonómicos:
* **`C1` (1ª Blanca) + Teclas (3 a 25)**: Cambia entre **24 Instrumentos Melódicos** (Pianos acústicos, Rhodes, DX7, Órgano Hammond B3, Guitarras, Bajos 808/303, Cuerdas y Sintetizadores) con preview sonoro en celesta.
* **`C#1` (1ª Negra) + Teclas (3 a 25)**: Cambia entre **24 Kits de Batería** (Standard, Room Rock, Heavy Gated, Roland TR-808 Trap, Jazz, Escobillas, Orquestal...) con preview en bombo/caja.
* **`D1` (2ª Blanca) + Pads (1 a 8)**: Control completo del **LIVE BEAT LOOPER**:
  - `Pad 1`: Armar metrónomo / Cerrar loop con redondeo inteligente / Grabar Overdub en capas 2, 3 y 4.
  - `Pad 2`: Pausar o reanudar el bucle.
  - `Pad 3`: Metrónomo click On / Off.
  - `Pad 4`: Borrar todas las pistas (Reset).
  - `Pads 5, 6, 7 y 8`: **Control de Capas 1 a 4** (Toque corto: Silenciar/Mute toggle con chime grave/agudo; Sostener > 1.0s: Borrado individual de esa capa).
* **`D#1` (2ª Negra) + Pads (1 a 8)**: **8 Ritmos Pregrabados** listos para improvisar (1: Lo-Fi 76 BPM, 2: Boom-Bap 88 BPM, 3: Trap 808 138 BPM, 4: Deep House 124 BPM, 5: Rock 104 BPM, 6: Funk 94 BPM, 7: Jazz 118 BPM, 8: Afrobeat 108 BPM).

---

### 2. Atajos Globales de Teclado
* **`C1` + `C#1` (Pulsar a la vez)**: Alterna el modo **FULL LEVEL** del teclado (100% fuerza fija en todas las notas vs curva dinámica táctil).
* **`C1` + `C3` (Sostener 3 segundos)**: **Apagado Seguro** de la Raspberry Pi. Silencia de inmediato las notas extremas, avisa con un sutil chime y reproduce un arpegio descendente de despedida (el inverso exacto de la melodía de arranque) antes de apagar el sistema para proteger la tarjeta microSD.
* **Joystick 4 direcciones**:
  - *Horizontal*: Pitch Bend suave (&plusmn;2 semitonos).
  - *Vertical*: Modulación / Vibrato expresivo.

---

### 3. Matriz Simétrica 4x2 de los 8 Knobs
* **Fila Superior (Batería y Looper)**:
  - `K1`: **Drum Reverb Splash** (CC 91 caja y platos).
  - `K2`: **Drum Pitch Tuning** (Afinación &plusmn;12 semitonos).
  - `K3`: **Looper Tempo** (Control de velocidad en vivo de 30 a 210 BPM).
  - `K4`: **Drum Volume** (Volumen de batería y pads en CC 7 Ch 10).
* **Fila Inferior (Teclado y Master)**:
  - `K5`: **Keys Reverb Eco** (Reverberación catedral en teclado).
  - `K6`: **Keys Chorus Lush** (Grosor vintage Roland Juno).
  - `K7`: **Chorus Speed / Leslie Rotary Rate** (Modulación lenta a rotación rápida de 0.2 a 5.0 Hz).
  - `K8`: **Master Volume** (Volumen general de todo el sistema).

---

### 4. Modo CC en los Pads (Botón físico 'CC' activo)
* `Pad 1`: **Pedal de Sustain** (Toggle para mantener notas flotando sin pedal de pie).
* `Pad 2`: **Portamento / Glide** (Deslizamiento fluido de tono entre notas ligadas).
* `Pad 3`: **Cutoff Boost** (Apertura de filtro y brillo al 100%).
* `Pad 4`: **Reverb Kill** (Corte momentáneo de reverb mientras se pulsa).
* `Pad 5`: **Chorus Splash** (Explosión de chorus espacial mientras se pulsa).
* `Pad 6`: **Instrumento Anterior** (con preview sonoro).
* `Pad 7`: **Instrumento Siguiente** (con preview sonoro).
* `Pad 8`: **¡Pánico / Stop Total!** (silencia cualquier nota o bucle colgado).

---

## 📁 Estructura del Repositorio

```text
midi-to-synth/
├── README.md                      # Esta guía central
├── docs/
│   ├── Manual_Instrucciones_Akai_MPK_Mini.pdf  # Manual imprimible de 2 páginas A4
│   ├── manual_akai_mpk.html                    # Fuente HTML del manual visual
│   ├── MIDI_MAPPING_AKAI.md                    # Mapeo y arquitectura técnica de notas
│   ├── FASE_A_FLUIDSYNTH.md                    # Documentación de instalación base
│   └── OPTIMIZACION_LATENCIA.md                # Parámetros ALSA y buffers de baja latencia
└── scripts/
    ├── akai_controller.py         # Daemon principal (Looper, modificadores, routing, apagado)
    ├── start-synth.sh             # Script de arranque del servicio FluidSynth
    ├── synth.service              # Unidad de servicio Systemd para boot headless
    ├── install_fluidsynth.sh      # Script de aprovisionamiento de dependencias
    └── select_sound.sh            # Utilidad CLI para selección por terminal
```
