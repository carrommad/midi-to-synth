# Akai MPK Mini & Magic Pad Interactive Verification Test Suite

This test suite covers every hardware function, shortcut, instrument library, looper capability, and gestural trackpad mode implemented on the Raspberry Pi 3 standalone synth.

### Rotulación Física del Teclado (Marcas sobre las Teclas):
| Marca | Tecla Física | Acción / Función |
|---|---|---|
| **`[K]`** | **$C2$** (1ª blanca izquierda) | **Keys**: Mantén `[K]` + Pads 1..8 para elegir los 8 Sets Melódicos de Instrumentos (200 sonidos) |
| **`[D]`** | **$C\#2$** (1ª negra izquierda) | **Drums**: Mantén `[D]` + Pads 1..8 para elegir 16 Drum Sets (Bank A: 1..8, Bank B: 9..16; Pad 8 Bank A: Flamenco) |
| **`[L]`** | **$D2$** (2ª blanca izquierda) | **Looper**: Mantén `[L]` + Pads 1..8 para control del Live Looper de 8 pistas |
| **`[P]`** | **$D\#2$** (2ª negra izquierda) | **Presets**: Mantén `[P]` + Pads 1..8 para disparar los 16 Ritmos pregrabados |
| **`[●]`** | **$C2$** + **$B3$** (ambas a la vez) | **Big Dot Full Volume**: Mantén 2s `[●]` $C2$ (blanca izq) + `[●]` $B3$ (penúltima blanca der) para 100% volumen |
| **`[—]`** | **$C2$** + **$C4$** (ambas a la vez) | **Line Shutdown**: Mantén 3s los dos extremos `[—]` $C2$ + `[—]` $C4$ para apagar la Raspberry Pi |

---

## 1. Mute / Unmute Function Sounds Confirmation
- **Action:** Put pads in **CC Mode** (press CC button on Akai so it stays lit). Press and hold **Pad 8** for $\ge 2$ seconds.
- **Expected Behavior:**
  1. A soft descending two-tone chime (Celesta: notes 76 $\rightarrow$ 69) plays immediately *before* muting.
  2. Terminal/log shows: `[PAD CC A-8 MANTENIDO 2s] -> Sonidos de función y chimes: MUTED (Silencio)`.
  3. Subsequent function actions (e.g. tapping CC Pad 6/7) produce no preview chimes.
  4. Press and hold **Pad 8** for $\ge 2$ seconds again: A bright ascending two-tone chime (Celesta: 84 $\rightarrow$ 88) plays, confirming unmute.

---

## 2. Dedicated Flamenco Drum Kit on Key E2
- **Action:**
  1. Hold down **C#1** (extreme left black key, base C#) for $\ge 2$ seconds.
  2. While holding C#1, press **Key E2** (third white key, note 52).
  3. Release C#1.
- **Expected Behavior:**
  - FluidSynth selects `Flamenco Cajón & Palmas Kit` (idx 2).
  - Terminal logs: `[DRUM KIT SELECT] -> Tecla 3: Flamenco Cajón & Palmas Kit (Kit 0)`.
- **Testing Pad Bank A (Pads 1..8):**
  - **Pad 1:** Cajón Grave (Deep bass thump)
  - **Pad 2:** Cajón Golpe Seco (Acoustic snare snap)
  - **Pad 3:** Cajón Tapa Aguda (Side stick rim click)
  - **Pad 4:** Palmas Sordas (Muffled hand clap)
  - **Pad 5:** Castañuelas Clack (Claves sharp wood strike)
  - **Pad 6:** Castañuela Alta (High pitched woodblock)
  - **Pad 7:** Castañuela Baja (Low pitched woodblock)
  - **Pad 8:** Zapateado / Pitos (High agogo resonance)
- **Testing Pad Bank B (Pads 9..16):**
  - Press `BANK A/B` button so Bank B is active.
  - **Pad 9:** Tacón Sordo (Pedal hi-hat foot tap)
  - **Pad 10:** Pandereta Flamenca (Tambourine jingle)
  - **Pad 11:** Shaker / Cabasa Rítmica (Rhythmic scraping roll)
  - **Pad 12:** Maracas Acento (Crisp maraca shake)
  - **Pad 13:** Triángulo Cerrado (Muted acoustic metallic chime)
  - **Pad 14:** Triángulo Abierto (Open resonant metallic ring)
  - **Pad 15:** Raspado Corto (Short guiro scrape)
  - **Pad 16:** Raspado Largo (Long guiro scrape)

---

## 3. Melodic Library Diversity & Selection (No Duplicates)
- **Action:** Hold **C1** (extreme left white key) and press **Pad 1..8**:
  - **Pad 1:** Library 1 — Deep Basses & 808s (24 distinct GM bass/low instruments)
  - **Pad 2:** Library 2 — World & Ethnic Instruments (Sitar, Banjo, Koto, Kalimba, Pan Flute, Dulcimer, Steel Drums, etc.)
  - **Pad 3:** Library 3 — Synths, Leads & Warm Pads (Square, Saw, Chiff, Polysynth, Choir, Oberheim, etc.)
  - **Pad 4:** Library 4 — Pianos, Organs & Keys (Yamaha Grand, Rhodes, Wurlitzer, Harpsichord, Clavinet, Hammond, etc.)
  - **Pad 5:** Library 5 — Guitars & Plucked Strings (Spanish Nylon, Strat, Archtop, Harp, Banjo, etc.)
  - **Pad 6:** Library 6 — Orchestral Strings, Brass & Woodwinds (Violin, Cello, Trumpet, Trombone, Saxophones, Oboe, etc.)
  - **Pad 7:** Library 7 — Retro 8-Bit Chiptune & Sound FX (NES pulse, Game Boy saw, C64 chip, Raindrop, Crystal, etc.)
  - **Pad 8:** Library 8 — Ambient Drones & Soundscapes (Deep space pads, cathedral swells, cavern drops, etc.)
- **Expected Behavior:**
  - In CC Mode, tap **Pad 6** or **Pad 7** to step forward or backward through each of the 24 instruments within the active set.
  - Hold **Pad 6** or **Pad 7** ($>0.5$s) to cycle between the 8 library sets.
  - Every instrument within a set is a distinct General MIDI sound without repeated program numbers.

---

## 4. Magic Pad Gestures & Controls (Apple Magic Trackpad 2)
- **Action 1 (LinnStrument MPE Grid Mode):**
  - Tocar notas en la superficie de 4x8 casillas isomorfas en cuartas.
  - Comprobar polifonía de hasta 4 notas simultáneas sin notas colgadas ni saturación de colas.
  - Modulación vertical: apertura progresiva de Cutoff (CC 74).
- **Action 2 (Theremin Glide Mode):**
  - Hacer **doble clic en la esquina derecha** para cambiar a Modo 2 (`THEREMIN`, marimba E5).
  - Colocar el dedo: suena melodía monofónica continua sin trastes a lo largo de 4 octavas.
  - Levantar el dedo: corte limpio sin colas residuales.
- **Action 3 (Kaoss Pad Lead Ribbon Mode):**
  - Hacer **doble clic derecho** para cambiar a Modo 3 (`KAOSS_PAD`, marimba G5).
  - Tocar solos rápidos con ribbon melódico horizontal de 2 octavas (notas 48 a 72) y modulación de filtro y vibrato en Y.
- **Action 4 (Vector Morpher Drone Mode):**
  - Hacer **doble clic derecho** para cambiar a Modo 4 (`VECTOR_MORPHER`, marimba B5).
  - Verificar sonido drone de quintas abiertas de 2 voces sin choque armónico.
  - Hacer **doble clic derecho adicional**: escuchar el golpe sordo de pared (*Wall Bump*) impidiendo ciclar fuera de rango.
- **Action 5 (Clics de Control y Volumen):**
  - Clic simple en esquina inferior izquierda / derecha: cambia preset instrumental emitiendo nota de previsualización (100ms) del propio instrumento.
  - Pulsación sostenida (>0.55s) en esquina derecha: sube volumen de forma fluida (+16 cada 110ms); en esquina izquierda: baja volumen.
  - Clic dual simultáneo (L+R): pánico instantáneo.
- **Action 6 (Auto-Reconexión & Chimes Bluetooth):**
  - Apagar el interruptor físico del trackpad: verificar arpegio descendente de marimba (G5 $\rightarrow$ E5 $\rightarrow$ C5).
  - Encender el interruptor: verificar reconexión automática en <3s y arpegio ascendente de marimba (C5 $\rightarrow$ E5 $\rightarrow$ G5).

---

## 5. 8-Track Quantized Live Looper
- **Action:** Hold **D1** (second white key from left):
  - **Pad 1:** Tap to ARM/RECORD beat 1. Tap again to close loop (auto-quantized to 16th-note boundary).
  - **Pad 2:** Toggle Re-Voice Lock (play a new instrument over the recorded track without changing the loop's sound).
  - **Pad 3:** Toggle Metronome tick.
  - **Pad 4:** Tap = Play/Pause | Hold $>1.5$s = Clear all 8 tracks.
  - **Pads 5..8:** Individual track mutes/deletes across Bank A (Tracks 1–4) and Bank B (Tracks 5–8).

