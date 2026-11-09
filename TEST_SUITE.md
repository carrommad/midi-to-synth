# Akai MPK Mini & Magic Pad Interactive Verification Test Suite

This test suite covers every hardware function, shortcut, instrument library, looper capability, and gestural trackpad mode implemented on the Raspberry Pi 3 standalone synth.

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

## 4. Magic Pad Gestures (Apple Magic Trackpad)
- **Action 1 (Theremin Glide Mode):**
  - Tap with **3 fingers** until log outputs `[MAGIC PAD ✨] MODO CAMBIADO -> THEREMIN`.
  - Place a finger down: sound triggers automatically.
  - Slide horizontally: smooth microtonal pitch-bend across 4 octaves ($\pm 24$ semitones).
  - Slide vertically: expression/volume swell (CC 11).
  - Lift finger: sound stops cleanly.
- **Action 2 (Kaoss Pad FX Mode):**
  - Tap with **3 fingers** to switch to `KAOSS_PAD`.
  - Play keyboard notes with right hand while sliding left hand on trackpad:
    - X-axis sweeps Low-Pass Filter Cutoff (CC 74 from dark muffled to bright open).
    - Y-axis swells Reverb & Chorus depth (CC 91 / CC 93 from dry to cathedral ambience).
- **Action 3 (Vector Morpher Mode):**
  - Tap with **3 fingers** to switch to `VECTOR_MORPHER`.
  - Move finger between the 4 corners: dynamically crossfades stereo panning and spatial presence.
- **Action 4 (4-Finger Swipes):**
  - Swipe with **4 fingers** left to right: steps to next instrument preset with soft preview chime.
  - Swipe with **4 fingers** right to left: steps to previous instrument preset.

---

## 5. 8-Track Quantized Live Looper
- **Action:** Hold **D1** (second white key from left):
  - **Pad 1:** Tap to ARM/RECORD beat 1. Tap again to close loop (auto-quantized to 16th-note boundary).
  - **Pad 2:** Toggle Re-Voice Lock (play a new instrument over the recorded track without changing the loop's sound).
  - **Pad 3:** Toggle Metronome tick.
  - **Pad 4:** Tap = Play/Pause | Hold $>1.5$s = Clear all 8 tracks.
  - **Pads 5..8:** Individual track mutes/deletes across Bank A (Tracks 1–4) and Bank B (Tracks 5–8).

