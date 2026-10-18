#!/usr/bin/env python3
"""
Headless MIDI Knob Controller for Akai MPK Mini MK2.
Allows changing keyboard instruments and drum kits using physical rotary knobs (No screen needed!).
Includes audio preview clicks/notes as you turn the knob.
"""

import time
import socket
import threading
from typing import Optional
import mido

FLUID_HOST = "localhost"
FLUID_PORT = 9800

# 16 Curated Keyboard Instruments (Mapped to Knob 1: CC 70 or CC 1)
KEYBOARD_INSTRUMENTS = [
    (0, "Yamaha Grand Piano"),
    (2, "Electric Piano (Rhodes)"),
    (16, "Drawbar Organ (Hammond)"),
    (19, "Church Pipe Organ"),
    (24, "Nylon Acoustic Guitar"),
    (27, "Clean Electric Guitar"),
    (33, "Fingered Electric Bass"),
    (38, "Synth Bass 1 (Sub / 808 Bass)"),
    (39, "Synth Bass 2 (Acid / Resonant)"),
    (48, "String Ensemble"),
    (50, "Synth Strings"),
    (56, "Trumpet"),
    (62, "Synth Brass"),
    (80, "Lead 1 (Square Wave)"),
    (81, "Lead 2 (Sawtooth Wave)"),
    (88, "Warm Synth Pad"),
]

# 8 Curated Drum Kits (Mapped to Knob 2: CC 71 or CC 2)
DRUM_KITS = [
    (0, "Standard Drum Kit"),
    (8, "Room / Rock Kit"),
    (16, "Power Heavy Kit"),
    (24, "Electronic Kit (909 / Techno)"),
    (25, "Roland TR-808 Kit"),
    (32, "Jazz Drum Kit"),
    (40, "Brush Drum Kit"),
    (48, "Orchestra Percussion Kit"),
]

def send_fluid_command(cmd: str):
    """Send command to FluidSynth via TCP server socket."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect((FLUID_HOST, FLUID_PORT))
            s.sendall((cmd + "\n").encode("utf-8"))
    except Exception:
        pass

def play_preview_note(chan: int, note: int, vel: int = 90, duration: float = 0.12):
    """Play a short preview sound so the player hears what was selected without a screen."""
    def _worker():
        send_fluid_command(f"noteon {chan} {note} {vel}")
        time.sleep(duration)
        send_fluid_command(f"noteoff {chan} {note}")
    threading.Thread(target=_worker, daemon=True).start()

class KnobController:
    def __init__(self):
        self.current_key_idx: Optional[int] = None
        self.current_drum_idx: Optional[int] = None
        self.running = True

    def find_mpk_port(self) -> Optional[str]:
        try:
            for port in mido.get_input_names():
                if "mpk" in port.lower() or "akai" in port.lower():
                    return port
        except Exception:
            pass
        return None

    def on_knob_change(self, cc: int, val: int):
        # Knob 1 (CC 70 or CC 1): Select Keyboard Instrument
        if cc in (70, 1):
            num_slots = len(KEYBOARD_INSTRUMENTS)
            idx = int((val / 127.99) * num_slots)
            idx = max(0, min(num_slots - 1, idx))
            
            if idx != self.current_key_idx:
                self.current_key_idx = idx
                prog_num, name = KEYBOARD_INSTRUMENTS[idx]
                send_fluid_command(f"prog 0 {prog_num}")
                print(f"[KNOB 1] Teclas -> [{idx + 1}/{num_slots}] {name} (Prog {prog_num})")
                # Auditory preview feedback: middle C (60)
                play_preview_note(chan=0, note=60, vel=95, duration=0.15)

        # Knob 2 (CC 71 or CC 2): Select Drum Kit
        elif cc in (71, 2):
            num_slots = len(DRUM_KITS)
            idx = int((val / 127.99) * num_slots)
            idx = max(0, min(num_slots - 1, idx))
            
            if idx != self.current_drum_idx:
                self.current_drum_idx = idx
                kit_num, name = DRUM_KITS[idx]
                send_fluid_command(f"prog 9 {kit_num}")
                print(f"[KNOB 2] Batería -> [{idx + 1}/{num_slots}] {name} (Kit {kit_num})")
                # Auditory preview feedback: kick drum (36)
                play_preview_note(chan=9, note=36, vel=100, duration=0.15)

        # Knob 8 (CC 77 or CC 7 or CC 8): Master Gain / Volume
        elif cc in (77, 7, 8):
            gain = (val / 127.0) * 0.9  # Max gain 0.9
            send_fluid_command(f"gain {gain:.2f}")

    def run(self):
        print("=== Akai MPK Mini - Headless Knob Controller Started ===")
        print("  Knob 1 (CC 70/1): Gira para cambiar instrumentos de TECLADO")
        print("  Knob 2 (CC 71/2): Gira para cambiar kits de BATERÍA")
        print("  Knob 8 (CC 77/7): Gira para cambiar el VOLUMEN")
        print("  (Escucharás una nota/golpe de preescucha al cambiar de sonido)")
        print("=========================================================")

        while self.running:
            port_name = self.find_mpk_port()
            if not port_name:
                time.sleep(2.0)
                continue

            try:
                print(f"[+] Conectado a {port_name}. Listo para cambiar sonidos con las perillas.")
                with mido.open_input(port_name) as inport:
                    for msg in inport:
                        if msg.type == "control_change":
                            self.on_knob_change(msg.control, msg.value)
            except Exception as e:
                print(f"[-] Desconectado: {e}. Esperando reconexión...")
                time.sleep(2.0)

if __name__ == "__main__":
    controller = KnobController()
    controller.run()
