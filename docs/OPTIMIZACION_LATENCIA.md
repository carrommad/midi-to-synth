# Optimización de Rendimiento y Latencia en Linux Embebido

Este documento reúne las mejores prácticas para reducir la latencia de audio por debajo del umbral perceptible (<10ms) en la Raspberry Pi 3 Model B ejecutando FluidSynth.

---

## 1. Ajustes del Buffer de FluidSynth

FluidSynth permite configurar el tamaño de periodo y la cantidad de periodos ALSA:

```bash
fluidsynth -a alsa -m alsa_seq -g 0.6 \
    -o audio.period-size=128 \
    -o audio.periods=3 \
    /usr/share/sounds/sf2/FluidR3_GM.sf2
```

### Cálculo de Latencia Teórica
- A **44.1 kHz** con `period-size=128` y `periods=3`:  
  `Latencia = (128 * 3) / 44100 = 8.7 ms`  
  *(Casi imperceptible para el oído humano al tocar con los dedos).*
- Si escuchas crujidos (dropouts/underruns) al tocar acordes complejos, sube `period-size` a `256` (latencia ~17.4 ms).

---

## 2. Deshabilitar el Entorno Gráfico (Desktop)

Si tu tarjeta SD tiene instalado Raspberry Pi OS con escritorio, la interfaz gráfica consume valiosos ciclos de CPU y memoria RAM.

Para arrancar en modo consola pura (CLI):
```bash
sudo systemctl set-default multi-user.target
```
*(Si alguna vez necesitas volver al escritorio: `sudo systemctl set-default graphical.target`)*.

---

## 3. Prioridades de Hilo en Tiempo Real (Real-Time Audio)

Evita que procesos secundarios de Linux interrumpan el hilo de síntesis de audio:

1. Añadir el usuario al grupo de audio:
   ```bash
   sudo usermod -a -G audio cromero
   ```

2. Configurar `/etc/security/limits.d/audio-rt.conf`:
   ```text
   @audio - rtprio 95
   @audio - memlock unlimited
   @audio - nice -19
   ```

---

## 4. Gobernador de CPU en Modo Rendimiento

Por defecto, el kernel de Linux baja la velocidad del procesador a 600 MHz cuando no hay actividad y sube a 1200 MHz bajo carga. Este cambio de frecuencia puede introducir micro-cortes de audio:

Para fijar el reloj de la CPU a su máxima velocidad constante:
```bash
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

---

## 5. Salida Onboard 3.5mm vs DAC USB Externo

- **Jack integrado de 3.5mm**: Es práctico y viene integrado, pero utiliza modulación PWM en el SoC Broadcom bcm2835. Esto puede producir un ligero soplido o zumbido de fondo.
- **DAC USB Externo (Recomendado)**: Cualquier adaptador USB económico basado en PCM2704, CM108 o interfaz Behringer UCA222 ofrece:
  - Salida limpia sin interferencias de masa ni ruido PWM.
  - Soporte directo ALSA nativo de 24/16-bit a 48kHz.

---

## 6. Punto de Derivación: Ruta B (mt32-pi)

Si tras aplicar todas estas optimizaciones la latencia sigue siendo notable (>30ms) o buscas un encendido instantáneo en 3 segundos sin sistema operativo:

- **mt32-pi** es una distribución *bare-metal* (sin Linux) que emula sintetizadores Roland MT-32 y SoundFonts Sound Blaster directo sobre el hardware de la Pi 3B.
- Se graba directamente en la tarjeta microSD.
- El Akai MPK Mini se conecta por USB y es reconocido de forma nativa.
- *Desventaja*: Se pierde el acceso por SSH, terminal Linux y la capacidad de ejecutar otros programas.
