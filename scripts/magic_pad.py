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
Works via evdev or pure Linux input subsystem (/dev/input/event*).
"""

import os
import sys
import glob
import time
import struct
import socket
import threading
from typing import Optional, Dict, Tuple

FLUID_HOST = "localhost"
FLUID_PORT = 9800

# Input event binary structure in Linux (struct input_event: timeval (2 long), type (ushort), code (ushort), value (int))
# Standard 64-bit: 16 bytes time + 2 bytes type + 2 bytes code + 4 bytes value = 24 bytes
# Standard 32-bit: 8 bytes time + 2 bytes type + 2 bytes code + 4 bytes value = 16 bytes
EVENT_SIZE_64 = 24
EVENT_FORMAT_64 = "llHHi"
EVENT_SIZE_32 = 16
EVENT_FORMAT_32 = "iiHHi"

# EVDEV event codes
EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02
EV_ABS = 0x03

ABS_X = 0x00
ABS_Y = 0x01
ABS_MT_SLOT = 0x2f
ABS_MT_TOUCH_MAJOR = 0x30
ABS_MT_POSITION_X = 0x35
ABS_MT_POSITION_Y = 0x36
ABS_MT_TRACKING_ID = 0x39

BTN_TOUCH = 0x14a
BTN_TOOL_FINGER = 0x145
BTN_TOOL_DOUBLETAP = 0x14d
BTN_TOOL_TRIPLETAP = 0x14e
BTN_TOOL_QUADTAP = 0x14f


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
            self.sock.settimeout(1.0)
            self.sock.connect((self.host, self.port))
        except Exception:
            self.sock = None

    def send(self, cmd: str):
        with self.lock:
            if not self.sock:
                self.connect()
            if self.sock:
                try:
                    payload = (cmd.strip() + "\n").encode("utf-8")
                    self.sock.sendall(payload)
                except Exception:
                    self.sock = None


class MagicPadController:
    MODES = ["THEREMIN", "KAOSS_PAD", "VECTOR_MORPHER"]

    def __init__(self):
        self.fluid = FluidClient()
        self.current_mode_idx: int = 1  # Default: Kaoss Pad FX
        self.mode: str = self.MODES[self.current_mode_idx]
        self.running: bool = True

        # Multi-touch state
        self.active_slots: Dict[int, Dict[str, int]] = {}
        self.current_slot: int = 0
        self.touch_count: int = 0

        # Swipe tracking
        self.swipe_start_x: Optional[float] = None
        self.swipe_start_time: float = 0.0

        # Tap tracking for 3 fingers
        self.tripletap_press_time: float = 0.0

        # Calibration bounds
        self.min_x: int = 0
        self.max_x: int = 1920
        self.min_y: int = 0
        self.max_y: int = 1080

    def cycle_mode(self):
        self.current_mode_idx = (self.current_mode_idx + 1) % len(self.MODES)
        self.mode = self.MODES[self.current_mode_idx]
        print(f"\n[MAGIC PAD ✨] MODO CAMBIADO -> {self.mode}", flush=True)
        # Musical chime feedback
        if self.mode == "THEREMIN":
            self.fluid.send("prog 15 8\ncc 15 91 80\nnoteon 15 72 70\n")
            threading.Timer(0.1, lambda: self.fluid.send("noteoff 15 72")).start()
        elif self.mode == "KAOSS_PAD":
            self.fluid.send("prog 15 8\ncc 15 91 80\nnoteon 15 76 70\n")
            threading.Timer(0.1, lambda: self.fluid.send("noteoff 15 76")).start()
        elif self.mode == "VECTOR_MORPHER":
            self.fluid.send("prog 15 8\ncc 15 91 80\nnoteon 15 79 70\n")
            threading.Timer(0.1, lambda: self.fluid.send("noteoff 15 79")).start()

    def step_instrument(self, forward: bool = True):
        cmd = "cc 0 30 127" if forward else "cc 0 29 127"  # Corresponds to Pad CC forward/prev
        print(f"\n[MAGIC PAD 🖐 4-FINGER SWIPE] Instrumento -> {'SIGUIENTE ▶' if forward else 'ANTERIOR ◀'}", flush=True)
        # Notify FluidSynth & Akai controller through CC
        self.fluid.send(f"prog 15 8\ncc 15 91 80\nnoteon 15 {84 if forward else 60} 70")
        threading.Timer(0.08, lambda: self.fluid.send(f"noteoff 15 {84 if forward else 60}")).start()

    def process_touch_motion(self, norm_x: float, norm_y: float):
        """Processes normalized coordinates [0.0, 1.0] depending on active mode."""
        if self.mode == "KAOSS_PAD":
            # X-Axis -> Filter Cutoff (CC 74: 20 to 127)
            cutoff = int(20 + norm_x * 107)
            # Y-Axis -> Reverb / FX Splash (CC 91: 0 to 127)
            reverb = int((1.0 - norm_y) * 127)
            self.fluid.send(f"cc 0 74 {cutoff}\ncc 0 91 {reverb}\ncc 9 91 {reverb}")

        elif self.mode == "THEREMIN":
            # X-Axis -> Continuous Pitch Bend (+- 12 semitones around base note)
            # 0 to 16383 (8192 center)
            pb_val = int(norm_x * 16383)
            # Y-Axis -> Expression / Volume (CC 11 / CC 7: 40 to 127)
            expr = int(40 + (1.0 - norm_y) * 87)
            self.fluid.send(f"pitch_bend_range 0 12\npitch_bend 0 {pb_val}\ncc 0 11 {expr}")

        elif self.mode == "VECTOR_MORPHER":
            # X-Axis -> Stereo Pan (CC 10: 0 Left to 127 Right)
            pan = int(norm_x * 127)
            # Y-Axis -> Chorus Lush Depth (CC 93: 0 to 127)
            chorus = int((1.0 - norm_y) * 127)
            self.fluid.send(f"cc 0 10 {pan}\ncc 0 93 {chorus}")

    def find_touchpad_device(self) -> Optional[str]:
        # Search /dev/input/by-id or event devices with touch capabilities
        for p in glob.glob("/dev/input/event*"):
            try:
                # Test opening read-only non-blocking
                fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK)
                os.close(fd)
                # Check device name via sysfs
                dev_name_path = f"/sys/class/input/{os.path.basename(p)}/device/name"
                if os.path.exists(dev_name_path):
                    with open(dev_name_path, "r") as f:
                        name = f.read().lower()
                        if any(k in name for k in ["touchpad", "trackpad", "magic", "touch", "alps", "synaptics"]):
                            return p
            except Exception:
                continue
        # Fallback to mouse/event if available
        mouse_events = glob.glob("/dev/input/event*")
        return mouse_events[0] if mouse_events else None

    def run(self):
        print("==================================================================")
        print(" Magic Pad - Multi-Touch Expressive Gestural Controller          ")
        print("==================================================================")
        print(" • 3-Finger Tap: Ciclar Modos (Theremin / Kaoss Pad / Morpher)   ")
        print(" • 4-Finger Swipe (Izquierda -> Derecha): Siguiente Instrumento ")
        print(" • 4-Finger Swipe (Derecha -> Izquierda): Instrumento Anterior  ")
        print(" • X/Y Touch: Modulación continua y expresiva sin latencia       ")
        print("==================================================================")

        dev_path = self.find_touchpad_device()
        if not dev_path:
            print("[!] No se encontró touchpad o superficie táctil disponible. Entrando en modo espera...")
            return

        print(f"[+] Escuchando gestos táctiles en {dev_path}...")
        is_64bit = (struct.calcsize("l") == 8)
        event_size = EVENT_SIZE_64 if is_64bit else EVENT_SIZE_32
        event_fmt = EVENT_FORMAT_64 if is_64bit else EVENT_FORMAT_32

        try:
            with open(dev_path, "rb") as dev:
                current_x = self.max_x // 2
                current_y = self.max_y // 2

                while self.running:
                    data = dev.read(event_size)
                    if not data or len(data) < event_size:
                        time.sleep(0.005)
                        continue

                    _, _, ev_type, ev_code, ev_value = struct.unpack(event_fmt, data)

                    if ev_type == EV_KEY:
                        # 3-Finger Tap detection
                        if ev_code == BTN_TOOL_TRIPLETAP:
                            if ev_value == 1:
                                self.tripletap_press_time = time.time()
                            elif ev_value == 0:
                                if (time.time() - self.tripletap_press_time) < 0.45:
                                    self.cycle_mode()

                        # 4-Finger Swipe detection
                        elif ev_code == BTN_TOOL_QUADTAP:
                            if ev_value == 1:
                                self.swipe_start_x = current_x
                                self.swipe_start_time = time.time()
                            elif ev_value == 0 and self.swipe_start_x is not None:
                                dt = time.time() - self.swipe_start_time
                                dx = current_x - self.swipe_start_x
                                if dt < 0.8 and abs(dx) > (self.max_x * 0.15):
                                    if dx > 0:
                                        self.step_instrument(forward=True)
                                    else:
                                        self.step_instrument(forward=False)
                                self.swipe_start_x = None

                    elif ev_type == EV_ABS:
                        if ev_code in [ABS_X, ABS_MT_POSITION_X]:
                            current_x = ev_value
                        elif ev_code in [ABS_Y, ABS_MT_POSITION_Y]:
                            current_y = ev_value

                    elif ev_type == EV_SYN:
                        norm_x = max(0.0, min(1.0, (current_x - self.min_x) / max(1.0, float(self.max_x - self.min_x))))
                        norm_y = max(0.0, min(1.0, (current_y - self.min_y) / max(1.0, float(self.max_y - self.min_y))))
                        self.process_touch_motion(norm_x, norm_y)

        except PermissionError:
            print(f"[!] Permiso denegado para leer {dev_path}. Añade tu usuario al grupo 'input' (`sudo usermod -aG input $USER`).")
        except Exception as e:
            print(f"[-] Error en Magic Pad loop: {e}")


if __name__ == "__main__":
    controller = MagicPadController()
    controller.run()
