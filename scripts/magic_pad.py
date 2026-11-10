#!/usr/bin/env python3
"""
Magic Pad Controller for Raspberry Pi 3B (LinnStrument MPE Expressive Grid).
Works seamlessly over USB with Apple Magic Trackpad:
  - Modes:
      * 1: LINNSTRUMENT (4 Rows x 8 Columns isomorphic fourths grid with MPE glide & timbre)
      * 2: THEREMIN (Continuous pitch bend glide on X, Expression on Y)
      * 3: KAOSS_PAD (X = Filter Cutoff CC 74, Y = Reverb CC 91)
      * 4: VECTOR_MORPHER (X = Pan CC 10, Y = Chorus CC 93)
  - 3-Finger Tap: Cycle Modes (LINNSTRUMENT -> THEREMIN -> KAOSS_PAD -> VECTOR_MORPHER)
  - 4-Finger Horizontal Swipe: Change Instrument Preset (Next / Previous)
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

# Lista de presets populares para el Magic Pad
MAGIC_PRESETS = [
    (80, "Square Lead Synth"),
    (81, "Sawtooth Lead Synth"),
    (88, "Warm Pad Synth"),
    (19, "Church Pipe Organ"),
    (4,  "Electric Piano"),
    (11, "Vibraphone"),
    (40, "Violin Strings"),
    (54, "Synth Voice Choir")
]


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

        # Gesto 3 dedos
        self.three_finger_start_time: float = 0.0
        self.three_finger_handled: bool = False

        # Gesto 4 dedos
        self.four_finger_start_x: Optional[float] = None
        self.four_finger_start_time: float = 0.0
        self.four_finger_handled: bool = False

        # Calibración bounds Apple Magic Trackpad
        self.min_x: int = -3678
        self.max_x: int = 3934
        self.min_y: int = -2478
        self.max_y: int = 2587

        # LinnStrument Matrix Tuning (4 Rows x 8 Columns):
        self.linn_base_notes = [40, 45, 50, 55]
        self.preset_idx = 0

        # Theremin state
        self.theremin_active = False

    def cycle_mode(self):
        self.all_notes_off()
        self.current_mode_idx = (self.current_mode_idx + 1) % len(self.MODES)
        self.mode = self.MODES[self.current_mode_idx]
        print(f"\n[MAGIC PAD ✨ 3-FINGER TAP] MODO CAMBIADO -> {self.mode}", flush=True)

        pitch = 72 if self.mode == "LINNSTRUMENT" else (76 if self.mode == "KAOSS_PAD" else (79 if self.mode == "THEREMIN" else 84))
        self.fluid.send(f"prog 15 8\ncc 15 91 80\nnoteon 15 {pitch} 85\n")
        threading.Timer(0.12, lambda: self.fluid.send(f"noteoff 15 {pitch}")).start()

    def change_preset(self, forward: bool = True):
        self.all_notes_off()
        if forward:
            self.preset_idx = (self.preset_idx + 1) % len(MAGIC_PRESETS)
        else:
            self.preset_idx = (self.preset_idx - 1) % len(MAGIC_PRESETS)

        prog_num, name = MAGIC_PRESETS[self.preset_idx]
        self.fluid.send(f"prog {MAGIC_PAD_MIDI_CHANNEL} {prog_num}")
        print(f"\n[MAGIC PAD 🖐 4-FINGER SWIPE] Sonido -> #{prog_num} {name}", flush=True)

        pitch = 84 if forward else 60
        self.fluid.send(f"prog 15 8\ncc 15 91 80\nnoteon 15 {pitch} 75\n")
        threading.Timer(0.08, lambda: self.fluid.send(f"noteoff 15 {pitch}")).start()

    def all_notes_off(self):
        for slot, note in list(self.active_notes.items()):
            self.fluid.send(f"noteoff {MAGIC_PAD_MIDI_CHANNEL} {note}")
        self.fluid.send(f"pitch_bend {MAGIC_PAD_MIDI_CHANNEL} 8192")
        self.active_notes.clear()
        self.slots.clear()
        self.theremin_active = False

    def process_touches(self):
        num_fingers = len(self.slots)

        # -------------------------------------------------------------
        # 1. DETECCIÓN DE GESTOS GLOBALES (3 y 4 dedos)
        # -------------------------------------------------------------
        if num_fingers == 3:
            now = time.time()
            if self.three_finger_start_time == 0.0:
                self.three_finger_start_time = now
                self.three_finger_handled = False
            elif not self.three_finger_handled and (now - self.three_finger_start_time) < 0.4:
                # Tap rápido detectado
                pass
            return

        elif num_fingers >= 4:
            now = time.time()
            # Promedio de X para detectar swipe
            avg_x = sum(s.get('x', 0) for s in self.slots.values()) / max(1, num_fingers)
            if self.four_finger_start_x is None:
                self.four_finger_start_x = avg_x
                self.four_finger_start_time = now
                self.four_finger_handled = False
            elif not self.four_finger_handled and (now - self.four_finger_start_time) < 0.8:
                delta_x = avg_x - self.four_finger_start_x
                if abs(delta_x) > 1200:  # Desplazamiento claro
                    self.four_finger_handled = True
                    self.change_preset(forward=(delta_x > 0))
            return

        # -------------------------------------------------------------
        # 2. PROCESAMIENTO SEGÚN MODO ACTIVO (1 y 2 dedos)
        # -------------------------------------------------------------
        if self.mode == "LINNSTRUMENT":
            for slot_id in list(self.slots.keys()):
                self.process_linnstrument_slot(slot_id)

        elif self.mode == "THEREMIN":
            first_slot = next(iter(self.slots.values()), None)
            if first_slot and 'x' in first_slot and 'y' in first_slot:
                norm_x = max(0.0, min(1.0, (first_slot['x'] - self.min_x) / (self.max_x - self.min_x)))
                norm_y = max(0.0, min(1.0, (first_slot['y'] - self.min_y) / (self.max_y - self.min_y)))
                if not self.theremin_active:
                    self.theremin_active = True
                    self.fluid.send(f"pitch_bend_range {MAGIC_PAD_MIDI_CHANNEL} 24\nnoteon {MAGIC_PAD_MIDI_CHANNEL} 60 100")
                pb_val = int(norm_x * 16383)
                expr = int(30 + (1.0 - norm_y) * 97)
                self.fluid.send(f"pitch_bend {MAGIC_PAD_MIDI_CHANNEL} {pb_val}\ncc {MAGIC_PAD_MIDI_CHANNEL} 11 {expr}")

        elif self.mode == "KAOSS_PAD":
            first_slot = next(iter(self.slots.values()), None)
            if first_slot and 'x' in first_slot and 'y' in first_slot:
                norm_x = max(0.0, min(1.0, (first_slot['x'] - self.min_x) / (self.max_x - self.min_x)))
                norm_y = max(0.0, min(1.0, (first_slot['y'] - self.min_y) / (self.max_y - self.min_y)))
                cutoff = int(20 + norm_x * 107)
                reverb = int((1.0 - norm_y) * 127)
                self.fluid.send(f"cc {MAGIC_PAD_MIDI_CHANNEL} 74 {cutoff}\ncc {MAGIC_PAD_MIDI_CHANNEL} 91 {reverb}\ncc 0 74 {cutoff}\ncc 0 91 {reverb}")

        elif self.mode == "VECTOR_MORPHER":
            first_slot = next(iter(self.slots.values()), None)
            if first_slot and 'x' in first_slot and 'y' in first_slot:
                norm_x = max(0.0, min(1.0, (first_slot['x'] - self.min_x) / (self.max_x - self.min_x)))
                norm_y = max(0.0, min(1.0, (first_slot['y'] - self.min_y) / (self.max_y - self.min_y)))
                pan = int(norm_x * 127)
                chorus = int((1.0 - norm_y) * 127)
                self.fluid.send(f"cc {MAGIC_PAD_MIDI_CHANNEL} 10 {pan}\ncc {MAGIC_PAD_MIDI_CHANNEL} 93 {chorus}\ncc 0 10 {pan}")

    def process_linnstrument_slot(self, slot_id: int):
        slot = self.slots.get(slot_id)
        if not slot:
            return

        x = slot.get('x', 0)
        y = slot.get('y', 0)
        pressure = slot.get('pressure', 60)

        norm_x = max(0.0, min(1.0, (x - self.min_x) / (self.max_x - self.min_x)))
        norm_y = max(0.0, min(1.0, (y - self.min_y) / (self.max_y - self.min_y)))

        col = max(0, min(7, int(norm_x * 8)))
        row = max(0, min(3, int((1.0 - norm_y) * 4)))
        target_note = self.linn_base_notes[row] + col
        vel = max(30, min(127, int(pressure * 1.4)))

        if not slot.get('active', False):
            slot['active'] = True
            slot['note'] = target_note
            slot['base_x'] = x
            slot['base_y'] = y
            self.active_notes[slot_id] = target_note
            self.fluid.send(f"noteon {MAGIC_PAD_MIDI_CHANNEL} {target_note} {vel}")
            print(f"[LINNSTRUMENT] Nota: {target_note} (Fila {row+1}, Col {col+1}) Vel: {vel}", flush=True)
        else:
            delta_x = x - slot.get('base_x', x)
            pb = int(8192 + (delta_x / 300.0) * 4096)
            pb = max(0, min(16383, pb))
            cutoff = int(40 + (1.0 - norm_y) * 87)
            self.fluid.send(f"pitch_bend {MAGIC_PAD_MIDI_CHANNEL} {pb}\ncc {MAGIC_PAD_MIDI_CHANNEL} 74 {cutoff}")

    def release_slot(self, slot_id: int):
        if slot_id in self.active_notes:
            note = self.active_notes.pop(slot_id)
            self.fluid.send(f"noteoff {MAGIC_PAD_MIDI_CHANNEL} {note}\npitch_bend {MAGIC_PAD_MIDI_CHANNEL} 8192")
        if slot_id in self.slots:
            del self.slots[slot_id]

        # Si se levantaron los dedos y había 3 dedos en pantalla: confirmar Tap
        if len(self.slots) == 0:
            now = time.time()
            if self.three_finger_start_time > 0 and (now - self.three_finger_start_time) < 0.45:
                self.cycle_mode()
            self.three_finger_start_time = 0.0
            self.three_finger_handled = False
            self.four_finger_start_x = None
            self.four_finger_start_time = 0.0
            self.four_finger_handled = False

            if self.theremin_active:
                self.theremin_active = False
                self.fluid.send(f"noteoff {MAGIC_PAD_MIDI_CHANNEL} 60\ncc {MAGIC_PAD_MIDI_CHANNEL} 120 0\ncc {MAGIC_PAD_MIDI_CHANNEL} 123 0")

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
        print(" • 3-Finger Tap: Cycle Modes (LinnStrument/Theremin/Kaoss/Vector) ", flush=True)
        print(" • 4-Finger Swipe: Next/Prev Instrument Sound Preset             ", flush=True)
        print("==================================================================", flush=True)

        self.fluid.connect()
        init_prog, init_name = MAGIC_PRESETS[0]
        self.fluid.send(f"prog {MAGIC_PAD_MIDI_CHANNEL} {init_prog}\ncc {MAGIC_PAD_MIDI_CHANNEL} 7 120\ncc {MAGIC_PAD_MIDI_CHANNEL} 91 50\n")

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
                time.sleep(2.0)


if __name__ == "__main__":
    controller = MagicPadLinnstrumentController()
    controller.run()
