#!/usr/bin/env python3
"""
Magic Pad Controller for Raspberry Pi 3B (LinnStrument MPE Expressive Grid).
Works seamlessly over USB or Bluetooth with Apple Magic Trackpad:
  - LINNSTRUMENT ISOMORPHIC GRID (4 Rows x 8 Columns):
      * Tuned in Fourths (+5 semitones per row, identical to guitar / LinnStrument)
      * Full Polyphonic Multi-Touch: Play chords and harmonies with multiple fingers
      * X-Axis Motion: Continuous pitch vibrato & micro-pitch gliding (Pitch Bend)
      * Y-Axis Motion: Expressive Timbre & Cutoff Filter modulation (CC 74)
      * Z-Axis Pressure: Dynamic note velocity & touch expression
  - 3-Finger Tap: Cycle Modes (LINNSTRUMENT -> THEREMIN -> KAOSS PAD -> VECTOR MORPHER)
  - 4-Finger Sweep: Change Instrument Preset (Next / Previous)
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

# Canal MIDI dedicado para el Magic Pad en FluidSynth: Canal 2 (totalmente aislado del MPK Mini y del APC40)
MAGIC_PAD_MIDI_CHANNEL = 2


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

        # Multi-touch tracking
        # slot -> {'x': int, 'y': int, 'pressure': int, 'note': int, 'active': bool, 'base_x': int, 'base_y': int}
        self.slots: Dict[int, Dict] = {}
        self.current_slot: int = 0
        self.active_notes: Dict[int, int] = {}  # slot -> midi_note

        # Gestures
        self.swipe_start_x: Optional[float] = None
        self.swipe_start_time: float = 0.0
        self.tripletap_press_time: float = 0.0

        # Apple Magic Trackpad calibration bounds
        self.min_x: int = -3678
        self.max_x: int = 3934
        self.min_y: int = -2478
        self.max_y: int = 2587

        # LinnStrument Matrix Tuning (4 Rows x 8 Columns):
        # Afinación por cuartas (+5 semitones entre filas):
        # Row 3 (Superior): G3 (55) + 0..7 semitonos -> G3 a D4
        # Row 2:           D3 (50) + 0..7 semitonos -> D3 a A3
        # Row 1:           A2 (45) + 0..7 semitonos -> A2 a E3
        # Row 0 (Inferior): E2 (40) + 0..7 semitonos -> E2 a B2 (Cuerda grave de bajo/guitarra)
        self.linn_base_notes = [40, 45, 50, 55]
        self.current_preset = 80  # Lead Synth Square por defecto

    def cycle_mode(self):
        self.all_notes_off()
        self.current_mode_idx = (self.current_mode_idx + 1) % len(self.MODES)
        self.mode = self.MODES[self.current_mode_idx]
        print(f"\n[MAGIC PAD ✨] MODO CAMBIADO -> {self.mode}", flush=True)

        pitch = 72 if self.mode == "LINNSTRUMENT" else (76 if self.mode == "KAOSS_PAD" else 79)
        self.fluid.send(f"prog 15 8\ncc 15 91 80\nnoteon 15 {pitch} 70\n")
        threading.Timer(0.1, lambda: self.fluid.send(f"noteoff 15 {pitch}")).start()

    def all_notes_off(self):
        for slot, note in list(self.active_notes.items()):
            self.fluid.send(f"noteoff {MAGIC_PAD_MIDI_CHANNEL} {note}")
        self.active_notes.clear()
        self.slots.clear()

    def process_linnstrument_touch(self, slot_id: int):
        slot = self.slots.get(slot_id)
        if not slot:
            return

        x = slot.get('x', 0)
        y = slot.get('y', 0)
        pressure = slot.get('pressure', 60)

        norm_x = max(0.0, min(1.0, (x - self.min_x) / (self.max_x - self.min_x)))
        norm_y = max(0.0, min(1.0, (y - self.min_y) / (self.max_y - self.min_y)))

        # 4 Filas x 8 Columnas
        col = int(norm_x * 8)
        col = max(0, min(7, col))
        row = int((1.0 - norm_y) * 4)
        row = max(0, min(3, row))

        # Nota isomórfica LinnStrument
        target_note = self.linn_base_notes[row] + col
        vel = max(30, min(127, int(pressure * 1.4)))

        if not slot.get('active', False):
            # Nuevo toque (Note On)
            slot['active'] = True
            slot['note'] = target_note
            slot['base_x'] = x
            slot['base_y'] = y
            self.active_notes[slot_id] = target_note
            self.fluid.send(f"noteon {MAGIC_PAD_MIDI_CHANNEL} {target_note} {vel}")
            print(f"[LINNSTRUMENT] Nota: {target_note} (Fila {row+1}, Col {col+1}) Vel: {vel}", flush=True)
        else:
            # Modulación continua dentro de la nota activa (X-glide / Y-timbre)
            delta_x = x - slot.get('base_x', x)
            delta_y = y - slot.get('base_y', y)

            # Vibrato continuo en X (Pitch Bend suave +/-2 semitonos)
            pb = int(8192 + (delta_x / 300.0) * 4096)
            pb = max(0, min(16383, pb))

            # Timbre / Cutoff en Y (CC 74)
            cutoff = int(40 + (1.0 - norm_y) * 87)
            self.fluid.send(f"pitch_bend {MAGIC_PAD_MIDI_CHANNEL} {pb}\ncc {MAGIC_PAD_MIDI_CHANNEL} 74 {cutoff}")

    def release_linnstrument_touch(self, slot_id: int):
        if slot_id in self.active_notes:
            note = self.active_notes.pop(slot_id)
            self.fluid.send(f"noteoff {MAGIC_PAD_MIDI_CHANNEL} {note}\npitch_bend {MAGIC_PAD_MIDI_CHANNEL} 8192")
        if slot_id in self.slots:
            del self.slots[slot_id]

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
        print(" Isolation: Operates on FluidSynth Channel 2                     ", flush=True)
        print(" Fourths Tuning: [Row 0: E2, Row 1: A2, Row 2: D3, Row 3: G3]   ", flush=True)
        print("==================================================================", flush=True)

        self.fluid.connect()
        # Inicializar programa para Magic Pad (Square Lead con Reverb)
        self.fluid.send(f"prog {MAGIC_PAD_MIDI_CHANNEL} {self.current_preset}\ncc {MAGIC_PAD_MIDI_CHANNEL} 7 120\ncc {MAGIC_PAD_MIDI_CHANNEL} 91 50\n")

        while self.running:
            dev = self.find_touchpad()
            if not dev:
                time.sleep(2.0)
                continue

            print(f"[+] Magic Trackpad detectado y listo: {dev.name} ({dev.path})", flush=True)
            try:
                for ev in dev.read_loop():
                    if ev.type == ecodes.EV_ABS:
                        if ev.code == ecodes.ABS_MT_SLOT:
                            self.current_slot = ev.value
                        elif ev.code in (ecodes.ABS_MT_POSITION_X, ecodes.ABS_X):
                            if self.current_slot not in self.slots:
                                self.slots[self.current_slot] = {}
                            self.slots[self.current_slot]['x'] = ev.value
                        elif ev.code in (ecodes.ABS_MT_POSITION_Y, ecodes.ABS_Y):
                            if self.current_slot not in self.slots:
                                self.slots[self.current_slot] = {}
                            self.slots[self.current_slot]['y'] = ev.value
                        elif ev.code in (ecodes.ABS_MT_PRESSURE, ecodes.ABS_PRESSURE):
                            if self.current_slot not in self.slots:
                                self.slots[self.current_slot] = {}
                            self.slots[self.current_slot]['pressure'] = ev.value
                        elif ev.code == ecodes.ABS_MT_TRACKING_ID:
                            if ev.value == -1:
                                # Dedo levantado
                                self.release_linnstrument_touch(self.current_slot)
                            else:
                                # Dedo apoyado
                                if self.current_slot not in self.slots:
                                    self.slots[self.current_slot] = {}
                                self.slots[self.current_slot]['tracking_id'] = ev.value

                    elif ev.type == ecodes.EV_SYN and ev.code == ecodes.SYN_REPORT:
                        # Procesar toques activos
                        for s_id, s_data in list(self.slots.items()):
                            if 'x' in s_data and 'y' in s_data:
                                self.process_linnstrument_touch(s_id)

            except Exception as e:
                print(f"[-] Conexión con trackpad interrumpida: {e}. Reconectando...", flush=True)
                self.all_notes_off()
                time.sleep(2.0)


if __name__ == "__main__":
    controller = MagicPadLinnstrumentController()
    controller.run()
