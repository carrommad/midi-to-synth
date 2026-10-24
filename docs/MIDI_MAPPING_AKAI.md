# Mapeo MIDI y Comportamiento del Akai MPK Mini MK2 / MK3 en FluidSynth

Este documento detalla la distribución de notas, comportamiento de pads, arquitectura de modificadores 2x2, perillas y el motor de ritmos (Live Looper y 7 Grooves) para FluidSynth en la Raspberry Pi.

---

## 1. Distribución de Teclas y Pads

```text
 ┌───────────────────────────────────────────────────────────────┐
 │ [JOYSTICK]  [BANK A/B]  [CC]  [PROG]   [KNOB 1] [KNOB 2] ...  │
 │                                                               │
 │             [PAD 5] [PAD 6] [PAD 7] [PAD 8]                   │
 │             [PAD 1] [PAD 2] [PAD 3] [PAD 4]                   │
 │                                                               │
 │ [OCT -/+]   ┌──┬─┬──┬──┬─┬──┬─┬──┬──┬─┬──┬──┐                 │
 │             │  │█│  │  │█│  │█│  │  │█│  │█ │  25 Mini Teclas│
 │             └──┴─┴──┴──┴─┴──┴─┴──┴──┴─┴──┴──┘                 │
 └───────────────────────────────────────────────────────────────┘
```

### A. 25 Mini Teclas (Canal MIDI 1 - Melódico)
Por defecto, las 25 teclas transmiten en el **Canal 1** y reproducen el instrumento melódico activo (por defecto: `000 Yamaha Grand Piano`).
- Sensibles a la velocidad (intensidad del toque con curva dinámica optimizada).
- Botones **OCT - / OCT +**: Permiten desplazar el rango hasta 4 octavas hacia arriba o hacia abajo.

### B. 8 Pads de Percusión (Canal MIDI 10 / Ch 9 en FluidSynth)
Los pads transmiten notas de percusión General MIDI en el Canal 10:
- **Banco A**:
  - **Pad 1 (Nota 36 / C1)**: Bombo Acústico (Bass Drum 1 / 808 Kick)
  - **Pad 2 (Nota 37 / C#1)**: Golpe de aro (Side Stick)
  - **Pad 3 (Nota 38 / D1)**: Caja Acústica (Acoustic Snare)
  - **Pad 4 (Nota 39 / D#1)**: Palmada (Hand Clap)
  - **Pad 5 (Nota 40 / E1)**: Caja Eléctrica (Electric Snare)
  - **Pad 6 (Nota 41 / F1)**: Tom Grave (Low Floor Tom)
  - **Pad 7 (Nota 42 / F#1)**: Charles Cerrado (Closed Hi-Hat)
  - **Pad 8 (Nota 43 / G1)**: Tom Medio (Low-Mid Tom)
- **Banco B**: Notas 44 a 51 (Charles abierto, Platos Crash, Ride, etc.).

### C. Modo CC en los Pads (Pulsando el botón físico `CC`):
Al activar el botón **`CC`** en el Akai, los 8 pads se convierten en una pedalera y centro de control en directo para el teclado:
- **Pad 1**: **Pedal de Sustain (Toggle)** (mantiene las notas flotando sin necesidad de pedal de pie).
- **Pad 2**: **Portamento / Glide (Toggle)** (deslizamiento continuo de tono entre notas ligadas).
- **Pad 3**: **Brillo / Cutoff Boost** (realce de agudos y armónicos al 100%).
- **Pad 4**: **Reverb Kill / Mute (Momentáneo)** (corte instantáneo y seco de reverberación mientras se mantiene pulsado).
- **Pad 5**: **Chorus Splash (Momentáneo)** (chorus estéreo ultra grueso al 100% mientras se mantiene pulsado).
- **Pad 6**: **Instrumento Anterior** (navega hacia atrás por los 24 sonidos melódicos con vista previa inmediata).
- **Pad 7**: **Instrumento Siguiente** (navega hacia adelante por los 24 sonidos melódicos con vista previa inmediata).
- **Pad 8**: **¡Pánico / Stop Total!** (silencia de golpe cualquier nota o bucle colgado).

---

## 2. Los 4 Modificadores Sin Pantalla (Arquitectura Simétrica 2x2)

¡Cero pantallas y cero botones confusos! Las cuatro primeras teclas del extremo izquierdo del teclado actúan como teclas modificadoras ergonómicas:

```text
     [C#1] Negra 1 (Kits de Batería)    [D#1] Negra 2 (7 Ritmos Pregrabados)
    ┌──┬─┬──┬──┬─┬──┬─┬──┬──┬─┬──┬──┐
    │C1│█│D1│  │█│  │█│  │  │█│  │█ │   (Teclas a la derecha: Opciones 1..24)
    └──┴─┴──┴──┴─┴──┴─┴──┴──┴─┴──┴──┘
     [C1] Blanca 1 (Pianos/Sintes)     [D1] Blanca 2 (Live Looper & Grabación)
```

### 🎯 Resumen de la Matriz 2x2:
- **PAR IZQUIERDO (`C1` / `C#1`) + TECLAS -> Selección de Sonidos:**
  - **`C1` (1ª Blanca)** + Teclas: 24 Instrumentos Melódicos (Pianos, Rhodes, Órganos, Bajos, Cuerdas, Sintes).
  - **`C#1` (1ª Negra)** + Teclas: 24 Kits de Batería (Standard, Room, 808, 909, Jazz, Brush...).
- **PAR DERECHO (`D1` / `D#1`) + PADS -> Motores de Ritmo:**
  - **`D1` (2ª Blanca)** + Pads: **LIVE BEAT LOOPER** (Graba tus ritmos, overdub infinito, claqueta, tap tempo).
  - **`D#1` (2ª Negra)** + Pads: **7 RITMOS PREGRABADOS** (Lo-Fi, Boom-Bap, Trap, House, Rock, Funk, Jazz + Stop).

---

### A. Para cambiar Instrumentos de Teclado (Pianos, Bajos, Sintes):
- **Mantén pulsada la Tecla 1 (`C1`, Blanca en el extremo izquierdo)**.
- Con la mano derecha toca una tecla a partir de **D1 (Tecla 3)**:
  - Tecla 3 (D1): **Yamaha Grand Piano**
  - Tecla 4 (D#1): Bright Acoustic Piano
  - Tecla 5 (E1): Electric Piano (Rhodes)
  - Tecla 6 (F1): Electric Piano (FM DX7)
  - Tecla 7 (F#1): Clavinet / Harpsichord
  - Tecla 8 (G1): **Órgano Hammond B3**
  - Tecla 12 (B1): Guitarra eléctrica limpia
  - Tecla 14 (C#2): Bajo eléctrico con dedos
  - Tecla 17 (E2): **Synth Bass 1 (Classic 808 Sub-Bass)**
  - Tecla 18 (F2): **Synth Bass 2 (Acid 303 Bass)**
  - Tecla 19 (F#2): Cuerdas orquestales
  - Tecla 23 (A#2): **Synth Lead 1 (Square Wave)**
  - Tecla 24 (B2): **Synth Lead 2 (Sawtooth Wave)**
  - Tecla 25 (C3): **Warm Synth Pad**

---

### B. Para cambiar Kits de Batería (808, 909, Rock, Jazz...):
- **Mantén pulsada la Tecla 2 (`C#1`, Tecla Negra contigua, fácil de sentir al tacto)**.
- Con la mano derecha toca cualquier tecla a partir de **D1 (Tecla 3)**:
  - Opción 1: **Standard Drum Kit**
  - Opción 6: **Room Rock Kit**
  - Opción 9: **Power Heavy Rock Kit**
  - Opción 13: **Roland TR-808 Classic Trap Kit**
  - Opción 14: **Jazz Drum Kit**
  - Opción 17: **Brush Kit (Escobillas)**
  - Opción 19: **Kit de Percusión Orquestal**

---

### C. Modo FULL LEVEL en las Teclas (Fuerza 100% en el Piano):
- **Mantén pulsadas a la vez las dos primeras teclas del extremo izquierdo (`C1` + `C#1`)**:
  - Activa / Desactiva el modo **FULL LEVEL para las teclas del piano**.
  - **Activado (Chime agudo 84)**: Todas las teclas suenan al 100% de fuerza (velocidad 127), ideal para tocar con soltura sin fatiga en los dedos.
  - **Desactivado (Chime suave 60)**: Vuelve a la respuesta dinámica táctil (con curva suave optimizada para no perder notas).

---

### D. Apagado Seguro de la Raspberry Pi (Protección de Tarjeta SD):
- **Mantén pulsadas a la vez las teclas `C1` (más grave) y `C3` (más aguda) durante 3 segundos**:
  - Suena un chime musical descendente de despedida.
  - Ejecuta un apagado ordenado del sistema operativo Linux (`poweroff`) protegiendo la tarjeta micro-SD.

---

## 3. Las 8 Perillas Giratorias (Knobs) - Matriz Simétrica 4x2

Las 8 perillas están organizadas en una matriz simétrica de 4 columnas perfectamente emparejadas:
- **FILA SUPERIOR (`K1`, `K2`, `K3`, `K4`):** Control exclusivo de la **BATERÍA / LIVE LOOPER**.
- **FILA INFERIOR (`K5`, `K6`, `K7`, `K8`):** Control exclusivo del **TECLADO / PIANO & MASTER**.

```text
┌────────────────────┬────────────────────┬────────────────────┬────────────────────┐
│      KNOB 1        │      KNOB 2        │      KNOB 3        │      KNOB 4        │
│ Drum Reverb Splash │ Drum Pitch Tuning  │ Looper/Metro Tempo │ DRUM & LOOP VOLUME │  <-- FILA SUPERIOR: BATERÍA & BEAT 🥁
├────────────────────┼────────────────────┼────────────────────┼────────────────────┤
│      KNOB 5        │      KNOB 6        │      KNOB 7        │      KNOB 8        │
│    Keys Reverb     │    Keys Chorus     │ Keys Brillo/Filtro │   MASTER VOLUME    │  <-- FILA INFERIOR: TECLADO 🎹
└────────────────────┴────────────────────┴────────────────────┴────────────────────┘
     [Columna 1]          [Columna 2]          [Columna 3]          [Columna 4]
       REVERB          AFINACIÓN / CHORUS     TEMPO / BRILLO          VOLUMEN
```

### Tabla de Funciones y Acción en Vivo:

| Perilla | Sección | Función / Efecto | Acción Sonora Inmediata en Vivo |
|:---:|:---:|:---|:---|
| **`K1`** | 🥁 **Batería** | **Drum Reverb Splash (CC 91)** | Aplica reverberación ambiental a la caja, palmadas y platos. *(Nunca cambia kits ni instrumentos)*. |
| **`K2`** | 🥁 **Batería** | **Drum Pitch / Afinación (±12 st)** | Sube o baja la afinación de toda la batería 1 octava completa: bombos 808 ultra graves a cajas trap agudas. |
| **`K3`** | 🥁 **Looper** | **Looper Tempo (30-210 BPM)** | **Ajuste de velocidad en vivo:** Gira para acelerar o ralentizar tanto el ritmo grabado como los ritmos pregrabados y metrónomo. Rango de 30 a 210 BPM. |
| **`K4`** | 🥁 **Batería & Beat** | **Drum & Loop Volume Mix (CC 7)** | **Mezcla Batería / Fade In-Out:** Sube o baja el volumen de la batería para hacer parones o intensificar el estribillo. |
| **`K5`** | 🎹 **Teclado** | **Keys Reverb Eco (CC 91 + DSP)** | Baña el piano/guitarra en una inmensa catedral (de 100% seco a eco infinito). |
| **`K6`** | 🎹 **Teclado** | **Keys Chorus & Lush (CC 93 + DSP)** | Chorus estéreo exuberante vintage Roland Juno (de 0% limpio a 100% súper ancho). |
| **`K7`** | 🎹 **Teclado** | **Chorus Speed / Leslie Rotary Rate** | **Control de velocidad de modulación (0.2 a 5.0 Hz):** Gira a la izquierda para un vaivén lento, profundo y ambiental (tipo Rhodes o sintetizador vintage); gira a la derecha para una rotación rápida y vibrante tipo **altavoz giratorio Leslie de órgano Hammond** o trémolo. |
| **`K8`** | 🔊 **Master** | **Master Volume (Volumen Maestro)** | **Volumen general de todo el sistema** (0% a 100%, con curva logarítmica natural). |

---

## 4. Motores de Ritmo: Live Looper (`D1` + Pads) vs 8 Presets (`D#1` + Pads)

### A. LIVE BEAT LOOPER (Mantén `D1` - Segunda Tecla Blanca + Pads 1..8):
El Looper te permite grabar tus propios ritmos golpeando los pads o tocando notas en el teclado, y añadir tantas capas encima como desees (*overdubbing* ilimitado).

```text
┌────────────────────────┬────────────────────────┬────────────────────────┬────────────────────────┐
│         PAD 5          │         PAD 6          │         PAD 7          │         PAD 8          │
│     🔊 PISTA 1 (Mute)   │     🔊 PISTA 2 (Mute)   │     🔊 PISTA 3 (Mute)   │     🔊 PISTA 4 (Mute)   │  <- Fila Superior
│   (Voz 1: Bombo/Base)  │   (Voz 2: Caja/Platos) │   (Voz 3: Melodía/Bajo)│   (Voz 4: Arreglos)    │
├────────────────────────┼────────────────────────┼────────────────────────┼────────────────────────┤
│         PAD 1          │         PAD 2          │         PAD 3          │         PAD 4          │
│  🔴 REC / ▶ PLAY /     │    ▶ / ⏸ PAUSA         │     ⏱ METRÓNOMO        │    🗑 CLEAR ALL        │  <- Fila Inferior
│  🟠 OVERDUB (Multiuso) │  (Pausa / Reanuda)     │   (Activa/Mutea click) │  (Borra las 4 pistas)  │
└────────────────────────┴────────────────────────┴────────────────────────┴────────────────────────┘
```

#### Flujo de Trabajo del Live Looper Profesional Híbrido (Mezcla B + C):
1. **⏱ Aclimatación y Escucha (`D1 + PAD 1`):**
   - Pulsa **`PAD 1`**: Entra en modo **ARMED**. El metrónomo empieza a marcar el tempo ajustado en **`K3`**.
   - Puedes escuchar la claqueta todos los compases que necesites para aclimatarte sin prisas. **Todavía no graba silencio**.
2. **🔴 Inicio Instantáneo por Primera Nota (Filosofía C):**
   - En cuanto tocas tu **primera nota de piano o golpe de pad**, suena un chime agudo y **la grabación arranca exactamente en ese instante como Tiempo 0**.
   - Cero huecos vacíos ni silencios de desfase.
3. **▶ Cierre Inteligente con Redondeo Amigable:**
   - Cuando termines tu frase (1, 2, 4 u 8 compases), pulsa **`PAD 1`**.
   - Si pulsas un poco después de la última nota (hasta medio compás de margen de tolerancia), el sistema **redondea inteligentemente al compás final de tu frase** y arranca el loop inmediatamente en reproducción continua.
   - **Nunca se quedará esperando otro compás entero en silencio**.
   - Suena el chime de fin y **el metrónomo se silencia solo**.
4. **🟠 Añadir Capas 2, 3 y 4 (Overdub alternado con Pad 1):**
   - Pulsa **`PAD 1`** mientras suena el bucle: entrarás en grabación sincronizada de la siguiente capa disponible (Capas 2, 3 o 4).
   - Toca encima y vuelve a pulsar **`PAD 1`** para cerrar la capa y volver a PLAY.
5. **🔊 / 🔇 Silenciar o Borrar Capas Individuales (Pads 5, 6, 7 y 8):**
   - **Pulsación corta**: Conmuta Silenciar (Mute / chime grave tenue) o Activar (Unmute / chime agudo brillante) de esa capa específica.
     - `PAD 5`: Capa 1 (Base).
     - `PAD 6`: Capa 2.
     - `PAD 7`: Capa 3.
     - `PAD 8`: Capa 4.
   - **Pulsación larga (> 1.0 segundo)**: Borra por completo los datos de esa capa individual (suena chime de disolución y la capa queda vacía y lista para volver a ser grabada).
6. **⏸ Pausar / Reanudar (Pad 2):** Pausa sin perder ninguna pista.
7. **⏱ Metrónomo On/Off (Pad 3):** Activa o silencia el click de claqueta.
8. **🗑 Borrar Todo (Pad 4):** Limpia las 4 pistas de memoria para empezar una nueva sesión desde cero (suena chime de reset).
9. **⏱ Control de Tempo en Vivo (`KNOB 3`):** Gira la perilla K3 para cambiar la velocidad del bucle en tiempo real entre 30 y 210 BPM.

---

### B. 8 RITMOS PREGRABADOS (Mantén `D#1` - Segunda Tecla Negra + Pads 1..8):
Si no quieres grabar y prefieres una base profesional lista para improvisar encima:

```text
┌────────────────────────┬────────────────────────┬────────────────────────┬────────────────────────┐
│         PAD 5          │         PAD 6          │         PAD 7          │         PAD 8          │
│    Acoustic Pop/Rock   │  Neo-Soul/Funk Pocket  │    Jazz Swing Ride     │  Afrobeat/Latin Groove │  <- Fila Superior
│       (104 BPM)        │       (94 BPM)         │       (118 BPM)        │       (108 BPM)        │
├────────────────────────┼────────────────────────┼────────────────────────┼────────────────────────┤
│         PAD 1          │         PAD 2          │         PAD 3          │         PAD 4          │
│    Lo-Fi Chill Hop     │  Boom-Bap 90s Classic  │    Modern Trap 808     │   Deep House 4-on-Floor│  <- Fila Inferior
│       (76 BPM)         │       (88 BPM)         │       (138 BPM)        │       (124 BPM)        │
└────────────────────────┴────────────────────────┴────────────────────────┴────────────────────────┘
```
- **Toca cualquier Pad del 1 al 8** para arrancar el ritmo correspondiente.
- **Vuelve a tocar el mismo Pad** para detener la base (*Toggle* encendido/apagado).
- **⏱ Auto-Sincronización Inteligente de BPM con el Arpegiador (¡Novedad!):**
  - **Cómo usarlo:**
    1. Ajusta en la pantalla OLED del Akai el tempo deseado (o el tempo exacto de tu sintetizador Roland S-1) manteniendo pulsado **`Arp On/Off`** y girando **`K7`**.
    2. Mantén pulsada cualquier nota o acorde con el arpegiador activo durante 1–2 segundos.
    3. Pulsa **`D#1` + Pad (1..8)**: el ritmo pregrabado **arrancará bloqueado de forma instantánea al BPM exacto de tu arpegiador** en lugar del tempo por defecto.
  - **Ajuste manual posterior:** En cualquier momento durante la reproducción, puedes seguir acelerando o frenando el ritmo libremente girando el knob **`K3`** (30 a 210 BPM).

---

## 5. Tabla Resumen de Atajos Táctiles (Cheat Sheet)

| Tecla Modificadora (Mantener pulsada) | Disparador (Pulsar) | Acción en Vivo |
|:---|:---|:---|
| **`C1`** (1ª Blanca) | **Teclas 1 a 24** | **Cambiar Instrumento Melódico** (24 Pianos, Sintes, Bajos...) |
| **`C#1`** (1ª Negra) | **Teclas 1 a 24** | **Cambiar Kit de Batería** (24 Drum Kits: Standard, 808, 909...) |
| **`D1`** (2ª Blanca) | **Pads 1 a 8** | **LIVE BEAT LOOPER** (Rec/Play/Overdub, Pausa, Clear, Metro, Tap, BPM, Stop) |
| **`D#1`** (2ª Negra) | **Pads 1 a 8** | **8 RITMOS PREGRABADOS** (1: Lo-Fi, 2: Boom-Bap, 3: Trap, 4: House, 5: Rock, 6: Funk, 7: Jazz, 8: Afrobeat) |
| **`C1` + `C#1`** (Juntas) | Ninguno (inmediato) | **Full Level Teclado** (100% fuerza fija vs sensibilidad dinámica) |
| **`C1` + `C3`** (3 segundos) | Mantener 3 seg | **Apagado Seguro del Sistema Linux** |
