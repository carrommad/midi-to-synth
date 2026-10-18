# Sintetizador Autónomo Raspberry Pi 3B + Akai MPK Mini MK2 (Ruta A: FluidSynth)

Transforma tu **Raspberry Pi 3 Model B (v1.2)** en un módulo de sonido y sintetizador independiente, de baja latencia y arranque automático sin monitor, controlado por el teclado y pads del **Akai MPK Mini MK2**.

---

## 🖥️ Especificaciones del Sistema (Hardware & OS Verificado)

| Componente | Detalle Verificado |
|---|---|
| **Placa** | Raspberry Pi 3 Model B Rev 1.2 (Quad-Core Cortex-A53 @ 1.2 GHz, 1 GB RAM) |
| **Sistema Operativo** | **Raspberry Pi OS (Debian GNU/Linux 13 "Trixie")** |
| **Arquitectura** | **64-bit (`arm64` / `aarch64`)** |
| **Kernel** | `Linux 6.12.75+rpt-rpi-v8 #1 SMP PREEMPT` |
| **Edición de Imagen** | `pi-gen stage2` (Raspberry Pi OS Lite - Headless / Sin entorno gráfico) |
| **Controlador MIDI** | Akai MPK Mini MK2 / MK3 (USB Class-Compliant) |
| **Salida de Audio** | Salida analógica integrada Jack 3.5mm (`bcm2835 Headphones`, ALSA `hw:0,0`) |

---

## 🎹 Arquitectura del Sistema (Conexión a Roland S-1 y Altavoz)

```mermaid
graph TD
    subgraph Controladores & Fuentes
        Akai[Akai MPK Mini MK2] -->|Cable USB / MIDI| RPi[Raspberry Pi 3B]
        Power[Fuente 5V 2.5A] -->|Micro-USB| RPi
    end

    subgraph Módulo de Sonido (Pi 3B)
        RPi --> ALSA_SEQ[ALSA Sequencer Driver]
        ALSA_SEQ -->|Autoconexión MIDI| Fluid[FluidSynth Engine]
        SoundFont[FluidR3_GM.sf2 - 128 Instrumentos + Baterías] --> Fluid
        Fluid -->|ALSA Audio| Jack[Jack 3.5mm Out]
    end

    subgraph Sintetizador & Salida Externa
        Jack -->|Cable Jack 3.5mm Estéreo| Roland[Roland S-1 MIX IN]
        Roland -->|Suma de Audio + Efectos S-1| MixOut[Roland S-1 MIX OUT]
        MixOut -->|Cable Aux / RCA / Jack| Speaker[Altavoz / Monitores de Audio]
    end
```

---

## 📁 Estructura del Proyecto

```
raspberry-mk2/
├── README.md                      # Documentación central y guía operativa
├── scripts/
│   ├── start-synth.sh             # Script de arranque de FluidSynth con autoconexión
│   ├── synth.service              # Unidad de servicio Systemd para arranque headless
│   └── install_fluidsynth.sh      # Script de instalación y configuración integral
└── docs/
    ├── FASE_A_FLUIDSYNTH.md       # Procedimiento técnico detallado de la Ruta A
    ├── MIDI_MAPPING_AKAI.md       # Mapeo de teclas, pads (Canal 10) y cambio de instrumentos
    └── OPTIMIZACION_LATENCIA.md   # Ajuste de buffers, prioridades rtprio y derivación a mt32-pi
```

---

## 🚀 Despliegue Rápido en la Raspberry Pi

### 1. Conexión por SSH (Sin Contraseña)
```bash
ssh cromero@192.168.1.29
```

### 2. Sincronizar este proyecto a la Pi
Desde tu PC (PowerShell):
```powershell
scp -r "c:\Users\cromero\Desktop\raspberry-mk2" cromero@192.168.1.29:/home/cromero/
```

### 3. Ejecutar el instalador automatizado
En la terminal de la Raspberry Pi:
```bash
cd /home/cromero/raspberry-mk2
chmod +x scripts/*.sh
./scripts/install_fluidsynth.sh
```

---

## 🛠️ Fases del Plan de Implementación

| Fase | Descripción | Estado |
|:---:|:---|:---:|
| **Fase 0** | Diagnóstico inicial (SSH, periféricos, audio físico) | ✅ Completada |
| **Fase 1** | Verificación de hardware (`lsusb`, `speaker-test`) | ✅ Completada |
| **Fase 2** | Instalación de FluidSynth y SoundFont General MIDI | ⏳ En curso |
| **Fase 3** | Conexión MIDI y prueba interactiva de sonido | Pendiente |
| **Fase 4** | Automatización como servicio Systemd en arranque | Pendiente |
| **Fase 5** | Optimización de latencia (buffer 128, rtprio, CPU performance) | Lista para aplicar |

---

## 🎹 Selector de Sonidos Sin Pantalla (C1 y C#1 en el Extremo Izquierdo)

¡Ergonomía perfecta con una sola mano en el extremo izquierdo y opciones a la derecha!

```
    [C#1] Negra (Baterías)
   ┌──┬─┬──┬──┬─┬──┬─┬──┬──┬─┬──┬──┐
   │C1│█│D1│  │█│  │█│  │  │█│  │█ │   (Opciones 1, 2, 3, 4, 5... a la derecha)
   └──┴─┴──┴──┴─┴──┴─┴──┴──┴─┴──┴──┘
   [C1] Blanca (Pianos/Melódicos)
```

### 1. Cambiar Sonido de Piano / Sintetizador / Bajo:
- **Mantén pulsada la Tecla 1 (C1, tecla blanca en el extremo izquierdo)**.
- Con la mano derecha toca cualquiera de las teclas del piano a la derecha (D1 en adelante):
  - *D1:* Yamaha Grand Piano | *E1:* Rhodes | *G1:* Hammond | *E2:* Synth Bass 808 | *A#2 / B2:* Synth Leads.

### 2. Cambiar Kit de Batería (808, 909, Rock, Jazz...):
- **Mantén pulsada la Tecla 2 (C#1, tecla negra contigua, fácil de ubicar al tacto)**.
- Toca una tecla a la derecha (o uno de los 8 pads) para cambiar el kit de batería.

### 3. Las 8 Perillas Giratorias (Knobs) - 2 Bancos de 8 Efectos:
Las 8 perillas controlan **16 parámetros de sonido en tiempo real**:
- **BANCO A (Teclado y Master):** Activo por defecto.
  - `K1`: Cutoff / Brillo | `K2`: Resonancia | `K3`: Ataque | `K4`: Release/Cola
  - `K5`: Reverb Sala | `K6`: Chorus Juno | `K7`: Paneo estéreo | `K8`: **Volumen Maestro**
- **BANCO B (Baterías y Espacio Global):** Se activa al pulsar `BANK A/B` o mantener `C#1`.
  - `K1`: Filtro de Batería | `K2`: Pegada | `K3`: Decaimiento | `K4`: Reverb Batería
  - `K5`: Tamaño de Sala | `K6`: Chorus Depth | `K7`: Paneo Batería | `K8`: Balance de Batería

### 4. Modo `CC` en los Pads (Live FX & Beat Drops - 2 Bancos):
Al pulsar el botón físico **`CC`**, los 8 pads se convierten en disparadores de efectos:
- **BANCO A (Expresión de Teclado):** `Pad 1`: **Sustain Pedal** (pedal de sostenido mientras lo pulsas) | `Pad 2`: Glide/Portamento | `Pad 3`: Apertura de Filtro | `Pad 4`: Reverb Mute | `Pad 8`: Pánico (silencio).
- **BANCO B (DJ & Beat Drops):** `Pad 1`: **BEAT DROP** (mutea/desmutea la batería) | `Pad 2`: Mutea el teclado | `Pad 3`: Reverb Dub Splash | `Pad 4`: Batería Bajo el Agua (Choke) | `Pad 7`: Reset general de efectos.

- **Joystick:** 100% libre para Pitch Bend y Vibrato.

---

## 📋 Cambio Rápido de Instrumentos por Terminal (Opcional)

Hemos incluido la herramienta de línea de comandos **`select-sound`** directamente en la Raspberry Pi para cambiar kits de batería y timbres de teclado en tiempo real sin reiniciar nada:

```bash
# Cambiar la batería de los PADS (Canal 10):
select-sound 808          # Cambia a la mítica caja de ritmos Roland TR-808
select-sound electronic   # Batería electrónica estilo 909 / Techno
select-sound standard     # Batería acústica estándar
select-sound power        # Batería rockera con pegada
select-sound jazz         # Batería estilo jazz

# Cambiar el sonido de las TECLAS (Canal 1):
select-sound piano        # Piano de cola de concierto Yamaha
select-sound rhodes       # Piano eléctrico vintage (Rhodes)
select-sound synthbass    # Sub-bajo sintetizado tipo 808
select-sound organ        # Órgano Hammond con rotary
select-sound lead         # Sintetizador solista Diente de Sierra (Saw)
select-sound pad          # Colchón cálido ambiental (Warm Pad)

# Ver el estado y sonidos actuales:
select-sound status
select-sound list
```

---

## 📋 Mapeo Rápido de Instrumentos

- **Teclas (Canal 1)**: Reproducen instrumentos melódicos. Por defecto: `000 Acoustic Grand Piano`.
  - Para cambiar instrumento en vivo desde la consola de FluidSynth: `prog 0 <número>` (ej. `prog 0 38` para Synth Bass, `prog 0 81` para Lead Sawtooth).
- **Pads (Canal 10)**: Reproducen el kit de percusión General MIDI:
  - **Pad 1 (C1 / 36)**: Bombo 808 / Kick
  - **Pad 2 (D1 / 38)**: Caja / Snare
  - **Pad 3 (F#1 / 42)**: Charles cerrado / Closed Hat
  - **Pad 4 (A#1 / 46)**: Charles abierto / Open Hat
  - **Pad 5 (D#1 / 39)**: Palmada / Clap
  - **Pad 6 (F1 / 41)**: Tom grave
  - **Pad 7 (G1 / 43)**: Tom agudo
  - **Pad 8 (C#2 / 49)**: Plato Crash

---

## ⚠️ Árbol de Decisión para Problemas Comunes

| Síntoma | Causa Probable | Solución Inmediata |
|:---|:---|:---|
| `aconnect -i` no muestra el MPK | Cable USB o puerto | Probar otro cable o puerto. Verificar con `dmesg \| tail`. |
| El teclado aparece pero no suena | Falta conectar puertos ALSA | Ejecutar `aconnect 'MPK mini':0 'FLUID Synth':0`. |
| Sonido con crujidos o latencia | Buffer muy pequeño o CPU scaling | Subir a `period-size=256` o fijar CPU en modo `performance`. |
| Los pads tocan notas y no cambian instrumentos | Configuración de fábrica del Akai | Usar el software **Akai MPK Editor** en Windows para asignar `Program Change`. |
| El servicio systemd no arranca | Rutas o permisos | Revisar logs con `sudo journalctl -u synth.service -n 20`. |

---

## 📚 Enlaces a la Documentación
- [Integración con Sintetizador Roland S-1 y Altavoces](file:///c:/Users/cromero/Desktop/raspberry-mk2/docs/ROLAND_S1_INTEGRATION.md)
- [Guía Detallada Paso a Paso (Ruta A)](file:///c:/Users/cromero/Desktop/raspberry-mk2/docs/FASE_A_FLUIDSYNTH.md)
- [Mapeo MIDI y Uso de Pads con Akai MPK Mini](file:///c:/Users/cromero/Desktop/raspberry-mk2/docs/MIDI_MAPPING_AKAI.md)
- [Optimización de Latencia y Derivación a mt32-pi](file:///c:/Users/cromero/Desktop/raspberry-mk2/docs/OPTIMIZACION_LATENCIA.md)
