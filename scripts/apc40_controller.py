#!/usr/bin/env python3
"""
Akai APC40 MKII Full Drum Workstation & Multi-FX Performance Controller for Raspberry Pi 3.
Direct note-to-drum mapping with instant FluidSynth sound routing (Channel 9).
- Desconecta el enlace directo por defecto de ALSA (Canal 0 Yamaha Piano) para que
  los pads suenen EXCLUSIVAMENTE a batería y percusión en el Canal 9.
"""

import time
import socket
import threading
import subprocess
from typing import Optional, Dict
import mido

FLUID_HOST = "localhost"
FLUID_PORT = 9800

DRUM_KITS = [
    (0, "Standard Acoustic Drum Kit"),
    (25, "Roland TR-808 Classic Trap Kit"),
    (24, "Electronic 909 Dance Kit"),
    (16, "Power Heavy Rock Drum Kit"),
    (32, "Jazz Warm Brush & Sticks Kit"),
    (48, "Orchestral Percussion & Timpani Kit")
]

DRUM_SOUND_MAP = {
    0: 36,   # Kick 1
    1: 37,   # Side Stick
    2: 38,   # Snare 1
    3: 39,   # Hand Clap
    4: 40,   # Snare 2
    5: 41,   # Low Floor Tom
    6: 42,   # Closed Hi-Hat
    7: 43,   # High Floor Tom
    8: 44,   # Pedal Hi-Hat
    9: 45,   # Low Tom
    10: 46,  # Open Hi-Hat
    11: 47,  # Low-Mid Tom
    12: 48,  # Hi-Mid Tom
    13: 49,  # Crash Cymbal 1
    14: 50,  # High Tom
    15: 51,  # Ride Cymbal 1
    16: 52,  # Chinese Cymbal
    17: 53,  # Ride Bell
    18: 54,  # Tambourine
    19: 55,  # Splash Cymbal
    20: 56,  # Cowbell
    21: 57,  # Crash Cymbal 2
    22: 58,  # Vibraslap
    23: 59,  # Ride Cymbal 2
    24: 60,  # Hi Bongo
    25: 61,  # Low Bongo
    26: 62,  # Mute Hi Conga
    27: 63,  # Open Hi Conga
    28: 64,  # Low Conga
    29: 65,  # High Timbale
    30: 66,  # Low Timbale
    31: 67,  # High Agogo
    32: 68,  # Low Agogo
    33: 69,  # Cabasa
    34: 70,  # Maracas
    35: 71,  # Short Whistle
    36: 72,  # Long Whistle
    37: 73,  # Short Guiro
    38: 74,  # Long Guiro
    39: 75,  # Claves
}


class FluidClient:
    def __init__(self, host=FLUID_HOST, port=FLUID_PORT):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self._lock = threading.Lock()

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
            return True
        except Exception:
            self.sock = None
            return False

    def send(self, cmd: str):
        with self._lock:
            if not self.sock:
                self.connect()
            if self.sock:
                try:
                    self.sock.sendall((cmd + "\n").encode("utf-8"))
                except Exception:
                    self.connect()
                    if self.sock:
                        try:
                            self.sock.sendall((cmd + "\n").encode("utf-8"))
                        except Exception:
                            pass


fluid = FluidClient()


class APC40FullSessionController:
    def __init__(self):
        self.running = True
        self.inport: Optional[mido.ports.BaseInput] = None
        self.outport: Optional[mido.ports.BaseOutput] = None
        self.active_pads: Dict[int, int] = {}
        self.current_kit_idx: int = 0
        self.drum_col_volumes = [127] * 8
        self.drum_col_pans = [64] * 8

        self.metronome_active = False
        self.current_bpm = 120.0
        self.metronome_thread: Optional[threading.Thread] = None
        self.tap_times = []

    def find_apc_ports(self):
        in_p = None
        out_p = None
        for p in mido.get_input_names():
            if "apc40" in p.lower():
                in_p = p
                break
        for p in mido.get_output_names():
            if "apc40" in p.lower():
                out_p = p
                break
        return in_p, out_p

    def disconnect_raw_alsa_passthrough(self):
        # Desconectar el puerto hardware raw de ALSA hacia FluidSynth para evitar que
        # las notas físicas del APC40 se envíen en paralelo al Canal 0 (Yamaha Grand Piano)
        try:
            subprocess.run("aconnect -d 'APC40 mkII':0 'FLUID Synth':0 2>/dev/null || true", shell=True)
            print("[+] Enlace crudo ALSA de APC40 a FluidSynth (Canal 0 Piano) anulado correctamente.", flush=True)
        except Exception:
            pass

    def init_apc_hardware(self):
        if not self.outport:
            return
        sysex = mido.Message("sysex", data=[0x47, 0x7F, 0x29, 0x60, 0x00, 0x04, 0x40, 0x08, 0x02, 0x01])
        try:
            self.outport.send(sysex)
        except Exception:
            pass
        self.disconnect_raw_alsa_passthrough()

    def select_drum_kit(self, kit_idx: int):
        if 0 <= kit_idx < len(DRUM_KITS):
            self.current_kit_idx = kit_idx
            kit_num, kit_name = DRUM_KITS[kit_idx]
            fluid.send(f"prog 9 {kit_num}")
            print(f"[DRUM KIT] -> Kit #{kit_num}: {kit_name}", flush=True)

    def trigger_panic(self):
        cmds = []
        for c in range(16):
            cmds.append(f"cc {c} 123 0\ncc {c} 120 0")
        cmds.append("set synth.chorus.active False")
        fluid.send("\n".join(cmds))
        self.active_pads.clear()
        print("\n[STOP ALL CLIPS / PANIC] ¡Silencio absoluto!", flush=True)

    def toggle_metronome(self):
        self.metronome_active = not self.metronome_active
        st = "ACTIVADO" if self.metronome_active else "APAGADO"
        print(f"\n[METRONOME] -> {st} ({int(self.current_bpm)} BPM)", flush=True)
        if self.metronome_active:
            if not self.metronome_thread or not self.metronome_thread.is_alive():
                self.metronome_thread = threading.Thread(target=self._metronome_loop, daemon=True)
                self.metronome_thread.start()

    def _metronome_loop(self):
        fluid.send("prog 15 115\ncc 15 7 100\n")
        beat = 0
        while self.metronome_active and self.running:
            interval = 60.0 / max(30.0, min(240.0, self.current_bpm))
            pitch = 77 if (beat % 4 == 0) else 76
            vel = 115 if (beat % 4 == 0) else 85
            fluid.send(f"noteon 15 {pitch} {vel}\n")
            time.sleep(0.06)
            fluid.send(f"noteoff 15 {pitch}\n")
            beat += 1
            time.sleep(max(0.01, interval - 0.06))

    def handle_tap_tempo(self):
        now = time.time()
        self.tap_times.append(now)
        self.tap_times = [t for t in self.tap_times if now - t <= 3.0]
        if len(self.tap_times) >= 2:
            diffs = [self.tap_times[i] - self.tap_times[i - 1] for i in range(1, len(self.tap_times))]
            avg_diff = sum(diffs) / len(diffs)
            if avg_diff > 0.15:
                calc_bpm = round(60.0 / avg_diff, 1)
                self.current_bpm = max(40.0, min(220.0, calc_bpm))
                print(f"\n[TAP TEMPO] -> {self.current_bpm} BPM", flush=True)

    def handle_pad_event(self, msg):
        drum_note = DRUM_SOUND_MAP.get(msg.note, 36 + (msg.note % 36))
        col = msg.note % 8
        fader_scale = self.drum_col_volumes[col] / 127.0
        effective_vel = max(1, min(127, int(msg.velocity * fader_scale)))

        if msg.type == "note_on" and msg.velocity > 0:
            col_pan = self.drum_col_pans[col]
            fluid.send(f"cc 9 10 {col_pan}\nnoteon 9 {drum_note} {effective_vel}")
            self.active_pads[msg.note] = drum_note
        else:
            d_note = self.active_pads.pop(msg.note, drum_note)
            fluid.send(f"noteoff 9 {d_note}")

    def handle_channel_strip_knob(self, col_idx: int, value: int):
        self.drum_col_pans[col_idx] = value
        fluid.send(f"cc 9 10 {value}")
        pan = f"R {int(((value - 64) / 64.0) * 100)}%" if value > 64 else (f"L {int(((64 - value) / 64.0) * 100)}%" if value < 64 else "Centro")
        print(f"[COL {col_idx + 1} STEREO PAN] -> {pan}", flush=True)

    def handle_device_control_fx(self, control: int, value: int):
        val_norm = value / 127.0

        if control in (16, 24):
            fluid.send(f"cc 9 91 {value}\nset synth.reverb.level {round(val_norm, 2)}")
            print(f"[FX 1: REVERB LEVEL] -> {int(val_norm * 100)}%", flush=True)
        elif control in (17, 25):
            room = round(val_norm, 2)
            fluid.send(f"set synth.reverb.room-size {room}")
            print(f"[FX 2: REVERB ROOM] -> {int(room * 100)}%", flush=True)
        elif control in (18, 26):
            fluid.send(f"cc 9 93 {value}")
            print(f"[FX 3: CHORUS LEVEL] -> {int(val_norm * 100)}%", flush=True)
        elif control in (19, 27):
            fluid.send(f"cc 9 74 {value}")
            print(f"[FX 4: FILTER CUTOFF] -> {int(val_norm * 100)}%", flush=True)
        elif control in (20, 28):
            fluid.send(f"cc 9 71 {value}")
            print(f"[FX 5: RESONANCE Q] -> {int(val_norm * 100)}%", flush=True)
        elif control in (21, 29):
            fluid.send(f"cc 9 10 {value}")
            pan = f"R {int((val_norm - 0.5) * 200)}%" if value > 64 else (f"L {int((0.5 - val_norm) * 200)}%" if value < 64 else "Centro")
            print(f"[FX 6: MASTER DRUM PAN] -> {pan}", flush=True)
        elif control in (22, 30):
            pitch_bend_val = int((val_norm - 0.5) * 16383)
            fluid.send(f"pitch_bend 9 {pitch_bend_val}")
            st = round((val_norm - 0.5) * 24, 1)
            print(f"[FX 7: DRUM TUNING] -> {'+' if st > 0 else ''}{st} st", flush=True)
        elif control in (23, 31):
            fluid.send(f"cc 9 7 {value}")
            print(f"[FX 8: DRUM TRIM] -> {int(val_norm * 100)}%", flush=True)

    def handle_fader(self, control: int, value: int):
        if 48 <= control <= 55:
            col_idx = control - 48
            self.drum_col_volumes[col_idx] = value
            print(f"[FADER {col_idx + 1} PAD VOLUME] -> {int((value / 127.0) * 100)}%", flush=True)
        elif control == 14:
            gain = round((value / 127.0) * 2.5, 2)
            fluid.send(f"set synth.gain {gain}")
            print(f"[MASTER FADER] -> Gain {gain}", flush=True)

    def run(self):
        print("==================================================================", flush=True)
        print(" Akai APC40 mkII - Dedicated Drum & FX Station                   ", flush=True)
        print("==================================================================", flush=True)

        fluid.connect()
        fluid.send("prog 9 0\ncc 9 7 127\ncc 9 10 64\ncc 9 91 30\nset synth.gain 1.25\n")

        while self.running:
            in_name, out_name = self.find_apc_ports()
            if not in_name:
                time.sleep(2.0)
                continue

            try:
                self.disconnect_raw_alsa_passthrough()
                self.inport = mido.open_input(in_name)
                if out_name:
                    try:
                        self.outport = mido.open_output(out_name)
                        self.init_apc_hardware()
                    except Exception:
                        pass

                print(f"[+] Conectado y listo en {in_name}.", flush=True)

                while self.running:
                    for msg in self.inport.iter_pending():
                        if msg.type in ("note_on", "note_off"):
                            if msg.note == 81 and msg.type == "note_on":
                                self.trigger_panic()
                            elif msg.note == 90 and msg.type == "note_on":
                                self.toggle_metronome()
                            elif msg.note == 99 and msg.type == "note_on":
                                self.handle_tap_tempo()
                            elif 82 <= msg.note <= 87 and msg.type == "note_on" and msg.velocity > 0:
                                self.select_drum_kit(msg.note - 82)
                            else:
                                self.handle_pad_event(msg)

                        elif msg.type == "control_change":
                            if 16 <= msg.control <= 31:
                                self.handle_device_control_fx(msg.control, msg.value)
                            elif (48 <= msg.control <= 55):
                                if msg.channel == 0:
                                    self.handle_fader(msg.control, msg.value)
                                else:
                                    self.handle_channel_strip_knob(msg.control - 48, msg.value)
                            elif msg.control == 14:
                                self.handle_fader(msg.control, msg.value)

                    time.sleep(0.002)

            except Exception as e:
                print(f"[-] Reconectando: {e}", flush=True)
                if self.inport:
                    try:
                        self.inport.close()
                    except Exception:
                        pass
                if self.outport:
                    try:
                        self.outport.close()
                    except Exception:
                        pass
                time.sleep(2.0)


if __name__ == "__main__":
    controller = APC40FullSessionController()
    controller.run()
