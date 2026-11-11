#!/usr/bin/env python3
"""
Magic Pad Controller for Raspberry Pi 3B (LinnStrument MPE Expressive Grid).
Works seamlessly over Bluetooth / USB with Apple Magic Trackpad 2:
  - Modes (Bounded Linear Navigation: Linn <-> Theremin <-> Kaoss <-> Vector):
      * 1: LINNSTRUMENT (4 Rows x 8 Columns isomorphic fourths grid with MPE glide & timbre)
      * 2: THEREMIN (Continuous pitch bend glide on X, Expression on Y)
      * 3: KAOSS_PAD (X = Filter Cutoff CC 74, Y = Reverb CC 91)
      * 4: VECTOR_MORPHER (X = Pan CC 10, Y = Chorus CC 93)
  - Tactile Click Controls:
      * Single Click Left / Right: Previous / Next Sound Preset
      * Double Click Left / Right: Previous / Next Mode (Bounded with 'Wall' audio bump)
      * Long Press Left (>0.6s): Volume Down (with auto-repeat)
      * Long Press Right (>0.6s): Volume Up (with auto-repeat)
      * Dual Click (L+R together): Silence all audio (Panic)
"""

import os
import sys
import time
import socket
import threading
from typing import Optional, Dict

import evdev
from evdev import ecodes

FLUID_HOST = "localhost"
FLUID_PORT = 9800

MAGIC_PAD_MIDI_CHANNEL = 2

# 16 Curated Instrument Presets for LinnStrument Mode
LINNSTRUMENT_PRESETS = [
    (88, "Synth Pad 1 (Warm Analog Pad)"),
    (89, "Synth Pad 2 (Polysynth Warmth)"),
    (80, "Synth Lead 1 (Square Wave)"),
    (81, "Synth Lead 2 (Sawtooth Wave)"),
    (2,  "Electric Piano (Rhodes MK1)"),
    (4,  "Electric Piano 2 (FM DX7)"),
    (11, "Vibraphone (Jazz Vibes)"),
    (12, "Marimba Resonant"),
    (24, "Nylon Spanish Guitar (Flamenco)"),
    (26, "Jazz Electric Archtop Guitar"),
    (40, "Solo Violin Soloist"),
    (42, "Solo Cello Resonant"),
    (48, "String Ensemble 1 (Orchestral)"),
    (54, "Synth Voice (Ooohs & Aaahs)"),
    (19, "Church Pipe Organ Majestic"),
    (16, "Drawbar Organ (Hammond B3)")
]

# 8 Curated Continuous Presets for Theremin Mode
THEREMIN_PRESETS = [
    (80, "Theremin Sine / Pure Lead"),
    (78, "Whistle Folk / Pan Flute"),
    (77, "Shakuhachi Bamboo Flute"),
    (42, "Expressive Solo Cello"),
    (40, "Solo Violin Vibrato"),
    (81, "Sawtooth Lead Solo"),
    (95, "Space Atmosphere Dark Synth"),
    (82, "Calliope Synth Lead")
]

# 8 Curated Presets for Kaoss Ribbon Lead Mode
KAOSS_PRESETS = [
    (81, "Lead Sawtooth Kaossilator"),
    (80, "Lead Square 8-Bit"),
    (87, "Lead Bass+Lead Distorted"),
    (84, "Lead Charang Rock Synth"),
    (29, "Overdriven Guitar Solo"),
    (30, "Distortion Guitar Lead"),
    (82, "Calliope Lead Arcade"),
    (90, "Polysynth Lead Brite")
]

# 8 Curated Presets for Vector Chord Drone Mode
VECTOR_PRESETS = [
    (88, "Warm Analog Pad"),
    (89, "Polysynth Warm Strings"),
    (91, "Space Choir / Voice Pad"),
    (92, "Bowed Glass Atmosphere"),
    (94, "Halo Pad Celestial"),
    (95, "Sweep Pad Cosmic"),
    (48, "String Ensemble Orchestral"),
    (54, "Synth Voice (Aah Pad)")
]


# Factores de compensación de ganancia por programa MIDI en la SoundFont:
# Estandariza la sonoridad acústica percibida para que órganos y sintes estridentes
# no suenen desproporcionadamente más fuertes que guitarras, pianos o cuerdas.
PROGRAM_GAIN_TRIM: Dict[int, float] = {
    # Órganos (alta energía sostenida sin capas de velocidad): atenuar a 58%
    16: 0.58,  # Drawbar Organ
    19: 0.55,  # Church Pipe Organ
    # Guitarras eléctricas saturadas: atenuar a 55%
    29: 0.55,  # Overdriven Guitar
    30: 0.55,  # Distortion Guitar
    # Sintetizadores Lead digitales (ondas cuadradas/sierra plenas): atenuar a 65%
    80: 0.65,  # Synth Lead Square
    81: 0.65,  # Synth Lead Sawtooth
    82: 0.65,  # Calliope Lead
    84: 0.60,  # Charang Rock Lead
    87: 0.60,  # Bass + Lead Distorted
    90: 0.65,  # Polysynth Lead
    # Instrumentos acústicos de cuerda pulsada (menor energía RMS): realzar a 135%
    24: 1.35,  # Nylon Spanish Guitar
    26: 1.30,  # Jazz Electric Guitar
    # Percusión melódica y pianos: realzar pianos acústicos/eléctricos
    2:  1.25,  # Rhodes MK1
    4:  1.20,  # FM DX7
    11: 1.10,  # Vibraphone
    12: 1.10,  # Marimba
    # Cuerdas y vientos solo
    40: 1.25,  # Violin
    42: 1.25,  # Cello
    77: 1.20,  # Shakuhachi
    78: 1.20,  # Whistle / Pan Flute
    # Conjuntos y coros
    48: 1.00,  # String Ensemble
    54: 1.05,  # Synth Voice
    # Pads atmosféricos
    88: 1.15,  # Synth Pad 1 Warm
    89: 1.15,  # Synth Pad 2 Polysynth
    91: 1.10,  # Space Choir
    92: 1.10,  # Bowed Glass
    94: 1.10,  # Halo Pad
    95: 1.05,  # Sweep Pad
}


class FluidClient:
    def __init__(self, host: str = FLUID_HOST, port: int = FLUID_PORT):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.lock = threading.Lock()

    def connect(self):
        try:
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.settimeout(0.5)
            self.sock.connect((self.host, self.port))
        except Exception:
            self.sock = None

    def send(self, cmd: str):
        with self.lock:
            try:
                if not self.sock:
                    self.connect()
                if self.sock:
                    payload = (cmd.strip() + "\n").encode("utf-8")
                    self.sock.sendall(payload)
            except Exception:
                self.connect()
                if self.sock:
                    try:
                        payload = (cmd.strip() + "\n").encode("utf-8")
                        self.sock.sendall(payload)
                    except Exception:
                        pass


class MagicPadLinnstrumentController:
    MODES = ["LINNSTRUMENT", "THEREMIN", "KAOSS_PAD", "VECTOR_MORPHER"]

    def __init__(self):
        self.fluid = FluidClient()
        self.current_mode_idx: int = 0  # Default: LINNSTRUMENT
        self.mode: str = self.MODES[self.current_mode_idx]
        self.running: bool = True

        self.slots: Dict[int, Dict] = {}
        self.current_slot: int = 0
        self.active_notes: Dict[int, int] = {}

        # Volume state for Magic Pad (Channel 2)
        # Nivel normal por defecto al encender / iniciar sesión (60% de 127 = 76)
        self.DEFAULT_SESSION_VOLUME: int = 76
        self.current_volume: int = self.DEFAULT_SESSION_VOLUME

        # Click handling state
        self.click_press_time: float = 0.0
        self.last_click_side: Optional[str] = None
        self.last_click_time: float = 0.0
        self.pending_single_click_timer: Optional[threading.Timer] = None
        self.volume_hold_timer: Optional[threading.Timer] = None
        self.volume_hold_active: bool = False

        # Octave shifting state (-2, -1, 0, +1, +2):
        self.octave_shift: int = 0

        # Gesture tracking for 4-finger lateral swipes
        self.gesture_start_x: Optional[float] = None
        self.gesture_start_time: float = 0.0
        self.gesture_processed: bool = False

        # Calibración bounds Apple Magic Trackpad 2
        self.min_x: int = -3678
        self.max_x: int = 3934
        self.min_y: int = -2478
        self.max_y: int = 2587

        # LinnStrument Matrix Tuning (4 Rows x 8 Columns):
        self.linn_base_notes = [40, 45, 50, 55]
        self.linn_preset_idx = 0
        self.theremin_preset_idx = 0
        self.kaoss_preset_idx = 0
        self.vector_preset_idx = 0

        # State tracking for continuous modes
        self.theremin_active = False
        self.kaoss_active = False
        self.kaoss_current_note: Optional[int] = None
        self.vector_active = False
        self.vector_current_notes: list = []

        # Throttling & deduplicación de eventos para evitar saturar el parser TCP de FluidSynth
        self.last_mod_time: float = 0.0
        self.last_sent_cc: Dict[int, int] = {}

        # Supresión de notas musicales durante clics físicos de control
        self.is_button_down: bool = False
        self.last_touch_x: float = 0.0
        self.last_touch_y: float = 0.0

    def get_current_preset_list(self):
        if self.mode == "THEREMIN":
            return THEREMIN_PRESETS
        elif self.mode == "KAOSS_PAD":
            return KAOSS_PRESETS
        elif self.mode == "VECTOR_MORPHER":
            return VECTOR_PRESETS
        return LINNSTRUMENT_PRESETS

    def get_function_sound_volume(self, base_percentage: float = 0.65) -> tuple:
        """Calcula el volumen CC 7 y la velocidad para los sonidos de función/menú
        como un porcentaje proporcional estricto del volumen actual del pad."""
        ratio = self.current_volume / 127.0
        cc_vol = max(10, min(120, int(ratio * base_percentage * 127)))
        vel = max(15, min(100, int(ratio * base_percentage * 110)))
        return cc_vol, vel

    def play_wall_sound(self):
        """Sonido elegante de 'tope / pared': golpe percusivo suave y amortiguado (Woodblock/Muted Taiko)."""
        print(f"\n[MAGIC PAD 🛑 TOPE/PARED] Límite de modos alcanzado ({self.mode}).", flush=True)
        # Volumen proporcional al volumen actual del pad
        fb_vol, fb_vel = self.get_function_sound_volume(base_percentage=0.70)
        self.fluid.send(f"prog 15 115\ncc 15 7 {fb_vol}\ncc 15 91 35\nnoteon 15 44 {fb_vel}\n")
        threading.Timer(0.06, lambda: self.fluid.send("noteoff 15 44")).start()

    def play_connect_sound(self):
        """Chime acústico elegante al conectarse el Magic Trackpad:
        Arpegio suave ascendente de marimba de concierto (C5 -> E5 -> G5)."""
        print(f"\n[MAGIC PAD 🔔 CONECTADO] Emitiendo chime acústico de conexión.", flush=True)
        fb_vol, fb_vel = self.get_function_sound_volume(base_percentage=0.75)
        self.fluid.send(f"prog 15 12\ncc 15 7 {fb_vol}\ncc 15 91 50\n")
        
        def _chime():
            notes = [72, 76, 79]  # C5, E5, G5
            for note in notes:
                self.fluid.send(f"noteon 15 {note} {fb_vel}\n")
                time.sleep(0.08)
                self.fluid.send(f"noteoff 15 {note}\n")
        
        threading.Thread(target=_chime, daemon=True).start()

    def play_disconnect_sound(self):
        """Chime acústico sutil al desconectarse el Magic Trackpad:
        Arpegio suave descendente de marimba de concierto (G5 -> E5 -> C5)."""
        print(f"\n[MAGIC PAD 🔕 DESCONECTADO] Emitiendo chime de desconexión.", flush=True)
        fb_vol, fb_vel = self.get_function_sound_volume(base_percentage=0.65)
        self.fluid.send(f"prog 15 12\ncc 15 7 {fb_vol}\ncc 15 91 40\n")
        
        def _chime():
            notes = [79, 76, 72]  # G5, E5, C5
            for note in notes:
                self.fluid.send(f"noteon 15 {note} {fb_vel}\n")
                time.sleep(0.08)
                self.fluid.send(f"noteoff 15 {note}\n")
        
        threading.Thread(target=_chime, daemon=True).start()

    def get_current_prog_number(self) -> int:
        """Devuelve el número de programa MIDI activo actualmente según el modo."""
        presets = self.get_current_preset_list()
        if self.mode == "THEREMIN":
            return presets[self.theremin_preset_idx][0]
        elif self.mode == "KAOSS_PAD":
            return presets[self.kaoss_preset_idx][0]
        elif self.mode == "VECTOR_MORPHER":
            return presets[self.vector_preset_idx][0]
        return presets[self.linn_preset_idx][0]

    def apply_current_mode_volume(self):
        """Aplica el volumen compensado acústicamente tanto por la arquitectura del modo
        como por el factor de calibración tímbrica del instrumento específico (SoundFont)."""
        prog_num = self.get_current_prog_number()
        inst_trim = PROGRAM_GAIN_TRIM.get(prog_num, 1.0)

        if self.mode == "LINNSTRUMENT":
            # 1 a 3 notas polifónicas: 100% de current_volume * trim
            vol = int(self.current_volume * 1.00 * inst_trim)
        elif self.mode == "THEREMIN":
            # 1 voz senoidal continua: 90% de current_volume * trim
            vol = int(self.current_volume * 0.90 * inst_trim)
        elif self.mode == "KAOSS_PAD":
            # 1 voz lead brillante: 85% de current_volume * trim
            vol = int(self.current_volume * 0.85 * inst_trim)
        elif self.mode == "VECTOR_MORPHER":
            # 2 voces simultáneas (acorde drone quintas): 65% de current_volume * trim
            vol = int(self.current_volume * 0.65 * inst_trim)
        else:
            vol = int(self.current_volume * inst_trim)

        vol = max(0, min(127, vol))
        self.fluid.send(f"cc {MAGIC_PAD_MIDI_CHANNEL} 7 {vol}")

    def change_octave(self, up: bool = True):
        """Transpone las octavas del Magic Trackpad entre 5 niveles (-2 a +2).
        Derecha a Izquierda (<-) = Sube octava (+1).
        Izquierda a Derecha (->) = Baja octava (-1)."""
        if up:
            if self.octave_shift >= 2:
                self.play_wall_sound()
                return
            self.octave_shift += 1
        else:
            if self.octave_shift <= -2:
                self.play_wall_sound()
                return
            self.octave_shift -= 1

        self.all_notes_off()
        sign = f"+{self.octave_shift}" if self.octave_shift > 0 else str(self.octave_shift)
        print(f"\n[MAGIC PAD 🖐️🖐️ SWIPE 4 DEDOS] Octava -> {sign} ({'Agudo' if up else 'Grave'})", flush=True)

        # Chime acústico suave indicando el cambio de octava
        fb_vol, fb_vel = self.get_function_sound_volume(base_percentage=0.60)
        chime_note = 72 + self.octave_shift * 12
        chime_note = max(24, min(108, chime_note))
        self.fluid.send(f"prog 15 12\ncc 15 7 {fb_vol}\ncc 15 91 40\nnoteon 15 {chime_note} {fb_vel}\n")
        threading.Timer(0.10, lambda: self.fluid.send(f"noteoff 15 {chime_note}")).start()

    def change_mode(self, forward: bool = True):
        # NAVEGACIÓN ESTRICTAMENTE ACOTADA (No cíclica):
        # Mode 1 (LINNSTRUMENT) <-> Mode 2 (THEREMIN) <-> Mode 3 (KAOSS_PAD) <-> Mode 4 (VECTOR_MORPHER)
        if forward:
            if self.current_mode_idx >= len(self.MODES) - 1:
                self.play_wall_sound()
                return
            self.current_mode_idx += 1
        else:
            if self.current_mode_idx <= 0:
                self.play_wall_sound()
                return
            self.current_mode_idx -= 1

        self.all_notes_off()
        self.mode = self.MODES[self.current_mode_idx]
        print(f"\n[MAGIC PAD 🖱️ DOUBLE-CLICK {'RIGHT' if forward else 'LEFT'}] MODO -> {self.mode}", flush=True)

        # Aplicar el preset activo del nuevo modo
        if self.mode == "LINNSTRUMENT":
            prog, name = LINNSTRUMENT_PRESETS[self.linn_preset_idx]
            self.fluid.send(f"prog {MAGIC_PAD_MIDI_CHANNEL} {prog}")
        elif self.mode == "THEREMIN":
            prog, name = THEREMIN_PRESETS[self.theremin_preset_idx]
            self.fluid.send(f"prog {MAGIC_PAD_MIDI_CHANNEL} {prog}")
        elif self.mode == "KAOSS_PAD":
            prog, name = KAOSS_PRESETS[self.kaoss_preset_idx]
            self.fluid.send(f"prog {MAGIC_PAD_MIDI_CHANNEL} {prog}")
        elif self.mode == "VECTOR_MORPHER":
            prog, name = VECTOR_PRESETS[self.vector_preset_idx]
            self.fluid.send(f"prog {MAGIC_PAD_MIDI_CHANNEL} {prog}")

        # Aplicar el volumen compensado al nuevo modo seleccionado
        self.apply_current_mode_volume()

        # Feedback elegante de cambio de modo: Gota / Marimba acústica sutil (Prog 12)
        # Notas armónicas ascendentes según el modo: C5 (72), E5 (76), G5 (79), B5 (83)
        mode_tones = [72, 76, 79, 83]
        pitch = mode_tones[self.current_mode_idx]
        fb_vol, fb_vel = self.get_function_sound_volume(base_percentage=0.60)
        self.fluid.send(f"prog 15 12\ncc 15 7 {fb_vol}\ncc 15 91 50\nnoteon 15 {pitch} {fb_vel}\n")
        threading.Timer(0.09, lambda: self.fluid.send(f"noteoff 15 {pitch}")).start()

    def change_preset(self, forward: bool = True):
        self.all_notes_off()
        presets = self.get_current_preset_list()
        if self.mode == "THEREMIN":
            if forward:
                self.theremin_preset_idx = (self.theremin_preset_idx + 1) % len(presets)
            else:
                self.theremin_preset_idx = (self.theremin_preset_idx - 1) % len(presets)
            prog_num, name = presets[self.theremin_preset_idx]
        elif self.mode == "KAOSS_PAD":
            if forward:
                self.kaoss_preset_idx = (self.kaoss_preset_idx + 1) % len(presets)
            else:
                self.kaoss_preset_idx = (self.kaoss_preset_idx - 1) % len(presets)
            prog_num, name = presets[self.kaoss_preset_idx]
        elif self.mode == "VECTOR_MORPHER":
            if forward:
                self.vector_preset_idx = (self.vector_preset_idx + 1) % len(presets)
            else:
                self.vector_preset_idx = (self.vector_preset_idx - 1) % len(presets)
            prog_num, name = presets[self.vector_preset_idx]
        else:
            if forward:
                self.linn_preset_idx = (self.linn_preset_idx + 1) % len(presets)
            else:
                self.linn_preset_idx = (self.linn_preset_idx - 1) % len(presets)
            prog_num, name = presets[self.linn_preset_idx]

        self.fluid.send(f"prog {MAGIC_PAD_MIDI_CHANNEL} {prog_num}")
        self.apply_current_mode_volume()
        print(f"\n[MAGIC PAD 🖱️ CLICK {'RIGHT' if forward else 'LEFT'}] Sonido ({self.mode}) -> #{prog_num} {name}", flush=True)

        # Previsualización acústica elegante con el propio instrumento seleccionado:
        # Toca una nota corta y sutil (Do central o La agudo según dirección) en el propio canal
        preview_pitch = 69 if forward else 60
        fb_vol, fb_vel = self.get_function_sound_volume(base_percentage=0.60)
        self.fluid.send(f"noteon {MAGIC_PAD_MIDI_CHANNEL} {preview_pitch} {fb_vel}\n")
        threading.Timer(0.10, lambda: self.fluid.send(f"noteoff {MAGIC_PAD_MIDI_CHANNEL} {preview_pitch}")).start()

    def adjust_volume(self, step: int):
        self.current_volume = max(0, min(127, self.current_volume + step))
        pct = int((self.current_volume / 127.0) * 100)
        self.apply_current_mode_volume()
        print(f"\n[MAGIC PAD 🔊 VOLUMEN SESIÓN] Nivel maestro: {pct}% (Base: {self.current_volume}/127)", flush=True)

        # Micro-click de feedback de volumen: intensidad y volumen proporcionales al nivel actual
        vol_tone = 72 if step > 0 else 60
        fb_vol, fb_vel = self.get_function_sound_volume(base_percentage=0.65)
        self.fluid.send(f"prog 15 115\ncc 15 7 {fb_vol}\nnoteon 15 {vol_tone} {fb_vel}\n")
        threading.Timer(0.04, lambda: self.fluid.send(f"noteoff 15 {vol_tone}")).start()

    def panic_silence(self):
        """Silenciar de inmediato todas las notas y efectos del Magic Pad."""
        self.all_notes_off()
        self.fluid.send(
            f"cc {MAGIC_PAD_MIDI_CHANNEL} 120 0\n"
            f"cc {MAGIC_PAD_MIDI_CHANNEL} 123 0\n"
            f"cc {MAGIC_PAD_MIDI_CHANNEL} 64 0\n"
            f"pitch_bend {MAGIC_PAD_MIDI_CHANNEL} 8192\n"
        )
        print("\n[MAGIC PAD 🛑 PANIC] SILENCIO TOTAL ACTIVADO (Panic Ch 2).", flush=True)
        # Chime seco de confirmación adaptado al volumen
        fb_vol, fb_vel = self.get_function_sound_volume(base_percentage=0.60)
        self.fluid.send(f"prog 15 8\ncc 15 7 {fb_vol}\ncc 15 91 0\nnoteon 15 60 {fb_vel}\n")
        threading.Timer(0.06, lambda: self.fluid.send("noteoff 15 60")).start()

    def all_notes_off(self):
        """Silenciar notas activas sin emitir el chime de pánico."""
        for slot, note in list(self.active_notes.items()):
            self.fluid.send(f"noteoff {MAGIC_PAD_MIDI_CHANNEL} {note}")
        self.fluid.send(
            f"noteoff {MAGIC_PAD_MIDI_CHANNEL} 60\n"
            f"pitch_bend {MAGIC_PAD_MIDI_CHANNEL} 8192\n"
            f"cc {MAGIC_PAD_MIDI_CHANNEL} 64 0\n"
            f"cc {MAGIC_PAD_MIDI_CHANNEL} 7 {self.current_volume}\n"
            f"cc {MAGIC_PAD_MIDI_CHANNEL} 11 127\n"
            f"cc {MAGIC_PAD_MIDI_CHANNEL} 120 0\n"
            f"cc {MAGIC_PAD_MIDI_CHANNEL} 123 0"
        )
        self.active_notes.clear()
        # Limpiar flags de estado para que no queden notas colgadas
        for slot in self.slots.values():
            slot['active'] = False
        self.theremin_active = False
        self.kaoss_active = False
        self.kaoss_current_note = None
        self.vector_active = False
        self.vector_current_notes = []

    def handle_click_down(self):
        now = time.time()
        self.click_press_time = now
        self.is_button_down = True
        self.all_notes_off()
        self.volume_hold_active = False

        # Guardar coordenadas de contacto del clic
        xs = [s.get('x', 0) for s in self.slots.values() if 'x' in s]
        if xs:
            self.last_touch_x = sum(xs) / len(xs)
        ys = [s.get('y', 0) for s in self.slots.values() if 'y' in s]
        if ys:
            self.last_touch_y = sum(ys) / len(ys)

        # Comprobar si hay dos dedos en extremos opuestos (Dual Click Panic)
        has_left = any(x < -500 for x in xs)
        has_right = any(x > 500 for x in xs)
        if (has_left and has_right) or len(self.slots) >= 3:
            if self.pending_single_click_timer:
                self.pending_single_click_timer.cancel()
                self.pending_single_click_timer = None
            self.panic_silence()
            return

        side = "RIGHT" if self.last_touch_x >= 0 else "LEFT"

        # Ajustar volumen en pasos suaves (+/- 8) con auto-repeat ralentizado a 300ms
        def _volume_hold_loop():
            self.volume_hold_active = True
            if self.pending_single_click_timer:
                self.pending_single_click_timer.cancel()
                self.pending_single_click_timer = None

            # Leer la posición real dinámica en el momento de la pulsación
            current_side = "RIGHT" if self.last_touch_x >= 0 else "LEFT"
            step = 8 if current_side == "RIGHT" else -8
            self.adjust_volume(step)

            # Auto-repeat mientras se mantenga presionado
            while self.volume_hold_active and self.running:
                time.sleep(0.30)
                if not self.volume_hold_active:
                    break
                current_side = "RIGHT" if self.last_touch_x >= 0 else "LEFT"
                step = 8 if current_side == "RIGHT" else -8
                self.adjust_volume(step)

        self.volume_hold_timer = threading.Timer(0.55, _volume_hold_loop)
        self.volume_hold_timer.daemon = True
        self.volume_hold_timer.start()

    def handle_click_up(self):
        now = time.time()
        # Detener la repetición de volumen si estaba activa
        self.volume_hold_active = False
        if self.volume_hold_timer:
            self.volume_hold_timer.cancel()
            self.volume_hold_timer = None

        # Periodo de gracia (120ms) tras soltar el botón antes de permitir nuevas notas táctiles
        def _clear_button_flag():
            self.is_button_down = False
        threading.Timer(0.12, _clear_button_flag).start()

        press_duration = now - self.click_press_time
        if press_duration >= 0.55:
            # Ya fue procesado por el bucle de ajuste de volumen
            return

        # Determinar si el click ocurrió en el lado izquierdo o derecho usando last_touch_x registrado
        xs = [s.get('x', 0) for s in self.slots.values() if 'x' in s]
        if xs:
            self.last_touch_x = sum(xs) / len(xs)
        side = "RIGHT" if self.last_touch_x >= 0 else "LEFT"

        # Detección de Doble Click vs Click Simple (ventana de 350ms):
        time_since_last = now - self.last_click_time
        if self.last_click_side == side and time_since_last < 0.35:
            # DOBLE CLICK CONFIRMADO -> CAMBIO DE MODO
            if self.pending_single_click_timer:
                self.pending_single_click_timer.cancel()
                self.pending_single_click_timer = None
            self.last_click_time = 0.0
            self.last_click_side = None
            self.change_mode(forward=(side == "RIGHT"))
        else:
            # CLICK SIMPLE CANDIDATO -> Esperar 320ms por si llega el segundo click
            if self.pending_single_click_timer:
                self.pending_single_click_timer.cancel()

            self.last_click_side = side
            self.last_click_time = now

            def _execute_single_click(target_side: str):
                self.change_preset(forward=(target_side == "RIGHT"))
                self.last_click_side = None
                self.last_click_time = 0.0

            self.pending_single_click_timer = threading.Timer(0.32, _execute_single_click, args=[side])
            self.pending_single_click_timer.daemon = True
            self.pending_single_click_timer.start()

    def is_in_click_corner(self, norm_x: float, norm_y: float) -> bool:
        """Silenciar exclusivamente un pequeño cuadro de ~1 cm² en las esquinas inferiores
        izquierda y derecha del Magic Trackpad (16.0 cm ancho x 11.5 cm alto).
        Toda la superficie restante permanece 100% activa para tocar."""
        if norm_y > 0.90:
            if norm_x < 0.09 or norm_x > 0.91:
                return True
        return False

    def process_touches(self):
        # Bloquear cualquier disparo de notas mientras se está pulsando un clic físico de control
        if self.is_button_down:
            return

        # -------------------------------------------------------------
        # 1. DETECCIÓN DE GESTO: SWIPE LATERAL DE 4 DEDOS (OCTAVAS)
        # -------------------------------------------------------------
        active_slots_with_coords = [s for s in self.slots.values() if 'x' in s and 'y' in s]
        num_fingers = len(active_slots_with_coords)

        if num_fingers >= 4:
            avg_x = sum(s['x'] for s in active_slots_with_coords) / num_fingers
            now = time.time()
            if self.gesture_start_x is None:
                self.gesture_start_x = avg_x
                self.gesture_start_time = now
                self.gesture_processed = False
            else:
                delta_x = avg_x - self.gesture_start_x
                elapsed = now - self.gesture_start_time
                # Umbral de desplazamiento de swipe (> 1200 unidades en trackpad)
                if not self.gesture_processed and elapsed < 0.6:
                    if delta_x < -1200:
                        # Derecha a Izquierda (<-): Sube octava
                        self.change_octave(up=True)
                        self.gesture_processed = True
                    elif delta_x > 1200:
                        # Izquierda a Derecha (->): Baja octava
                        self.change_octave(up=False)
                        self.gesture_processed = True
            return
        else:
            self.gesture_start_x = None
            self.gesture_processed = False

        # -------------------------------------------------------------
        # PROCESAMIENTO SEGÚN MODO ACTIVO (Superficie 100% pura para tocar)
        # -------------------------------------------------------------
        if self.mode == "LINNSTRUMENT":
            for slot_id in list(self.slots.keys()):
                self.process_linnstrument_slot(slot_id)

        elif self.mode == "THEREMIN":
            first_slot = next(iter(self.slots.values()), None)
            if first_slot and 'x' in first_slot and 'y' in first_slot:
                norm_x = max(0.0, min(1.0, (first_slot['x'] - self.min_x) / (self.max_x - self.min_x)))
                norm_y = max(0.0, min(1.0, (first_slot['y'] - self.min_y) / (self.max_y - self.min_y)))
                if self.is_in_click_corner(norm_x, norm_y):
                    return
                # Theremin: centro en C5 (nota 72) + octave_shift * 12
                center_pitch = max(24, min(96, 60 + self.octave_shift * 12))
                pb_val = int(norm_x * 16383)
                # Eje Y: Filtro cutoff/brillo y modulación, manteniendo CC 11 en rango audible pleno
                inst_trim = PROGRAM_GAIN_TRIM.get(self.get_current_prog_number(), 1.0)
                theremin_vol = int(self.current_volume * 0.90 * inst_trim)
                expr = int(70 + (1.0 - norm_y) * 57)
                cutoff = int(35 + (1.0 - norm_y) * 92)
                if not self.theremin_active:
                    self.theremin_active = True
                    self.fluid.send(
                        f"pitch_bend_range {MAGIC_PAD_MIDI_CHANNEL} 24\n"
                        f"pitch_bend {MAGIC_PAD_MIDI_CHANNEL} {pb_val}\n"
                        f"cc {MAGIC_PAD_MIDI_CHANNEL} 7 {theremin_vol}\n"
                        f"cc {MAGIC_PAD_MIDI_CHANNEL} 11 {expr}\n"
                        f"cc {MAGIC_PAD_MIDI_CHANNEL} 74 {cutoff}\n"
                        f"noteon {MAGIC_PAD_MIDI_CHANNEL} {center_pitch} 88"
                    )
                else:
                    self.fluid.send(
                        f"pitch_bend {MAGIC_PAD_MIDI_CHANNEL} {pb_val}\n"
                        f"cc {MAGIC_PAD_MIDI_CHANNEL} 7 {theremin_vol}\n"
                        f"cc {MAGIC_PAD_MIDI_CHANNEL} 11 {expr}\n"
                        f"cc {MAGIC_PAD_MIDI_CHANNEL} 74 {cutoff}"
                    )

        elif self.mode == "KAOSS_PAD":
            first_slot = next(iter(self.slots.values()), None)
            if first_slot and 'x' in first_slot and 'y' in first_slot:
                norm_x = max(0.0, min(1.0, (first_slot['x'] - self.min_x) / (self.max_x - self.min_x)))
                norm_y = max(0.0, min(1.0, (first_slot['y'] - self.min_y) / (self.max_y - self.min_y)))
                if self.is_in_click_corner(norm_x, norm_y):
                    return
                # Escala cromática / pentatónica rápida (2 octavas: notas base 48 + octave_shift*12 a +24)
                base_kaoss = max(24, min(96, 48 + self.octave_shift * 12))
                target_note = int(base_kaoss + norm_x * 24)
                cutoff = int(30 + (1.0 - norm_y) * 97)
                mod_depth = int((1.0 - norm_y) * 127)
                inst_trim = PROGRAM_GAIN_TRIM.get(self.get_current_prog_number(), 1.0)
                kaoss_vol = int(self.current_volume * 0.85 * inst_trim)

                now = time.time()
                if not self.kaoss_active:
                    self.kaoss_active = True
                    self.kaoss_current_note = target_note
                    self.last_sent_cc = {7: kaoss_vol, 74: cutoff, 1: mod_depth}
                    self.last_mod_time = now
                    self.fluid.send(
                        f"cc {MAGIC_PAD_MIDI_CHANNEL} 7 {kaoss_vol}\n"
                        f"cc {MAGIC_PAD_MIDI_CHANNEL} 74 {cutoff}\n"
                        f"cc {MAGIC_PAD_MIDI_CHANNEL} 1 {mod_depth}\n"
                        f"noteon {MAGIC_PAD_MIDI_CHANNEL} {target_note} 82"
                    )
                else:
                    if self.kaoss_current_note != target_note:
                        old_note = self.kaoss_current_note
                        self.kaoss_current_note = target_note
                        # Disparo con transición suave Legato (noteon antes de noteoff para evitar vacío acústico)
                        self.fluid.send(
                            f"noteon {MAGIC_PAD_MIDI_CHANNEL} {target_note} 78\n"
                            f"noteoff {MAGIC_PAD_MIDI_CHANNEL} {old_note}"
                        )
                    # Throttling de modulación continua (35 Hz máx y solo si el valor CC ha cambiado)
                    if now - self.last_mod_time >= 0.028:
                        cc_cmds = []
                        if self.last_sent_cc.get(74) != cutoff:
                            self.last_sent_cc[74] = cutoff
                            cc_cmds.append(f"cc {MAGIC_PAD_MIDI_CHANNEL} 74 {cutoff}")
                        if self.last_sent_cc.get(1) != mod_depth:
                            self.last_sent_cc[1] = mod_depth
                            cc_cmds.append(f"cc {MAGIC_PAD_MIDI_CHANNEL} 1 {mod_depth}")
                        if cc_cmds:
                            self.last_mod_time = now
                            self.fluid.send("\n".join(cc_cmds))

        elif self.mode == "VECTOR_MORPHER":
            first_slot = next(iter(self.slots.values()), None)
            if first_slot and 'x' in first_slot and 'y' in first_slot:
                norm_x = max(0.0, min(1.0, (first_slot['x'] - self.min_x) / (self.max_x - self.min_x)))
                norm_y = max(0.0, min(1.0, (first_slot['y'] - self.min_y) / (self.max_y - self.min_y)))
                if self.is_in_click_corner(norm_x, norm_y):
                    return
                # Acordes abiertos / Pad etéreo de 2 voces (Fundamental + Quinta armónica) adaptados a octave_shift:
                root_offsets = [0, 2, 4, 5, 7, 9, 11, 12]
                chord_idx = max(0, min(7, int(norm_x * 8)))
                base_root = max(24, min(84, 48 + self.octave_shift * 12))
                root = base_root + root_offsets[chord_idx]
                target_chord = [root, root + 7]

                pan = int(norm_x * 127)
                chorus = int((1.0 - norm_y) * 127)
                expr = int(60 + (1.0 - norm_y) * 67)
                inst_trim = PROGRAM_GAIN_TRIM.get(self.get_current_prog_number(), 1.0)
                vector_vol = int(self.current_volume * 0.65 * inst_trim)

                now = time.time()
                if not self.vector_active:
                    self.vector_active = True
                    self.vector_current_notes = target_chord
                    self.last_sent_cc = {7: vector_vol, 10: pan, 93: chorus, 11: expr}
                    self.last_mod_time = now
                    # Inicializar CC 72 (Release time) a un valor musical controlado (55)
                    cmds = [
                        f"cc {MAGIC_PAD_MIDI_CHANNEL} 72 55",
                        f"cc {MAGIC_PAD_MIDI_CHANNEL} 7 {vector_vol}",
                        f"cc {MAGIC_PAD_MIDI_CHANNEL} 10 {pan}",
                        f"cc {MAGIC_PAD_MIDI_CHANNEL} 93 {chorus}",
                        f"cc {MAGIC_PAD_MIDI_CHANNEL} 11 {expr}"
                    ]
                    for n in target_chord:
                        cmds.append(f"noteon {MAGIC_PAD_MIDI_CHANNEL} {n} 65")
                    self.fluid.send("\n".join(cmds))
                else:
                    if self.vector_current_notes != target_chord:
                        old_notes = self.vector_current_notes
                        self.vector_current_notes = target_chord
                        # Apagar notas viejas y disparar nuevas de inmediato sin solapamiento destructivo
                        cmds = []
                        for n in old_notes:
                            cmds.append(f"noteoff {MAGIC_PAD_MIDI_CHANNEL} {n}")
                        for n in target_chord:
                            cmds.append(f"noteon {MAGIC_PAD_MIDI_CHANNEL} {n} 60")
                        self.fluid.send("\n".join(cmds))

                    # Throttling de modulación continua para Vector Morpher (35 Hz máx y solo cambios reales)
                    if now - self.last_mod_time >= 0.028:
                        cc_cmds = []
                        if self.last_sent_cc.get(10) != pan:
                            self.last_sent_cc[10] = pan
                            cc_cmds.append(f"cc {MAGIC_PAD_MIDI_CHANNEL} 10 {pan}")
                        if self.last_sent_cc.get(93) != chorus:
                            self.last_sent_cc[93] = chorus
                            cc_cmds.append(f"cc {MAGIC_PAD_MIDI_CHANNEL} 93 {chorus}")
                        if self.last_sent_cc.get(11) != expr:
                            self.last_sent_cc[11] = expr
                            cc_cmds.append(f"cc {MAGIC_PAD_MIDI_CHANNEL} 11 {expr}")
                        if cc_cmds:
                            self.last_mod_time = now
                            self.fluid.send("\n".join(cc_cmds))

    def process_linnstrument_slot(self, slot_id: int):
        slot = self.slots.get(slot_id)
        if not slot or 'x' not in slot or 'y' not in slot:
            return

        x = slot['x']
        y = slot['y']
        pressure = slot.get('pressure', 60)

        norm_x = max(0.0, min(1.0, (x - self.min_x) / (self.max_x - self.min_x)))
        norm_y = max(0.0, min(1.0, (y - self.min_y) / (self.max_y - self.min_y)))

        # ZONAS MUERTAS EXCLUSIVAS EN ESQUINAS INFERIORES:
        # Solo las esquinas de clic quedan silenciadas; el resto de la superficie (incluyendo el centro inferior) suena libremente.
        if self.is_in_click_corner(norm_x, norm_y):
            return

        col = max(0, min(7, int(norm_x * 8)))
        row = max(0, min(3, int((1.0 - norm_y) * 4)))
        base_octave_offset = self.octave_shift * 12
        target_note = max(12, min(120, self.linn_base_notes[row] + col + base_octave_offset))
        vel = max(35, min(127, int(pressure * 1.5)))

        if not slot.get('active', False):
            # Limitar polifonía máxima simultánea a 4 voces para evitar saturación acústica por notas apiladas
            if len(self.active_notes) >= 4:
                oldest_slot = next(iter(self.active_notes.keys()))
                old_note = self.active_notes.pop(oldest_slot)
                self.fluid.send(f"noteoff {MAGIC_PAD_MIDI_CHANNEL} {old_note}")
                if oldest_slot in self.slots:
                    self.slots[oldest_slot]['active'] = False

            slot['active'] = True
            slot['note'] = target_note
            slot['base_x'] = x
            slot['base_y'] = y
            slot['last_pb'] = 8192
            slot['last_cutoff'] = 64
            slot['last_mod_time'] = 0.0
            self.active_notes[slot_id] = target_note
            self.fluid.send(f"noteon {MAGIC_PAD_MIDI_CHANNEL} {target_note} {vel}")
            print(f"[LINNSTRUMENT] Nota: {target_note} (Fila {row+1}, Col {col+1}) Vel: {vel}", flush=True)
        else:
            # Si el dedo se desplaza más de 1 casilla entera (columna o fila diferente), re-disparar nota limpiamente
            if slot.get('note') != target_note:
                old_note = slot['note']
                slot['note'] = target_note
                slot['base_x'] = x
                slot['base_y'] = y
                self.active_notes[slot_id] = target_note
                self.fluid.send(
                    f"noteoff {MAGIC_PAD_MIDI_CHANNEL} {old_note}\n"
                    f"noteon {MAGIC_PAD_MIDI_CHANNEL} {target_note} {vel}\n"
                    f"pitch_bend {MAGIC_PAD_MIDI_CHANNEL} 8192"
                )
            else:
                # Throttling de pitch bend y cutoff a 40 Hz por dedo (máximo cada 25ms y solo con cambios audibles)
                now = time.time()
                if now - slot.get('last_mod_time', 0.0) >= 0.025:
                    delta_x = x - slot.get('base_x', x)
                    pb = int(8192 + (delta_x / 300.0) * 4096)
                    pb = max(0, min(16383, pb))
                    cutoff = int(40 + (1.0 - norm_y) * 87)

                    cmds = []
                    if abs(pb - slot.get('last_pb', 8192)) > 64:
                        slot['last_pb'] = pb
                        cmds.append(f"pitch_bend {MAGIC_PAD_MIDI_CHANNEL} {pb}")
                    if abs(cutoff - slot.get('last_cutoff', 64)) > 2:
                        slot['last_cutoff'] = cutoff
                        cmds.append(f"cc {MAGIC_PAD_MIDI_CHANNEL} 74 {cutoff}")

                    if cmds:
                        slot['last_mod_time'] = now
                        self.fluid.send("\n".join(cmds))

    def release_slot(self, slot_id: int):
        if slot_id in self.active_notes:
            note = self.active_notes.pop(slot_id)
            self.fluid.send(f"noteoff {MAGIC_PAD_MIDI_CHANNEL} {note}\npitch_bend {MAGIC_PAD_MIDI_CHANNEL} 8192")
        if slot_id in self.slots:
            del self.slots[slot_id]

        if len(self.slots) == 0:
            if self.theremin_active:
                self.theremin_active = False
                self.fluid.send(
                    f"noteoff {MAGIC_PAD_MIDI_CHANNEL} 60\n"
                    f"cc {MAGIC_PAD_MIDI_CHANNEL} 7 {self.current_volume}\n"
                    f"cc {MAGIC_PAD_MIDI_CHANNEL} 11 127\n"
                    f"pitch_bend {MAGIC_PAD_MIDI_CHANNEL} 8192\n"
                    f"cc {MAGIC_PAD_MIDI_CHANNEL} 123 0"
                )
            if self.kaoss_active:
                self.kaoss_active = False
                if self.kaoss_current_note is not None:
                    self.fluid.send(f"noteoff {MAGIC_PAD_MIDI_CHANNEL} {self.kaoss_current_note}\ncc {MAGIC_PAD_MIDI_CHANNEL} 1 0")
                    self.kaoss_current_note = None
            if self.vector_active:
                self.vector_active = False
                cmds = []
                for n in self.vector_current_notes:
                    cmds.append(f"noteoff {MAGIC_PAD_MIDI_CHANNEL} {n}")
                self.vector_current_notes = []
                if cmds:
                    self.fluid.send("\n".join(cmds))

    def find_touchpad(self) -> Optional[evdev.InputDevice]:
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
                if any(k in dev.name.lower() for k in ("magic trackpad", "trackpad", "touchpad")):
                    return dev
            except Exception:
                pass
        return None

    def run(self):
        print("==================================================================", flush=True)
        print(" Magic Pad - LinnStrument MPE Expressive Grid Controller         ", flush=True)
        print(" • Single Click Left / Right: Previous / Next Sound Preset       ", flush=True)
        print(" • Double Click Left / Right: Prev / Next Mode (With Wall Bump)  ", flush=True)
        print(" • Long Press Click Left / Right: Volume Down / Volume Up        ", flush=True)
        print(" • Dual Click (L+R together): Silence All Audio (Panic)          ", flush=True)
        print("==================================================================", flush=True)

        self.fluid.connect()
        init_prog, init_name = LINNSTRUMENT_PRESETS[0]
        self.fluid.send(f"prog {MAGIC_PAD_MIDI_CHANNEL} {init_prog}\ncc {MAGIC_PAD_MIDI_CHANNEL} 7 {self.current_volume}\ncc {MAGIC_PAD_MIDI_CHANNEL} 91 50\n")

        while self.running:
            dev = self.find_touchpad()
            if not dev:
                time.sleep(2.0)
                continue

            print(f"[+] Magic Trackpad detectado y listo: {dev.name} ({dev.path})", flush=True)
            self.play_connect_sound()
            try:
                for ev in dev.read_loop():
                    if ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_LEFT:
                        if ev.value == 1:
                            self.handle_click_down()
                        elif ev.value == 0:
                            self.handle_click_up()

                    elif ev.type == ecodes.EV_ABS:
                        if ev.code == ecodes.ABS_MT_SLOT:
                            self.current_slot = ev.value
                        elif ev.code == ecodes.ABS_MT_POSITION_X:
                            if self.current_slot not in self.slots:
                                self.slots[self.current_slot] = {}
                            self.slots[self.current_slot]['x'] = ev.value
                            self.last_touch_x = ev.value
                        elif ev.code == ecodes.ABS_MT_POSITION_Y:
                            if self.current_slot not in self.slots:
                                self.slots[self.current_slot] = {}
                            self.slots[self.current_slot]['y'] = ev.value
                            self.last_touch_y = ev.value
                        elif ev.code == ecodes.ABS_MT_PRESSURE:
                            if self.current_slot not in self.slots:
                                self.slots[self.current_slot] = {}
                            self.slots[self.current_slot]['pressure'] = ev.value
                        elif ev.code in (ecodes.ABS_X, ecodes.ABS_Y, ecodes.ABS_PRESSURE):
                            # Ignorar coordenadas emuladas globales mono-touch del puntero
                            pass
                        elif ev.code == ecodes.ABS_MT_TRACKING_ID:
                            if ev.value == -1:
                                self.release_slot(self.current_slot)
                            else:
                                if self.current_slot not in self.slots:
                                    self.slots[self.current_slot] = {}
                                self.slots[self.current_slot]['tracking_id'] = ev.value

                    elif ev.type == ecodes.EV_SYN and ev.code == ecodes.SYN_REPORT:
                        self.process_touches()

            except Exception as e:
                print(f"[-] Reconectando: {e}", flush=True)
                self.all_notes_off()
                self.play_disconnect_sound()
                time.sleep(2.0)


if __name__ == "__main__":
    controller = MagicPadLinnstrumentController()
    controller.run()
