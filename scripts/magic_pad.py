#!/usr/bin/env python3
"""
Magic Pad Controller for Raspberry Pi & Linux Desktops
Translates multi-touch trackpad gestures into real-time expressive MIDI/FluidSynth controls:
  - 3-Finger Tap: Cycles operating mode
      * Mode 1: Theremin Glide (Continuous pitch + dynamic expression)
      * Mode 2: Kaoss Pad FX (X = CC 74 Filter Cutoff, Y = CC 91 Reverb / CC 93 Chorus)
      * Mode 3: 4-Corner Vector Morpher (Spatial balance & acoustic positioning)
  - 4-Finger Sweep:
      * Left -> Right: Next sound preset
      * Right -> Left: Previous sound preset
Built on python-evdev for high precision and immediate finger lift auto-silence.
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
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(0.5)
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


class MagicPadController:
    MODES = ["THEREMIN", "KAOSS_PAD", "VECTOR_MORPHER"]

    def __init__(self):
        self.fluid = FluidClient()
        self.current_mode_idx: int = 1  # Default: Kaoss Pad FX
        self.mode: str = self.MODES[self.current_mode_idx]
        self.running: bool = True

        # Multi-touch tracking
        self.active_slots: Dict[int, Dict[str, int]] = {}
        self.current_slot: int = 0
        self.fingers_on_pad: int = 0

        # Gestures
        self.swipe_start_x: Optional[float] = None
        self.swipe_start_time: float = 0.0
        self.tripletap_press_time: float = 0.0

        # Theremin state
        self.theremin_active: bool = False
        self.theremin_base_note: int = 60  # Middle C

        # Apple Magic Trackpad calibration bounds
        self.min_x: int = -3678
        self.max_x: int = 3934
        self.min_y: int = -2478
        self.max_y: int = 2587

    def cycle_mode(self):
        self.silence_theremin()
        self.current_mode_idx = (self.current_mode_idx + 1) % len(self.MODES)
        self.mode = self.MODES[self.current_mode_idx]
        print(f"\n[MAGIC PAD ✨] MODO CAMBIADO -> {self.mode}", flush=True)

        # Soft chime feedback
        pitch = 72 if self.mode == "THEREMIN" else (76 if self.mode == "KAOSS_PAD" else 79)
        self.fluid.send(f"prog 15 8\ncc 15 91 80\nnoteon 15 {pitch} 70\n")
        threading.Timer(0.1, lambda: self.fluid.send(f"noteoff 15 {pitch}")).start()

    def step_instrument(self, forward: bool = True):
        print(f"\n[MAGIC PAD 🖐 4-FINGER SWIPE] Instrumento -> {'SIGUIENTE ▶' if forward else 'ANTERIOR ◀'}", flush=True)
        pitch = 84 if forward else 60
        self.fluid.send(f"prog 15 8\ncc 15 91 80\nnoteon 15 {pitch} 70")
        threading.Timer(0.08, lambda: self.fluid.send(f"noteoff 15 {pitch}")).start()

    def silence_theremin(self):
        if self.theremin_active:
            self.theremin_active = False
            self.fluid.send(f"noteoff 0 {self.theremin_base_note}\ncc 0 120 0\ncc 0 123 0")

    def process_touch_motion(self, norm_x: float, norm_y: float):
        if self.mode == "KAOSS_PAD":
            cutoff = int(20 + norm_x * 107)
            reverb = int((1.0 - norm_y) * 127)
            self.fluid.send(f"cc 0 74 {cutoff}\ncc 0 91 {reverb}\ncc 9 91 {reverb}")

        elif self.mode == "THEREMIN":
            if not self.theremin_active:
                self.theremin_active = True
                self.fluid.send(f"pitch_bend_range 0 24\nnoteon 0 {self.theremin_base_note} 100")

            pb_val = int(norm_x * 16383)
            expr = int(30 + (1.0 - norm_y) * 97)
            self.fluid.send(f"pitch_bend 0 {pb_val}\ncc 0 11 {expr}")

        elif self.mode == "VECTOR_MORPHER":
            pan = int(norm_x * 127)
            chorus = int((1.0 - norm_y) * 127)
            self.fluid.send(f"cc 0 10 {pan}\ncc 0 93 {chorus}")

    def find_touchpad(self) -> Optional[evdev.InputDevice]:
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
                name = dev.name.lower()
                if any(k in name for k in ["magic trackpad", "touchpad", "trackpad", "apple"]):
                    caps = dev.capabilities()
                    if ecodes.EV_ABS in caps:
                        # Extract actual hardware axis bounds
                        abs_dict = dict(caps[ecodes.EV_ABS])
                        if ecodes.ABS_X in abs_dict:
                            self.min_x = abs_dict[ecodes.ABS_X].min
                            self.max_x = abs_dict[ecodes.ABS_X].max
                        if ecodes.ABS_Y in abs_dict:
                            self.min_y = abs_dict[ecodes.ABS_Y].min
                            self.max_y = abs_dict[ecodes.ABS_Y].max
                        return dev
            except Exception:
                continue
        return None

    def run(self):
        print("==================================================================")
        print(" Magic Pad - Multi-Touch Expressive Gestural Controller          ")
        print("==================================================================")
        print(" • 3-Finger Tap: Ciclar Modos (Theremin / Kaoss Pad / Morpher)   ")
        print(" • 4-Finger Swipe (Izquierda -> Derecha): Siguiente Instrumento ")
        print(" • 4-Finger Swipe (Derecha -> Izquierda): Instrumento Anterior  ")
        print(" • X/Y Touch: Modulación continua y expresiva sin latencia       ")
        print("==================================================================")

        device = self.find_touchpad()
        if not device:
            print("[!] No se encontró Apple Magic Trackpad en /dev/input/event*. Reintentando...")
            return

        print(f"[+] Conectado a {device.name} en {device.path} (X: [{self.min_x}..{self.max_x}], Y: [{self.min_y}..{self.max_y}])")

        current_x = (self.min_x + self.max_x) // 2
        current_y = (self.min_y + self.max_y) // 2

        try:
            for event in device.read_loop():
                if not self.running:
                    break

                if event.type == ecodes.EV_KEY:
                    if event.code == ecodes.BTN_TOUCH:
                        if event.value == 0:
                            # ALL touch contact released immediately
                            self.silence_theremin()
                    elif event.code == ecodes.BTN_TOOL_FINGER:
                        if event.value == 0 and self.fingers_on_pad <= 1:
                            self.silence_theremin()
                    elif event.code == ecodes.BTN_TOOL_TRIPLETAP:
                        if event.value == 1:
                            self.tripletap_press_time = time.time()
                        elif event.value == 0:
                            if (time.time() - self.tripletap_press_time) < 0.45:
                                self.cycle_mode()
                    elif event.code == ecodes.BTN_TOOL_QUADTAP:
                        if event.value == 1:
                            self.swipe_start_x = current_x
                            self.swipe_start_time = time.time()
                        elif event.value == 0 and self.swipe_start_x is not None:
                            dt = time.time() - self.swipe_start_time
                            dx = current_x - self.swipe_start_x
                            span = max(1, self.max_x - self.min_x)
                            if dt < 0.8 and abs(dx) > (span * 0.15):
                                self.step_instrument(forward=(dx > 0))
                            self.swipe_start_x = None

                elif event.type == ecodes.EV_ABS:
                    if event.code in [ecodes.ABS_X, ecodes.ABS_MT_POSITION_X]:
                        current_x = event.value
                    elif event.code in [ecodes.ABS_Y, ecodes.ABS_MT_POSITION_Y]:
                        current_y = event.value
                    elif event.code == ecodes.ABS_MT_SLOT:
                        self.current_slot = event.value
                    elif event.code == ecodes.ABS_MT_TRACKING_ID:
                        if event.value == -1:
                            # Finger lifted from this slot
                            self.active_slots.pop(self.current_slot, None)
                            if len(self.active_slots) == 0:
                                self.silence_theremin()
                        else:
                            self.active_slots[self.current_slot] = {"x": current_x, "y": current_y}

                elif event.type == ecodes.EV_SYN:
                    if event.code == ecodes.SYN_REPORT:
                        # If fingers are on pad, process motion
                        if len(self.active_slots) > 0 or self.theremin_active:
                            span_x = max(1.0, float(self.max_x - self.min_x))
                            span_y = max(1.0, float(self.max_y - self.min_y))
                            norm_x = max(0.0, min(1.0, (current_x - self.min_x) / span_x))
                            norm_y = max(0.0, min(1.0, (current_y - self.min_y) / span_y))
                            self.process_touch_motion(norm_x, norm_y)

        except Exception as e:
            print(f"[-] Error en Magic Pad: {e}")
        finally:
            self.silence_theremin()


if __name__ == "__main__":
    controller = MagicPadController()
    controller.run()
