#!/usr/bin/env python3
"""
Akai APC40 MKII Multi-Instrument Workstation & Multi-FX Performance Controller for Raspberry Pi 3.
8 Switchable Modes across the full 5x8 Matrix (40 Pads) via Track Select Buttons 1-8:
- Mode 0 ("NONE", Note 56): Full Acoustic & Electronic Drum Station (Channel 9, 6 Scene Launch kits)
- Mode 1 ("8 BARS", Note 57): World & Latin Percussion (Channel 9, 40 distinct ethnic/percussion sounds)
- Mode 2 ("4 BARS", Note 58): Deep Basses & Synth Subs (Channel 1, Prog 38 Synth Bass 1)
- Mode 3 ("2 BARS", Note 59): Pianos, Rhodes & Keys (Channel 3, Prog 4 Rhodes MK1)
- Mode 4 ("1 BAR", Note 60): Guitars & Plucks (Channel 4, Prog 24 Nylon Spanish Guitar / Sitar)
- Mode 5 ("1/2", Note 61): Orchestral Strings & Brass (Channel 5, Prog 48 Orchestral Strings)
- Mode 6 ("1/4", Note 62): Synth Leads & 8-Bit Chiptune (Channel 6, Prog 80 Square / Saw Lead)
- Mode 7 ("1/8", Note 63): Ambient Warm Pads & Soundscapes (Channel 7, Prog 88 Warm Space Pad)

Controls:
- Channel Faders 1-8: Individual volume per column in drum mode; channel volume in melodic mode.
- Master Fader: Overall Master Volume (FluidSynth gain).
- 8 Channel Strip Knobs: Independent Pan per column.
- 8 Device Control Knobs: Real-Time Multi-FX (Reverb, Room, Chorus, Cutoff, Resonance, Pan, Pitch Tuning, Master Trim).
- STOP ALL CLIPS (Note 81): Instant Panic on all channels.
- METRONOME (Note 90): Metronome on isolated Channel 15.
- TAP TEMPO (Note 99): Real-time Jam BPM detection.
"""

import time
import socket
import threading
import subprocess
from typing import Optional, Dict
import mido

FLUID_HOST = "localhost"
FLUID_PORT = 9800

# 6 Drum Kits for Mode 0 (Scene Launch 1..6)
DRUM_KITS = [
    (0, "Standard Acoustic Drum Kit"),
    (25, "Roland TR-808 Classic Trap Kit"),
    (24, "Electronic 909 Dance Kit"),
    (16, "Power Heavy Rock Drum Kit"),
    (32, "Jazz Warm Brush & Sticks Kit"),
    (48, "Orchestral Percussion & Timpani Kit")
]

# Mode 0: Standard & Electronic Drum Kit (40 sounds)
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

# Mode 1: World & Latin Percussion (40 distinct ethnic percussion instruments)
WORLD_PERCUSSION_MAP = {
    # Fila 0 (Pads 0..7): Percusión Brasileña y Samba
    0: 86,   # Surdo Mudo
    1: 87,   # Surdo Abierto
    2: 40,   # Caixa / Tamborim
    3: 38,   # Repinique / Snare
    4: 67,   # Agogô Agudo
    5: 68,   # Agogô Grave
    6: 71,   # Apito Silbato Corto
    7: 72,   # Apito Silbato Largo
    # Fila 1 (Pads 8..15): Percusión Menor y Efectos
    8: 78,   # Cuíca Muda
    9: 79,   # Cuíca Abierta
    10: 54,  # Pandeiro / Pandereta
    11: 69,  # Cabasa
    12: 70,  # Maracas
    13: 82,  # Shaker
    14: 73,  # Güiro Corto
    15: 74,  # Güiro Largo
    # Fila 2 (Pads 16..23): Madera, Campanas y Metal
    16: 75,  # Claves de Madera
    17: 76,  # Woodblock Agudo
    18: 77,  # Woodblock Grave
    19: 56,  # Cencerro / Cowbell
    20: 80,  # Triángulo Mudo
    21: 81,  # Triángulo Abierto
    22: 85,  # Castañuelas Flamencas
    23: 83,  # Cascabeles / Jingle Bell
    # Fila 3 (Pads 24..31): Congas, Bongós y Timbales
    24: 62,  # Conga Muda
    25: 63,  # Conga Abierta
    26: 64,  # Conga Grave
    27: 60,  # Bongó Agudo
    28: 61,  # Bongó Grave
    29: 65,  # Timbale Agudo
    30: 66,  # Timbale Grave
    31: 58,  # Vibraslap
    # Fila 4 (Pads 32..39): Percusión Oriental y Épica
    32: 116, # Taiko Drum Japonés
    33: 117, # Melodic Tom Oriental
    34: 118, # Synth Drum Electrónico
    35: 119, # Reverse Cymbal Whoosh
    36: 84,  # Belltree Resonante
    37: 52,  # Gong / Chinese Cymbal
    38: 55,  # Splash Cymbal
    39: 39,  # Hand Clap / Palmas
}

# 8 Modes Definition: (Name, MIDI Channel, Initial Program, Base Note, Step per row)
MODES_CONFIG = [
    # 0: Track 1 ("NONE") -> Full Drum Station
    {"name": "Drums & Beats", "type": "drum", "chan": 9, "prog": 0, "color": 1},
    # 1: Track 2 ("8 BARS") -> World & Latin Percussion
    {"name": "World & Latin Percussion", "type": "world", "chan": 9, "prog": 0, "color": 1},
    # 2: Track 3 ("4 BARS") -> Deep Basses & Synth Subs
    {"name": "Deep Basses & Subs", "type": "melodic", "chan": 1, "prog": 38, "base_note": 24, "color": 3},
    # 3: Track 4 ("2 BARS") -> Pianos, Rhodes & Organs
    {"name": "Pianos & Keys", "type": "melodic", "chan": 3, "prog": 4, "base_note": 48, "color": 1},
    # 4: Track 5 ("1 BAR") -> Guitars & Ethnic Plucks
    {"name": "Guitars & Ethnic Plucks", "type": "melodic", "chan": 4, "prog": 24, "base_note": 45, "color": 1},
    # 5: Track 6 ("1/2") -> Orchestral Strings & Brass
    {"name": "Orchestral Strings & Brass", "type": "melodic", "chan": 5, "prog": 48, "base_note": 48, "color": 1},
    # 6: Track 7 ("1/4") -> Synth Leads & Chiptune
    {"name": "Synth Leads & Chiptune", "type": "melodic", "chan": 6, "prog": 80, "base_note": 57, "color": 3},
    # 7: Track 8 ("1/8") -> Ambient Warm Pads & Soundscapes
    {"name": "Ambient Pads & Soundscapes", "type": "melodic", "chan": 7, "prog": 88, "base_note": 48, "color": 1},
]


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
            self.sock.settimeout(2.0)
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
        self.active_pads: Dict[int, tuple] = {}  # pad_note -> (chan, target_note)
        self.current_mode_idx: int = 0
        self.current_kit_idx: int = 0

        self.col_volumes = [127] * 8
        self.col_pans = [64] * 8

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

    def ensure_no_piano_passthrough(self):
        subprocess.run("aconnect -d 'APC40 mkII':0 'FLUID Synth':0 2>/dev/null || true", shell=True)
        subprocess.run("aconnect -l | grep 'RtMidi output' -B 1 | grep client | awk '{print $2}' | tr -d ':' | while read id; do aconnect -d ${id}:0 'FLUID Synth':0 2>/dev/null || true; done", shell=True)

    def init_apc_hardware(self):
        if not self.outport:
            return
        # SysEx for APC40 mkII Ableton Alternate Mode 1 (0x41)
        sysex = mido.Message("sysex", data=[0x47, 0x7F, 0x29, 0x60, 0x00, 0x04, 0x41, 0x08, 0x02, 0x01])
        try:
            self.outport.send(sysex)
        except Exception:
            pass
        self.ensure_no_piano_passthrough()
        self.update_track_select_leds()

    def update_track_select_leds(self):
        if not self.outport:
            return
        # Track Select 1..8 notes: 56 to 63
        for idx in range(8):
            note = 56 + idx
            vel = 1 if idx == self.current_mode_idx else 0  # 1 = Green, 0 = Off
            try:
                self.outport.send(mido.Message("note_on", channel=0, note=note, velocity=vel))
            except Exception:
                pass

    def select_mode(self, mode_idx: int):
        if 0 <= mode_idx < len(MODES_CONFIG):
            # Silenciar notas activas antes de conmutar
            for pad_note, (chan, target_note) in list(self.active_pads.items()):
                fluid.send(f"noteoff {chan} {target_note}")
            self.active_pads.clear()

            self.current_mode_idx = mode_idx
            cfg = MODES_CONFIG[mode_idx]
            self.update_track_select_leds()

            # Asegurar programa cargado en el canal correspondiente
            if cfg["type"] == "melodic":
                fluid.send(f"prog {cfg['chan']} {cfg['prog']}\ncc {cfg['chan']} 7 127\ncc {cfg['chan']} 10 64\n")
            elif cfg["type"] in ("drum", "world"):
                fluid.send("prog 9 0\ncc 9 7 127\ncc 9 10 64\n")

            labels = ["NONE", "8 BARS", "4 BARS", "2 BARS", "1 BAR", "1/2", "1/4", "1/8"]
            label = labels[mode_idx] if mode_idx < len(labels) else f"T{mode_idx+1}"
            print(f"\n[APC40 MODE {mode_idx + 1}: {label}] -> {cfg['name']} (Channel {cfg.get('chan', 9)})", flush=True)

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

    def compute_target_note_and_channel(self, pad_note: int):
        cfg = MODES_CONFIG[self.current_mode_idx]
        mode_type = cfg["type"]

        if mode_type == "drum":
            # Mode 0: Drums
            target = DRUM_SOUND_MAP.get(pad_note, 36 + (pad_note % 36))
            return 9, target

        elif mode_type == "world":
            # Mode 1: World & Latin Percussion
            target = WORLD_PERCUSSION_MAP.get(pad_note, 36 + (pad_note % 40))
            return 9, target

        elif mode_type == "melodic":
            # Modes 2..7: Melodic grid (Isomorphic Fourths Grid: +5 semitones per row, +1 per col)
            chan = cfg["chan"]
            base = cfg["base_note"]
            row = pad_note // 8
            col = pad_note % 8
            target = base + (row * 5) + col
            target = max(0, min(127, target))
            return chan, target

        return 9, pad_note

    def handle_pad_event(self, msg):
        col = msg.note % 8
        fader_scale = self.col_volumes[col] / 127.0
        effective_vel = max(1, min(127, int(msg.velocity * fader_scale)))
        chan, target_note = self.compute_target_note_and_channel(msg.note)

        if msg.type == "note_on" and msg.velocity > 0:
            col_pan = self.col_pans[col]
            fluid.send(f"cc {chan} 10 {col_pan}\nnoteon {chan} {target_note} {effective_vel}")
            self.active_pads[msg.note] = (chan, target_note)
        else:
            active_info = self.active_pads.pop(msg.note, (chan, target_note))
            c, t = active_info
            fluid.send(f"noteoff {c} {t}")

    def handle_channel_strip_knob(self, col_idx: int, value: int):
        self.col_pans[col_idx] = value
        cfg = MODES_CONFIG[self.current_mode_idx]
        chan = cfg.get("chan", 9)
        fluid.send(f"cc {chan} 10 {value}")
        pan = f"R {int(((value - 64) / 64.0) * 100)}%" if value > 64 else (f"L {int(((64 - value) / 64.0) * 100)}%" if value < 64 else "Centro")
        print(f"[COL {col_idx + 1} STEREO PAN] -> {pan}", flush=True)

    def handle_device_control_fx(self, control: int, value: int):
        val_norm = value / 127.0
        cfg = MODES_CONFIG[self.current_mode_idx]
        chan = cfg.get("chan", 9)

        if control in (16, 24):
            fluid.send(f"cc {chan} 91 {value}\nset synth.reverb.level {round(val_norm, 2)}")
            print(f"[FX 1: REVERB LEVEL] -> {int(val_norm * 100)}%", flush=True)
        elif control in (17, 25):
            room = round(val_norm, 2)
            fluid.send(f"set synth.reverb.room-size {room}")
            print(f"[FX 2: REVERB ROOM] -> {int(room * 100)}%", flush=True)
        elif control in (18, 26):
            fluid.send(f"cc {chan} 93 {value}")
            print(f"[FX 3: CHORUS LEVEL] -> {int(val_norm * 100)}%", flush=True)
        elif control in (19, 27):
            fluid.send(f"cc {chan} 74 {value}")
            print(f"[FX 4: FILTER CUTOFF] -> {int(val_norm * 100)}%", flush=True)
        elif control in (20, 28):
            fluid.send(f"cc {chan} 71 {value}")
            print(f"[FX 5: RESONANCE Q] -> {int(val_norm * 100)}%", flush=True)
        elif control in (21, 29):
            fluid.send(f"cc {chan} 10 {value}")
            pan = f"R {int((val_norm - 0.5) * 200)}%" if value > 64 else (f"L {int((0.5 - val_norm) * 200)}%" if value < 64 else "Centro")
            print(f"[FX 6: MASTER PAN] -> {pan}", flush=True)
        elif control in (22, 30):
            pitch_bend_val = int((val_norm - 0.5) * 16383)
            fluid.send(f"pitch_bend {chan} {pitch_bend_val}")
            st = round((val_norm - 0.5) * 24, 1)
            print(f"[FX 7: TUNING] -> {'+' if st > 0 else ''}{st} st", flush=True)
        elif control in (23, 31):
            fluid.send(f"cc {chan} 7 {value}")
            print(f"[FX 8: CHANNEL TRIM] -> {int(val_norm * 100)}%", flush=True)

    def handle_fader(self, control: int, value: int):
        if 48 <= control <= 55:
            col_idx = control - 48
            self.col_volumes[col_idx] = value
            print(f"[FADER {col_idx + 1} PAD VOLUME] -> {int((value / 127.0) * 100)}%", flush=True)
        elif control == 14:
            gain = round((value / 127.0) * 2.5, 2)
            fluid.send(f"set synth.gain {gain}")
            print(f"[MASTER FADER] -> Gain {gain}", flush=True)

    def run(self):
        print("==================================================================", flush=True)
        print(" Akai APC40 mkII - 8-Mode Multi-Instrument & Multi-FX Station    ", flush=True)
        print("==================================================================", flush=True)

        fluid.connect()
        # Inicializar canales 1 a 7 con los programas asignados a cada modo
        for idx, cfg in enumerate(MODES_CONFIG):
            if cfg["type"] == "melodic":
                fluid.send(f"prog {cfg['chan']} {cfg['prog']}\ncc {cfg['chan']} 7 127\ncc {cfg['chan']} 10 64\n")
        fluid.send("prog 9 0\ncc 9 7 127\ncc 9 10 64\ncc 9 91 30\nset synth.gain 1.25\n")

        while self.running:
            in_name, out_name = self.find_apc_ports()
            if not in_name:
                time.sleep(2.0)
                continue

            try:
                self.inport = mido.open_input(in_name)
                if out_name:
                    try:
                        self.outport = mido.open_output(out_name)
                        self.init_apc_hardware()
                    except Exception:
                        pass

                self.ensure_no_piano_passthrough()
                print(f"[+] Conectado y listo en {in_name}.", flush=True)

                while self.running:
                    for msg in self.inport.iter_pending():
                        if msg.type in ("note_on", "note_off"):
                            # Botón STOP ALL CLIPS (81) -> Panic
                            if msg.note == 81 and msg.type == "note_on":
                                self.trigger_panic()
                            # Botón METRONOME (90) -> Toggle Click
                            elif msg.note == 90 and msg.type == "note_on":
                                self.toggle_metronome()
                            # Botón TAP TEMPO (99) -> Ajuste de BPM
                            elif msg.note == 99 and msg.type == "note_on":
                                self.handle_tap_tempo()
                            # Track Select 1..8 (Notas 56 a 63) -> Conmutar 8 Modos Instrumentales
                            elif 56 <= msg.note <= 63 and msg.type == "note_on" and msg.velocity > 0:
                                self.select_mode(msg.note - 56)
                            # Scene Launch (82..87): cambio de Drum Kit (sólo en modo 0)
                            elif 82 <= msg.note <= 87 and msg.type == "note_on" and msg.velocity > 0:
                                if self.current_mode_idx == 0:
                                    self.select_drum_kit(msg.note - 82)
                            else:
                                self.handle_pad_event(msg)

                        elif msg.type == "control_change":
                            if 16 <= msg.control <= 31:
                                self.handle_device_control_fx(msg.control, msg.value)
                            elif 48 <= msg.control <= 55:
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
