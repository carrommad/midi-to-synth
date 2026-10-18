# Integración: Raspberry Pi 3 + Akai MPK Mini + Roland S-1 Tweak Synth

Esta guía describe cómo integrar la **Raspberry Pi 3** con el sintetizador **Roland S-1 (AIRA Compact)** y tu sistema de altavoces.

---

## 1. Diagrama de Conexiones del Setup

```
 [ Akai MPK Mini MK2 ]
          │  Cable USB (Alimentación + Datos MIDI)
          ▼
 [ Raspberry Pi 3B ] ◄── Fuente 5V 2.5A
          │
          │  Cable Jack 3.5mm estéreo (Macho a Macho)
          ▼
 [ Roland S-1 (MIX IN) ] ◄── Alimentación USB-C / Batería interna de litio
          │
          │  Cable Jack 3.5mm a Entrada de Altavoz (Aux / RCA / Jack 6.35mm)
          ▼
 [ Altavoz / Monitores de Audio ]
```

---

## 2. Puntos Clave para el Roland S-1

### A. Entrada MIX IN del Roland S-1
- El puerto **MIX IN** del S-1 es una entrada de línea estéreo de **3.5 mm**.
- La señal que llega desde la Raspberry Pi (baterías, pads, sintetizador FluidSynth) se suma automáticamente al motor de sonido interno del Roland S-1 y sale por su conector **MIX OUT / PHONES**.
- **Ventaja musical:** Puedes disparar ritmos y percusiones con los pads del Akai y tocar acordes desde la Pi, mientras usas las 4 voces del Roland S-1 (con sus osciladores ACB, D-Motion, chorus y delay) para líneas de bajo o leads ácidos.

---

### B. Ajuste de Ganancia (Gain Staging)
Para evitar saturación o distorsión armónica en la entrada del Roland S-1:
- El volumen de salida de la Raspberry Pi debe mantenerse al **85% (0.00 dB)** en ALSA.
- Puedes verificar o fijar este nivel en cualquier momento desde la Pi con:
  ```bash
  amixer -c 0 sset PCM 85%
  ```
- Ajusta el volumen final de escucha directamente con la rueda **VOLUME** del Roland S-1 o en tu altavoz.

---

### C. Prevención de Ruido de Masa (Ground Loop)
Si conectas la Raspberry Pi, el Roland S-1 y el altavoz a la misma regleta o cargador multipuerto USB, podría generarse un zumbido de masa (*ground loop hum*).
- **Solución más simple:** El Roland S-1 cuenta con **batería recargable integrada (hasta 4.5 horas)**. Al usar el S-1 con su propia batería mientras tocas, el bucle de masa queda físicamente roto y el sonido es completamente limpio.
- Si necesitas tener ambos conectados permanentemente por cable a la corriente, un aislador de masa pasivo jack 3.5mm (*ground loop noise isolator*) de bajo costo elimina cualquier interferencia.

---

## 3. Posibilidad Futura: Sincronización MIDI USB con el Roland S-1
El Roland S-1 también cuenta con interfaz USB-MIDI y entrada MIDI IN (TRS mini-jack):
- Si en el futuro conectas también el S-1 por USB a la Raspberry Pi, la Pi podrá enviar reloj de sincronización (MIDI Clock), permitiendo que el arpegiador o secuenciador por pasos del Roland S-1 corra al mismo tempo que tus ritmos del Akai.
