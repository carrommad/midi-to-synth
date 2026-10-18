# Guía Técnica: Ruta A - FluidSynth sobre Raspberry Pi OS

Esta guía describe la implementación de un sintetizador autónomo de baja latencia utilizando **FluidSynth** y el controlador MIDI **Akai MPK Mini MK2** en una **Raspberry Pi 3 Model B (v1.2)** sin necesidad de monitor ni teclado.
 
### Entorno Verificado:
- **SO:** Raspberry Pi OS basado en Debian GNU/Linux 13 (Trixie)
- **Arquitectura:** 64-bit (aarch64 / arm64)
- **Kernel:** 6.12.75+rpt-rpi-v8 PREEMPT (optimizado para latencia)
- **Tipo de instalación:** Lite (Stage 2, sin entorno de escritorio)

---

## 1. Arquitectura del Sistema

```
 [ Akai MPK Mini MK2 ]
          │ (USB MIDI - Class Compliant)
          ▼
 [ Raspberry Pi 3B / ALSA Sequencer ]
          │
    (alsa_seq: 'MPK mini':0 ──► 'FLUID Synth':0)
          │
   [ FluidSynth Engine ] ◄── General MIDI SoundFont (FluidR3_GM.sf2)
          │
  [ ALSA Audio Driver ] ──► Jack 3.5mm / Auriculares o Parlantes
```

---

## 2. Componentes Instalados
- **FluidSynth**: Motor sintetizador de software en tiempo real basado en la especificación SoundFont 2 (SF2).
- **fluid-soundfont-gm**: Banco de sonido estandarizado General MIDI con más de 128 instrumentos (pianos, bajos, sintetizadores, cuerdas) y kits de batería completos en el canal 10.
- **alsa-utils**: Herramientas de diagnóstico (`speaker-test`, `amixer`, `aconnect`).

---

## 3. Pruebas Manuales (Paso a Paso)

### A. Arranque manual de FluidSynth
```bash
fluidsynth -a alsa -m alsa_seq -g 0.6 /usr/share/sounds/sf2/FluidR3_GM.sf2
```
*Este comando inicia el servidor interactivo de FluidSynth en la terminal.*

### B. Conexión MIDI manual con `aconnect`
En una segunda terminal SSH:
1. Listar puertos MIDI de entrada:
   ```bash
   aconnect -i
   ```
   *(Identifica el cliente de tu teclado, ej: `client 20: 'MPK mini'`)*

2. Listar puertos MIDI de salida:
   ```bash
   aconnect -o
   ```
   *(Identifica el cliente del sintetizador, ej: `client 128: 'FLUID Synth'`)*

3. Conectar teclado y sintetizador:
   ```bash
   aconnect 'MPK mini':0 'FLUID Synth':0
   ```
   *(O usando números: `aconnect 20:0 128:0`)*

4. Tocar teclas o pads en el Akai: el sonido debe escucharse de inmediato.

---

## 4. Automatización con Systemd (Arranque Autónomo)

Para que el sintetizador arranque solo al conectar la alimentación de la Pi:
1. Se utiliza el script `scripts/start-synth.sh` que incluye el parámetro `-o midi.autoconnect=1`.
2. El servicio `/etc/systemd/system/synth.service` se activa con:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable synth.service
   sudo systemctl start synth.service
   ```

### Comandos de control del servicio:
- Ver estado: `sudo systemctl status synth.service`
- Ver registro en vivo: `sudo journalctl -u synth.service -f`
- Detener: `sudo systemctl stop synth.service`
- Reiniciar: `sudo systemctl restart synth.service`
