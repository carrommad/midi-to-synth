#!/usr/bin/env python3
"""
Advanced Headless Sound Selector for Akai MPK Mini MK2/MK3 on Raspberry Pi.
Enables 24 Melodic Instruments & 24 Drum Kits selected directly using the keyboard keys:
  - HOLD LOWEST KEY (C1)  + PRESS ANY KEY (1-24) -> Selects from 24 Melodic Instruments
  - HOLD HIGHEST KEY (C3) + PRESS ANY KEY (1-24) -> Selects from 24 Drum Kits
  - KNOB 8 -> Master Volume (0-100%)
"""

import time
import socket
import threading
import subprocess
from typing import Optional, Set, Any
import mido

FLUID_HOST = "localhost"
FLUID_PORT = 9800

# 7 Octave-Mapped Instrument Libraries (Holding C1 + Keys 1..24)
# Mapped dynamically based on the active octave shift (OCT -3 to OCT +3)
OCTAVE_INSTRUMENT_LIBRARIES = {
    # OCT -3: Deep Basses, 808 Subs & Acid 303s
    -3: [
        (32, "Acoustic Upright Bass"),
        (33, "Fingered Electric Bass"),
        (34, "Picked Electric Bass"),
        (35, "Fretless Bass"),
        (36, "Slap Bass 1 (Funk Pop)"),
        (37, "Slap Bass 2 (Heavy Thumb)"),
        (38, "Synth Bass 1 (Classic 808 Sub)"),
        (39, "Synth Bass 2 (Acid 303 Resonant)"),
        (38, "Moog Sub Bass 1"),
        (39, "Square Acid Bass"),
        (38, "Deep Sub-Drone Bass"),
        (39, "Reese Jungle Bass"),
        (32, "Double Bass Pizzicato"),
        (33, "Motown R&B Bass"),
        (34, "P-Bass Flatwound"),
        (35, "Warm Jazz Fretless"),
        (36, "MarkKing Thumb Slap"),
        (37, "Heavy Metal Picked Bass"),
        (38, "Sub 808 Distorted"),
        (39, "TB-303 High Res Sweep"),
        (38, "Electro House Donk Bass"),
        (39, "UK Garage Organ Bass"),
        (38, "Modular Analog Sub"),
        (39, "Dark Neuro Bass")
    ],
    # OCT -2: World & Ethnic Instruments
    -2: [
        (104, "Sitar (Classic Indian)"),
        (105, "Banjo (5-String Americana)"),
        (106, "Shamisen (Japanese Plucked)"),
        (107, "Koto (Japanese Traditional)"),
        (108, "Kalimba (Thumb Piano)"),
        (109, "Bagpipe (Scottish Highlands)"),
        (110, "Fiddle (Irish Celtic)"),
        (111, "Shanai (Indian Oboe)"),
        (114, "Steel Drums (Caribbean)"),
        (115, "Woodblock & Percussion"),
        (116, "Taiko Drum (Japanese)"),
        (117, "Melodic Tom"),
        (118, "Synth Drum"),
        (75,  "Pan Flute (Andean Zampona)"),
        (76,  "Blown Bottle"),
        (77,  "Shakuhachi (Bamboo Flute)"),
        (78,  "Whistle"),
        (79,  "Ocarina"),
        (15,  "Santur / Dulcimer"),
        (12,  "Vibraphone"),
        (14,  "Tubular Bells"),
        (104, "Sitar Drone & Resonator"),
        (107, "Koto Tremolo Pluck"),
        (114, "Trinidad Calypso Steel")
    ],
    # OCT -1: Synths, Leads & Warm Pads
    -1: [
        (80, "Synth Lead 1 (Square Wave)"),
        (81, "Synth Lead 2 (Sawtooth Wave)"),
        (82, "Synth Lead 3 (Calliope)"),
        (83, "Synth Lead 4 (Chiff Lead)"),
        (84, "Synth Lead 5 (Charang Guitar Lead)"),
        (85, "Synth Lead 6 (Voice Synth Lead)"),
        (86, "Synth Lead 7 (Fifths Saw Lead)"),
        (87, "Synth Lead 8 (Bass + Lead Solo)"),
        (88, "Synth Pad 1 (Warm Analog Pad)"),
        (89, "Synth Pad 2 (Polysynth Warmth)"),
        (90, "Synth Pad 3 (Choir Pad)"),
        (91, "Synth Pad 4 (Bowed Glass Pad)"),
        (92, "Synth Pad 5 (Metallic Shimmer Pad)"),
        (93, "Synth Pad 6 (Halo Ethereal Pad)"),
        (94, "Synth Pad 7 (Sweep Filter Pad)"),
        (95, "Synth Pad 8 (Space Ice Rain Pad)"),
        (50, "Synth Strings 1 (80s Analog)"),
        (51, "Synth Strings 2 (Slow Strings)"),
        (54, "Synth Voice (Ooohs & Aaahs)"),
        (62, "Synth Brass 1 (Jump Polysynth)"),
        (63, "Synth Brass 2 (Oberheim Brass)"),
        (80, "80s Arcade Lead"),
        (81, "EDM SuperSaw Lead"),
        (88, "Cyberpunk Drone Pad")
    ],
    # Neutral OCT (0): Pianos, Organs & Keyboards
    0: [
        (0,  "Yamaha Grand Piano"),
        (1,  "Bright Acoustic Piano"),
        (2,  "Electric Piano (Rhodes MK1)"),
        (3,  "Honky-Tonk Bar Piano"),
        (4,  "Electric Piano 2 (FM DX7)"),
        (5,  "Electric Piano (Wurlitzer Warm)"),
        (6,  "Harpsichord"),
        (7,  "Clavinet (Stevie Wonder Funk)"),
        (8,  "Celesta (Cristal Bell)"),
        (9,  "Glockenspiel"),
        (10, "Music Box"),
        (11, "Vibraphone (Jazz Vibes)"),
        (12, "Marimba (Wood Mallet)"),
        (13, "Xylophone"),
        (14, "Tubular Bells"),
        (16, "Drawbar Organ (Hammond B3)"),
        (17, "Percussive Organ (Rock Organ)"),
        (18, "Rock Rotary Organ"),
        (19, "Church Pipe Organ"),
        (20, "Reed Organ"),
        (21, "Accordion (French Musette)"),
        (22, "Harmonica (Blues Harp)"),
        (23, "Tango Bandoneon"),
        (0,  "Concert Grand Ambience")
    ],
    # OCT +1: Guitars & Plucked Strings
    1: [
        (24, "Nylon Spanish Guitar (Flamenco)"),
        (25, "Steel String Acoustic Guitar"),
        (26, "Jazz Electric Archtop Guitar"),
        (27, "Clean Electric Guitar (Strat)"),
        (28, "Muted Electric Guitar (Funk Chank)"),
        (29, "Overdrive Rock Guitar"),
        (30, "Distortion Lead Guitar"),
        (31, "Guitar Harmonics & Feedback"),
        (24, "Flamenco Rasgueado Pluck"),
        (25, "12-String Acoustic Guitar"),
        (26, "Warm Wes Montgomery Jazz"),
        (27, "Chorus Clean Strat"),
        (28, "Nile Rodgers Disco Funk Guitar"),
        (29, "Heavy Metal Rhythm Power"),
        (30, "Rock Solo Virtuoso Saw"),
        (31, "Pinch Harmonics Solo"),
        (104, "Acoustic Sitar Raga"),
        (105, "Bluegrass Country Banjo"),
        (15, "Gypsy Dulcimer Hammered"),
        (46, "Orchestral Harp (Concert Harp)"),
        (24, "Campanitas Nylon Solo"),
        (27, "Pedal Steel Country"),
        (29, "Tube Screamer Blues Lead"),
        (30, "Hard Rock Crunch Lead")
    ],
    # OCT +2: Orchestral, Brass & Winds
    2: [
        (40, "Solo Violin"),
        (41, "Solo Viola"),
        (42, "Solo Cello"),
        (43, "Contrabass Strings"),
        (44, "Tremolo Strings Ensemble"),
        (45, "Pizzicato Strings (Plucked)"),
        (46, "Orchestral Harp"),
        (47, "Timpani (Orchestral Drums)"),
        (48, "Full String Ensemble 1"),
        (49, "Full String Ensemble 2 (Slow)"),
        (56, "Trumpet (Fanfare & Classical)"),
        (57, "Trombone"),
        (58, "Tuba (Deep Brass)"),
        (59, "Muted Trumpet (Miles Jazz)"),
        (60, "French Horn"),
        (61, "Brass Section (Orchestral)"),
        (64, "Soprano Saxophone"),
        (65, "Alto Saxophone (Jazz Solo)"),
        (66, "Tenor Saxophone"),
        (67, "Baritone Saxophone"),
        (68, "Oboe"),
        (69, "English Horn"),
        (70, "Bassoon"),
        (71, "Clarinet")
    ],
    # OCT +3: Retro 8-Bit Chiptune & Sound FX
    3: [
        (80, "NES 25% Pulse Wave Lead"),
        (81, "Game Boy Saw Arp Lead"),
        (80, "C64 SID Arpeggiator Chip"),
        (81, "8-Bit Arcade Jump Lead"),
        (118, "8-Bit Synth Tom"),
        (119, "Reverse Cymbal Whoosh"),
        (120, "Guitar Fret Noise / Scratch"),
        (121, "Breath Noise FX"),
        (122, "Seashore Ocean Wave FX"),
        (123, "Bird Tweet Ambient FX"),
        (124, "Telephone Ring Retro"),
        (125, "Helicopter Rotor Blade"),
        (126, "Applause & Cheering Crowd"),
        (127, "Gunshot / Impact Hit"),
        (96,  "FX 1 (Sci-Fi Raindrop)"),
        (97,  "FX 2 (Soundtrack Ambient)"),
        (98,  "FX 3 (Crystal Chimes)"),
        (99,  "FX 4 (Atmosphere Space Drone)"),
        (100, "FX 5 (Brightness Bell Shimmer)"),
        (101, "FX 6 (Goblins Alien Creature)"),
        (102, "FX 7 (Echo Drops Deep Cave)"),
        (103, "FX 8 (Star Theme Sci-Fi Lead)"),
        (80,  "Chiptune Fast Triangle Bass"),
        (81,  "8-Bit Noise Snare Hit")
    ]
}

# Compatibility reference fallback
MELODIC_INSTRUMENTS = OCTAVE_INSTRUMENT_LIBRARIES[0]

# 24 Drum Kits (Mapped to Keys 1..24 while holding Highest Key)
DRUM_KITS = [
    (0, "Standard Drum Kit"),
    (1, "Standard Kit 1"),
    (2, "Standard Kit 2"),
    (3, "Standard Kit 3"),
    (4, "Standard Kit 4"),
    (8, "Room Rock Drum Kit"),
    (9, "Room Kit 1"),
    (10, "Room Kit 2"),
    (16, "Power Heavy Gated Rock Kit"),
    (17, "Power Kit 1"),
    (18, "Power Kit 2"),
    (24, "Electronic Kit (909 / Techno)"),
    (25, "Roland TR-808 Classic Trap Kit"),
    (32, "Jazz Drum Kit"),
    (33, "Jazz Kit 1"),
    (34, "Jazz Kit 2"),
    (40, "Brush Drum Kit (Escobillas)"),
    (41, "Brush Kit 1"),
    (48, "Orchestra Percussion Kit"),
    (0, "Standard Drum Kit (Alt)"),
    (8, "Room Rock Kit (Alt)"),
    (16, "Power Rock Kit (Alt)"),
    (24, "Electro 909 (Alt)"),
    (25, "Roland TR-808 (Alt)"),
]

class FluidClient:
    def __init__(self, host: str = FLUID_HOST, port: int = FLUID_PORT):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.lock = threading.Lock()
        self.connect()

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
                    self.sock.sendall((cmd + "\n").encode("utf-8"))
                except Exception:
                    self.connect()
                    if self.sock:
                        try:
                            self.sock.sendall((cmd + "\n").encode("utf-8"))
                        except Exception:
                            pass

fluid = FluidClient()

def play_preview(chan: int, note: int, vel: int = 105, duration: float = 0.3):
    """Play brief audible confirmation chime so player hears the newly selected instrument."""
    def _worker():
        fluid.send(f"noteon {chan} {note} {vel}")
        time.sleep(duration)
        fluid.send(f"noteoff {chan} {note}")
    threading.Thread(target=_worker, daemon=True).start()

class LiveMidiLooper:
    def __init__(self, fluid_client: FluidClient, controller: Optional[Any] = None):
        self.fluid = fluid_client
        self.controller = controller
        self.state: str = "IDLE"  # "IDLE", "RECORDING", "PLAYING", "OVERDUBBING", "PAUSED", "PRESET"
        self.bpm: int = 90
        self.metronome_active: bool = True
        # 8 Pistas independientes (Layers 1..8): cada pista es una lista de (phase_sec, channel, note, velocity, is_note_on, orig_prog)
        self.tracks: list = [[] for _ in range(8)]
        self.track_muted: list = [False for _ in range(8)]
        self.track_prog: list = [None for _ in range(8)]  # Voice lock per track
        self.revoice_mode: bool = False  # False: Lock instrument to track | True: Re-voice all melodic tracks to current
        self.auto_close_bars: int = 4  # Auto-close loop at boundary (4 bars default)
        self.current_track: int = 0
        self.first_note_time: Optional[float] = None
        self.loop_duration: float = 0.0
        self.rec_start_time: float = 0.0
        self.cycle_start_time: float = 0.0
        self.finish_pending: bool = False
        self.stop_event = threading.Event()
        self.play_thread: Optional[threading.Thread] = None
        self.metro_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.last_tap_times: list = []
        self.last_key_note_times: list = []
        self.detected_arp_bpm: Optional[int] = None
        self.last_arp_detected_time: float = 0.0
        self.undo_stack: list = []
        self.redo_stack: list = []

        # 16 Preset groove templates for instant jamming (Bank A: 1..8, Bank B: 9..16)
        self.preset_idx: Optional[int] = None
        self.preset_patterns = [
            # 1. Lo-Fi Chill Hop (76 BPM)
            {
                "name": "Lo-Fi Chill Hop",
                "bpm": 76,
                "steps": [
                    [(36, 110), (42, 75)], [], [(42, 60)], [],
                    [(38, 105), (42, 80)], [], [(42, 65)], [(36, 85)],
                    [(42, 75)], [], [(36, 105), (42, 70)], [],
                    [(38, 110), (42, 85)], [], [(46, 75)], [(42, 50)]
                ]
            },
            # 2. Boom-Bap 90s Classic (88 BPM)
            {
                "name": "Boom-Bap 90s Classic",
                "bpm": 88,
                "steps": [
                    [(36, 120), (42, 90)], [], [(42, 75)], [(36, 80)],
                    [(38, 125), (42, 95)], [], [(42, 75)], [],
                    [(42, 85)], [], [(36, 115), (42, 80)], [(36, 95)],
                    [(38, 127), (42, 95)], [], [(42, 75)], [(46, 85)]
                ]
            },
            # 3. Modern Trap 808 (138 BPM)
            {
                "name": "Modern Trap 808",
                "bpm": 138,
                "steps": [
                    [(36, 127), (42, 100)], [(42, 70)], [(42, 95)], [(42, 70)],
                    [(39, 120), (42, 100)], [(42, 70)], [(42, 95)], [(36, 115), (42, 80)],
                    [(42, 100)], [(42, 70)], [(42, 95)], [(36, 110)],
                    [(39, 125), (42, 100)], [(42, 70)], [(42, 110)], [(42, 85)]
                ]
            },
            # 4. Deep House 4-on-Floor (124 BPM)
            {
                "name": "Deep House 4-on-Floor",
                "bpm": 124,
                "steps": [
                    [(36, 122), (42, 75)], [], [(46, 95)], [],
                    [(36, 120), (39, 110), (42, 75)], [], [(46, 95)], [],
                    [(36, 122), (42, 75)], [], [(46, 95)], [],
                    [(36, 120), (39, 110), (42, 75)], [], [(46, 95)], []
                ]
            },
            # 5. Acoustic Pop / Rock (104 BPM)
            {
                "name": "Acoustic Pop / Rock",
                "bpm": 104,
                "steps": [
                    [(36, 118), (42, 90)], [], [(42, 75)], [],
                    [(38, 122), (42, 95)], [], [(42, 75)], [],
                    [(36, 115), (42, 90)], [], [(36, 95), (42, 75)], [],
                    [(38, 122), (42, 95)], [], [(42, 80)], [(36, 85)]
                ]
            },
            # 6. Neo-Soul / Funk Pocket (94 BPM)
            {
                "name": "Neo-Soul / Funk Pocket",
                "bpm": 94,
                "steps": [
                    [(36, 115), (42, 90)], [], [(42, 70)], [],
                    [(38, 118), (42, 90)], [(38, 55)], [(36, 85), (42, 70)], [(46, 85)],
                    [(42, 85)], [], [(36, 110), (42, 75)], [(36, 75)],
                    [(38, 120), (42, 90)], [], [(42, 75)], [(38, 60)]
                ]
            },
            # 7. Jazz Swing Ride (118 BPM)
            {
                "name": "Jazz Swing Ride",
                "bpm": 118,
                "steps": [
                    [(51, 95), (36, 60)], [], [(51, 65)], [],
                    [(51, 90), (44, 85)], [], [(51, 80)], [],
                    [(51, 95), (36, 55)], [], [(51, 65)], [],
                    [(51, 90), (44, 85)], [], [(51, 85)], []
                ]
            },
            # 8. Afrobeat / Latin Groove (108 BPM)
            {
                "name": "Afrobeat / Latin Groove",
                "bpm": 108,
                "steps": [
                    [(36, 120), (42, 85)], [(37, 100)], [(42, 75)], [(36, 95)],
                    [(37, 105), (42, 85)], [], [(36, 110), (42, 75)], [(37, 95)],
                    [(42, 85)], [(36, 100), (37, 100)], [(42, 75)], [],
                    [(37, 110), (42, 85)], [(36, 90)], [(46, 85)], [(37, 95)]
                ]
            },
            # 9. Underground Tekno 150 BPM (Hard Kick & Offbeat Hats)
            {
                "name": "Tekno Hard / Acid",
                "bpm": 150,
                "steps": [
                    [(36, 127)], [(42, 70)], [(46, 110)], [(42, 70)],
                    [(36, 127)], [(42, 70)], [(46, 110)], [(42, 70)],
                    [(36, 127)], [(42, 70)], [(46, 110)], [(42, 70)],
                    [(36, 127)], [(42, 70)], [(46, 110)], [(38, 90), (42, 70)]
                ]
            },
            # 10. Flamenco Rumba (102 BPM - Cajón Agudo & Grave)
            {
                "name": "Flamenco Rumba",
                "bpm": 102,
                "steps": [
                    [(36, 120), (42, 85)], [(42, 70)], [(38, 115)], [(42, 75)],
                    [(36, 95)], [(38, 110)], [(42, 85)], [(38, 105)],
                    [(36, 120), (42, 85)], [(42, 70)], [(38, 115)], [(42, 75)],
                    [(36, 100)], [(38, 110)], [(42, 90)], [(38, 115)]
                ]
            },
            # 11. Flamenco Bulerías (12-beat compás accents: 3, 6, 8, 10, 12)
            {
                "name": "Flamenco Bulerías",
                "bpm": 180,
                "steps": [
                    [(42, 75)], [(42, 75)], [(38, 127), (36, 110)], [(42, 75)],
                    [(42, 75)], [(38, 127), (36, 110)], [(42, 75)], [(38, 127)],
                    [(42, 75)], [(38, 127), (36, 110)], [(42, 75)], [(38, 127), (36, 110)],
                    [], [], [], []
                ]
            },
            # 12. Reggaeton / Dembow (95 BPM)
            {
                "name": "Reggaeton Dembow",
                "bpm": 95,
                "steps": [
                    [(36, 125)], [], [], [(38, 115)],
                    [(36, 120)], [], [(38, 115)], [],
                    [(36, 125)], [], [], [(38, 115)],
                    [(36, 120)], [], [(38, 115)], []
                ]
            },
            # 13. Drum & Bass / Jungle 174 BPM
            {
                "name": "Drum & Bass Break",
                "bpm": 174,
                "steps": [
                    [(36, 127), (42, 90)], [], [(42, 80)], [],
                    [(38, 125), (42, 90)], [], [(42, 75)], [(36, 110)],
                    [], [(36, 115)], [(38, 125), (42, 95)], [],
                    [(42, 80)], [(38, 85)], [(42, 85)], []
                ]
            },
            # 14. Bossa Nova Smooth (128 BPM)
            {
                "name": "Bossa Nova Smooth",
                "bpm": 128,
                "steps": [
                    [(36, 110), (37, 95), (42, 80)], [], [(42, 70)], [(37, 90)],
                    [(42, 80)], [], [(36, 105), (37, 95), (42, 75)], [],
                    [(42, 80)], [(37, 90)], [(36, 110), (42, 75)], [],
                    [(37, 95), (42, 80)], [], [(42, 70)], [(37, 85)]
                ]
            },
            # 15. Synthwave 80s Drive (115 BPM)
            {
                "name": "Synthwave 80s Drive",
                "bpm": 115,
                "steps": [
                    [(36, 125), (42, 90)], [(42, 70)], [(42, 85)], [(42, 70)],
                    [(38, 127), (42, 90)], [(42, 70)], [(42, 85)], [(42, 70)],
                    [(36, 120), (42, 90)], [(42, 70)], [(36, 110), (42, 85)], [(42, 70)],
                    [(38, 127), (42, 90)], [(42, 70)], [(42, 85)], [(36, 95), (42, 75)]
                ]
            },
            # 16. Minimal Microhouse (122 BPM)
            {
                "name": "Minimal Microhouse",
                "bpm": 122,
                "steps": [
                    [(36, 115), (42, 65)], [], [(37, 80)], [(42, 70)],
                    [(36, 110)], [(42, 65)], [(38, 95)], [],
                    [(36, 115), (42, 70)], [], [(37, 85)], [(42, 65)],
                    [(36, 110)], [(46, 85)], [(38, 90)], [(42, 60)]
                ]
            }
        ]
        self.base_bpm: int = 90
        self.base_loop_duration: float = 0.0

    def set_bpm(self, new_bpm: int):
        self.bpm = max(30, min(210, new_bpm))
        if self.base_bpm > 0 and self.base_loop_duration > 0:
            scale = self.base_bpm / float(self.bpm)
            self.loop_duration = self.base_loop_duration * scale
        if self.state in ["PLAYING", "OVERDUBBING"]:
            print(f"[LOOPER] BPM ajustado en vivo: {self.bpm} BPM (Duración: {self.loop_duration:.2f}s)", flush=True)

    def toggle_revoice_mode(self):
        """Conmuta el modo de re-instrumentación de las pistas grabadas:
        - Modo Bloqueo (False): Cada pista conserva el instrumento con el que se grabó.
        - Modo Re-Voice Global (True): Todas las pistas de teclado cambian en tiempo real al instrumento activo.
        """
        self.revoice_mode = not self.revoice_mode
        st = "RE-VOICE ALL (Todas las capas siguen instrumento activo)" if self.revoice_mode else "MULTI-INSTRUMENT LOCK (Cada capa bloqueada a su instrumento)"
        print(f"\n[LOOPER 🔀 RE-VOICE MODE] -> {st}", flush=True)
        self._play_chime("play" if self.revoice_mode else "pause")

    def remove_recent_note(self, channel: int, note: int, window: float = 1.0):
        with self.lock:
            for trk in range(8):
                if not self.tracks[trk]:
                    continue
                max_t = max(ev[0] for ev in self.tracks[trk])
                threshold = max(0.0, max_t - window)
                self.tracks[trk] = [
                    ev for ev in self.tracks[trk]
                    if not (ev[1] == channel and ev[2] == note and ev[0] >= threshold)
                ]

    def tap_rec_button(self):
        """Workflow profesional HÍBRIDO con Auto-Cierre & Multi-Pista 8 Slots:
        1. Estado ARMED: Suena claqueta a BPM de K3.
        2. Disparo por Primera Nota: Comienza t=0.0.
        3. Cierre Inteligente / Auto-Cierre: Redondeo exacto a compases musicales (o auto-cierre a los 4 compases).
        4. Overdub: Asigna dinámicamente el menor slot libre disponible entre 1 y 7 (0-indexed).
        """
        self.preset_idx = None

        if self.state in ["IDLE", "PAUSED"]:
            # ENTRAR EN MODO ARMED (8 pistas limpias)
            with self.lock:
                for i in range(8):
                    self.tracks[i].clear()
                    self.track_muted[i] = False
                    self.track_prog[i] = None
                self.current_track = 0
                self.state = "ARMED"
                self.loop_duration = 0.0
                self.base_loop_duration = 0.0
                self.stop_event.clear()

            print(f"\n[LOOPER ⏱ ARMED] Metrónomo activo a {self.bpm} BPM. Escucha el compás y toca cuando estés listo...", flush=True)
            self._play_chime("armed")
            self.metro_thread = threading.Thread(target=self._run_armed_metronome, daemon=True)
            self.metro_thread.start()

        elif self.state == "ARMED":
            self.stop_all()

        elif self.state == "RECORDING":
            # CIERRE MANUAL O FORZADO
            now = time.perf_counter()
            elapsed = max(0.01, now - self.rec_start_time)
            beat_dur = 60.0 / self.bpm
            bar_dur = 4.0 * beat_dur

            raw_bars = elapsed / bar_dur
            bars = max(1, round(raw_bars))
            self.base_loop_duration = bars * bar_dur
            self.loop_duration = self.base_loop_duration

            # Registrar programa activo para esta pista
            if self.controller:
                curr_lib = OCTAVE_INSTRUMENT_LIBRARIES.get(max(-3, min(3, (self.controller.lowest_base_c - 48) // 12)), OCTAVE_INSTRUMENT_LIBRARIES[0])
                self.track_prog[0] = curr_lib[self.controller.current_melodic_idx][0]

            with self.lock:
                wrapped = []
                for ev in self.tracks[0]:
                    t, ch, n, v, is_on = ev[:5]
                    prg = ev[5] if len(ev) > 5 else self.track_prog[0]
                    if t <= self.base_loop_duration:
                        wrapped.append((t, ch, n, v, is_on, prg))
                    elif t <= (self.base_loop_duration + 0.35 * bar_dur):
                        wrapped.append((t % self.base_loop_duration, ch, n, v, is_on, prg))
                wrapped.sort(key=lambda x: x[0])
                self.tracks[0] = wrapped
                self.state = "PLAYING"
                self.finish_pending = False

            total_evs = len(self.tracks[0])
            total_beats = bars * 4
            print(f"\n[LOOPER ▶ PLAY] Bucle cerrado con redondeo inteligente: {bars} compás(es) ({total_beats} pulsos, {self.loop_duration:.2f}s) con {total_evs} notas grabadas.", flush=True)
            self._play_chime("end_rec")
            self._start_playback_thread()

        elif self.state == "PLAYING":
            # ENTER OVERDUB MODE: Asignar dinámicamente el menor slot disponible entre 1 y 7
            self._push_history()
            next_trk = None
            for idx in range(1, 8):
                if len(self.tracks[idx]) == 0:
                    next_trk = idx
                    break
            if next_trk is None:
                # Si las 8 pistas están ocupadas, reutilizar el slot de overdub actual
                next_trk = (self.current_track + 1) % 8
                if next_trk == 0:
                    next_trk = 1

            self.current_track = next_trk
            self.track_muted[self.current_track] = False
            if self.controller:
                curr_lib = OCTAVE_INSTRUMENT_LIBRARIES.get(max(-3, min(3, (self.controller.lowest_base_c - 48) // 12)), OCTAVE_INSTRUMENT_LIBRARIES[0])
                self.track_prog[self.current_track] = curr_lib[self.controller.current_melodic_idx][0]
            self.state = "OVERDUBBING"
            print(f"\n[LOOPER 🟠 OVERDUB] ¡Grabando en Pista {self.current_track + 1} de 8! Pulsa D1+Pad 1 para cerrar.", flush=True)
            self._play_chime("overdub")

        elif self.state == "OVERDUBBING":
            # FINISH OVERDUB -> RETURN TO PLAY
            self.state = "PLAYING"
            with self.lock:
                self.tracks[self.current_track].sort(key=lambda x: x[0])
            n_notes = len(self.tracks[self.current_track])
            print(f"\n[LOOPER ▶ PLAY] Pista {self.current_track + 1} completada ({n_notes} notas grabadas).", flush=True)
            self._play_chime("play")

    def record_event(self, channel: int, note: int, velocity: int, is_note_on: bool):
        now = time.perf_counter()
        trk_prog = None
        if channel == 0 and self.controller:
            curr_lib = OCTAVE_INSTRUMENT_LIBRARIES.get(max(-3, min(3, (self.controller.lowest_base_c - 48) // 12)), OCTAVE_INSTRUMENT_LIBRARIES[0])
            trk_prog = curr_lib[self.controller.current_melodic_idx][0]

        # Si el Looper está en modo ARMED y el músico toca la primera nota:
        if self.state == "ARMED" and is_note_on:
            with self.lock:
                self.state = "RECORDING"
                self.rec_start_time = now
                self.base_bpm = self.bpm
                self.finish_pending = False
                self.tracks[0].clear()
                self.track_prog[0] = trk_prog
                # Cuantización de grid de 16avos: t=0.0
                self.tracks[0].append((0.0, channel, note, velocity, is_note_on, trk_prog))
            print(f"\n[LOOPER 🔴 REC] ¡Primera nota detectada! Grabación iniciada a {self.bpm} BPM...", flush=True)
            self._play_chime("start_rec")
            return

        elif self.state == "RECORDING":
            raw_offset = max(0.0, now - self.rec_start_time)
            # Cuantización a rejilla musical de semicorcheas (1/16th)
            step_grid = 60.0 / (self.bpm * 4.0)
            quantized_offset = round(raw_offset / step_grid) * step_grid

            # Auto-cierre automático de grabación si se alcanzan los compases predeterminados (ej: 4 compases = 16 beats)
            beat_dur = 60.0 / self.bpm
            max_rec_dur = self.auto_close_bars * 4.0 * beat_dur
            if raw_offset >= max_rec_dur and is_note_on:
                print(f"\n[LOOPER ⏱ AUTO-CIERRE] Alcanzado límite de {self.auto_close_bars} compases. Cerrando loop automáticamente...", flush=True)
                self.tap_rec_button()
                return

            with self.lock:
                self.tracks[0].append((quantized_offset, channel, note, velocity, is_note_on, trk_prog))

        elif self.state == "OVERDUBBING" and self.loop_duration > 0:
            phase = (now - self.cycle_start_time) % self.loop_duration
            scale = float(self.bpm) / self.base_bpm if self.base_bpm > 0 else 1.0
            base_phase = phase * scale
            # Cuantización a rejilla de semicorcheas
            step_grid = 60.0 / (self.bpm * 4.0)
            quantized_phase = round(base_phase / step_grid) * step_grid
            with self.lock:
                trk = self.current_track
                self.tracks[trk].append((quantized_phase, channel, note, velocity, is_note_on, trk_prog))

    def _run_armed_metronome(self):
        beat_dur = 60.0 / self.bpm
        beat_idx = 0
        start = time.perf_counter()
        while self.state in ["ARMED", "RECORDING"] and not self.stop_event.is_set():
            target = start + beat_idx * beat_dur
            sleep_dur = target - time.perf_counter()
            if sleep_dur > 0:
                time.sleep(sleep_dur)
            if self.stop_event.is_set() or self.state not in ["ARMED", "RECORDING"]:
                break

            # Sonido de claqueta durante ARMED y RECORDING en Canal 15 (Independiente del bus de batería)
            if self.metronome_active:
                click_note = 76 if (beat_idx % 4 == 0) else 77
                click_vel = 105 if (beat_idx % 4 == 0) else 70
                self.fluid.send(f"prog 15 115\ncc 15 7 115\nnoteon 15 {click_note} {click_vel}\n")

            beat_idx += 1

    def toggle_track_mute(self, track_idx: int):
        """Silenciar o activar una de las 8 pistas (Pads 5..8 Bank A: 1..4 | Bank B: 5..8)."""
        if 0 <= track_idx < 8:
            self.track_muted[track_idx] = not self.track_muted[track_idx]
            status = "🔇 MUTEADA" if self.track_muted[track_idx] else "🔊 ACTIVA"
            n_notes = len(self.tracks[track_idx])
            print(f"\n[LOOPER PISTA {track_idx + 1}] -> {status} ({n_notes} notas grabadas)", flush=True)
            if self.track_muted[track_idx]:
                # Chime grave tenue (Mute)
                self.fluid.send("cc 0 123 0\ncc 9 123 0")
                self._play_chime("track_mute")
            else:
                # Chime agudo brillante (Unmute)
                self._play_chime("track_unmute")

    def delete_track(self, track_idx: int):
        """Borrar individualmente una de las 8 pistas (Pads 5..8 sostenido > 1.0s)."""
        if 0 <= track_idx < 8:
            with self.lock:
                self.tracks[track_idx].clear()
                self.track_muted[track_idx] = False
                self.track_prog[track_idx] = None
            self.fluid.send("cc 0 123 0\ncc 9 123 0")
            print(f"\n[LOOPER 🗑 BORRADO] Pista {track_idx + 1} vaciada por completo. Slot liberado dinámicamente.", flush=True)
            self._play_chime("track_deleted")

    def toggle_play_pause(self):
        if self.state in ["PLAYING", "OVERDUBBING"]:
            self.state = "PAUSED"
            self.stop_internal()
            print("\n[LOOPER ⏸ PAUSA] Bucle pausado.", flush=True)
            self._play_chime("pause")
        elif self.state == "PAUSED" and self.loop_duration > 0:
            self.state = "PLAYING"
            self.stop_event.clear()
            self._start_playback_thread()
            print("\n[LOOPER ▶ PLAY] Bucle reanudado.", flush=True)
            self._play_chime("play")

    def _push_history(self):
        # Save snapshot of all 8 tracks for undo
        snapshot = [list(trk) for trk in self.tracks]
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > 10:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self) -> bool:
        with self.lock:
            if not self.undo_stack:
                print("\n[LOOPER ↩ UNDO] No hay más acciones para deshacer.", flush=True)
                return False
            # Save current state into redo stack
            current_state = [list(trk) for trk in self.tracks]
            self.redo_stack.append(current_state)
            previous_state = self.undo_stack.pop()
            self.tracks = [list(trk) for trk in previous_state]
            # If all tracks empty, stop loop
            if all(len(trk) == 0 for trk in self.tracks):
                self.stop_internal()
                self.state = "IDLE"
                self.loop_duration = 0.0

        # Cut any active notes cleanly
        self.fluid.send("cc 0 123 0\ncc 9 123 0")
        print("\n[LOOPER ↩ UNDO] Última capa/toma deshecha con éxito.", flush=True)
        self._play_chime("undo")
        return True

    def redo(self) -> bool:
        with self.lock:
            if not self.redo_stack:
                print("\n[LOOPER ↪ REDO] No hay acciones para rehacer.", flush=True)
                return False
            # Save current into undo stack
            current_state = [list(trk) for trk in self.tracks]
            self.undo_stack.append(current_state)
            next_state = self.redo_stack.pop()
            self.tracks = [list(trk) for trk in next_state]
            if self.state == "IDLE" and self.loop_duration > 0:
                self.state = "PLAYING"
                self._start_playback_thread()

        print("\n[LOOPER ↪ REDO] Capa/toma recuperada con éxito.", flush=True)
        self._play_chime("redo")
        return True

    def clear(self):
        with self.lock:
            self._push_history()
            self.stop_internal()
            for i in range(8):
                self.tracks[i].clear()
                self.track_muted[i] = False
                self.track_prog[i] = None
            self.current_track = 0
            self.loop_duration = 0.0
            self.state = "IDLE"
            self.preset_idx = None
        print("\n[LOOPER 🗑 RESET TOTAL] Todas las 8 pistas borradas. Sesión reseteada.", flush=True)
        self._play_chime("clear")

    def toggle_metronome(self):
        self.metronome_active = not self.metronome_active
        status = "ACTIVADO (Tick ⏱)" if self.metronome_active else "DESACTIVADO (Muteado)"
        print(f"\n[METRÓNOMO] -> {status} a {self.bpm} BPM", flush=True)
        def _worker():
            try:
                self.fluid.send("prog 15 8\ncc 15 91 80")
                if self.metronome_active:
                    self.fluid.send("noteon 15 84 90")
                    time.sleep(0.08)
                    self.fluid.send("noteoff 15 84")
                else:
                    self.fluid.send("noteon 15 60 75")
                    time.sleep(0.08)
                    self.fluid.send("noteoff 15 60")
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def register_key_note(self, note: int):
        """Measures incoming note intervals from keyboard/arpeggiator.
        When steady arpeggiated repetition is detected, calculates the matching BPM.
        """
        now = time.time()
        self.last_key_note_times.append(now)
        # Keep only the last 8 note timestamps
        if len(self.last_key_note_times) > 8:
            self.last_key_note_times.pop(0)

        if len(self.last_key_note_times) >= 4:
            # Check intervals between consecutive notes
            intervals = [
                self.last_key_note_times[i] - self.last_key_note_times[i - 1]
                for i in range(1, len(self.last_key_note_times))
            ]
            avg_interval = sum(intervals) / len(intervals)
            # Arpeggiator note repetition should be consistent (deviation < 25%)
            is_steady = all(abs(dt - avg_interval) < (avg_interval * 0.28) for dt in intervals)

            if is_steady and avg_interval > 0.05:
                # Default Akai MPK arpeggiator step is typically 1/16th or 1/8th note.
                # For 1/16th note: beat (1/4) = 4 * interval -> BPM = 60 / (4 * interval) = 15 / interval
                # For 1/8th note:  beat (1/4) = 2 * interval -> BPM = 60 / (2 * interval) = 30 / interval
                # If interval is between 0.075s and 0.35s, it is usually 1/16th note arpeggio:
                cand_16th = 15.0 / avg_interval
                cand_8th = 30.0 / avg_interval

                # Pick the division that produces a standard musical BPM between 45 and 210:
                if 45 <= cand_16th <= 210:
                    detected = int(round(cand_16th))
                elif 45 <= cand_8th <= 210:
                    detected = int(round(cand_8th))
                else:
                    detected = None

                if detected is not None:
                    self.detected_arp_bpm = detected
                    self.last_arp_detected_time = now

    def play_preset(self, idx: int):
        if idx >= len(self.preset_patterns):
            return
        if self.state == "PRESET" and self.preset_idx == idx:
            self.stop_all()
            return
        self.stop_all()
        self.preset_idx = idx

        # If arpeggiator notes were actively detected within the last 5 seconds, use that exact BPM
        now = time.time()
        if self.detected_arp_bpm is not None and (now - self.last_arp_detected_time) < 5.0:
            self.bpm = self.detected_arp_bpm
            bpm_source = f"Auto-Sync Arpegiador ({self.detected_arp_bpm} BPM)"
        else:
            self.bpm = self.preset_patterns[idx]["bpm"]
            bpm_source = f"Preset Default ({self.bpm} BPM)"

        self.state = "PRESET"
        self.stop_event.clear()
        self.play_thread = threading.Thread(target=self._run_preset_loop, daemon=True)
        self.play_thread.start()
        name = self.preset_patterns[idx]["name"]
        print(f"\n[PRESET BEAT ▶] '{name}' a {self.bpm} BPM [{bpm_source}]", flush=True)

    def stop_all(self):
        self.stop_internal()
        if self.state == "PRESET":
            self.state = "IDLE"
            self.preset_idx = None
        elif self.state in ["RECORDING", "OVERDUBBING", "PLAYING"]:
            self.state = "PAUSED"
        print("\n[LOOPER ⏹ STOP] Todo detenido.", flush=True)

    def stop_internal(self):
        self.stop_event.set()
        self.fluid.send("cc 0 123 0\ncc 9 123 0\ncc 0 120 0\ncc 9 120 0")

    def _start_playback_thread(self):
        self.stop_event.clear()
        self.play_thread = threading.Thread(target=self._run_playback, daemon=True)
        self.play_thread.start()

    def _run_rec_metronome(self):
        beat_dur = 60.0 / self.bpm
        beat_idx = 0
        start = self.rec_start_time
        while self.state == "RECORDING" and not self.stop_event.is_set():
            target = start + beat_idx * beat_dur
            sleep_dur = target - time.perf_counter()
            if sleep_dur > 0:
                time.sleep(sleep_dur)
            if self.state != "RECORDING" or self.stop_event.is_set():
                break
            if self.metronome_active:
                click_note = 76 if (beat_idx % 4 == 0) else 77
                click_vel = 105 if (beat_idx % 4 == 0) else 70
                self.fluid.send(f"prog 15 115\ncc 15 7 115\nnoteon 15 {click_note} {click_vel}\n")
            beat_idx += 1

    def _run_playback(self):
        last_played_prog = None
        while not self.stop_event.is_set() and self.state in ["PLAYING", "OVERDUBBING"]:
            self.cycle_start_time = time.perf_counter()
            dur = self.loop_duration
            if dur <= 0:
                time.sleep(0.01)
                continue

            # Recolectar notas activas de las 8 pistas no silenciadas
            evs = []
            with self.lock:
                for trk_idx in range(8):
                    if not self.track_muted[trk_idx]:
                        evs.extend(self.tracks[trk_idx])
            evs.sort(key=lambda x: x[0])
            idx = 0
            n_evs = len(evs)

            while not self.stop_event.is_set() and self.state in ["PLAYING", "OVERDUBBING"]:
                now = time.perf_counter()
                elapsed = now - self.cycle_start_time
                if elapsed >= dur:
                    break

                scale = (self.base_bpm / float(self.bpm)) if (self.base_bpm > 0 and self.bpm > 0) else 1.0
                is_full = bool(self.controller and getattr(self.controller, "keys_full_level", False))
                while idx < n_evs:
                    ev = evs[idx]
                    scaled_t = ev[0] * scale
                    if scaled_t <= elapsed:
                        t, ch, n, v, is_on = ev[:5]
                        ev_prog = ev[5] if len(ev) > 5 else None

                        # Voice Lock: Si Re-Voice mode está apagado y la pista tiene un instrumento propio registrado, conmutar antes de tocar
                        if ch == 0 and not self.revoice_mode and ev_prog is not None:
                            if ev_prog != last_played_prog:
                                self.fluid.send(f"prog 0 {ev_prog}")
                                last_played_prog = ev_prog

                        if is_on:
                            if is_full and ch == 0:
                                play_v = 127
                            else:
                                play_v = min(127, max(45, int(v * 1.30 + 15)))
                            self.fluid.send(f"noteon {ch} {n} {play_v}")
                        else:
                            self.fluid.send(f"noteoff {ch} {n}")
                        idx += 1
                    else:
                        break

                time.sleep(0.001)

    def _run_preset_loop(self):
        pat = self.preset_patterns[self.preset_idx]["steps"]
        step_idx = 0
        next_step_time = time.perf_counter()
        while not self.stop_event.is_set() and self.state == "PRESET":
            step_dur = (60.0 / self.bpm) / 4.0
            notes = pat[step_idx]
            for note, vel in notes:
                self.fluid.send(f"noteon 9 {note} {vel}")
            step_idx = (step_idx + 1) % 16
            next_step_time += step_dur
            delay = next_step_time - time.perf_counter()
            if delay > 0:
                if self.stop_event.wait(delay):
                    break
            else:
                next_step_time = time.perf_counter()

    def _play_chime(self, kind: str):
        if self.controller and getattr(self.controller, "mute_function_sounds", False):
            return
        def _worker():
            try:
                self.fluid.send("prog 15 8\ncc 15 7 55\ncc 15 91 80")
                if kind in ["rec", "start_rec"]:
                    # Chime ascendente de inicio de grabación (Do-Mi agudos)
                    self.fluid.send("noteon 15 84 65\n")
                    time.sleep(0.06)
                    self.fluid.send("noteoff 15 84\nnoteon 15 88 70\n")
                    time.sleep(0.1)
                    self.fluid.send("noteoff 15 88\n")
                elif kind in ["play", "end_rec"]:
                    # Chime resolutivo cristalino de cierre de bucle y loop activo
                    self.fluid.send("noteon 15 72 65\n")
                    time.sleep(0.06)
                    self.fluid.send("noteoff 15 72\nnoteon 15 76 65\n")
                    time.sleep(0.08)
                    self.fluid.send("noteoff 15 76\n")
                elif kind == "armed":
                    # Toque suave de preparación para escuchar la claqueta
                    self.fluid.send("noteon 15 79 60\n")
                    time.sleep(0.06)
                    self.fluid.send("noteoff 15 79\n")
                elif kind == "overdub":
                    self.fluid.send("noteon 15 79 65\n")
                    time.sleep(0.06)
                    self.fluid.send("noteoff 15 79\nnoteon 15 83 65\n")
                    time.sleep(0.1)
                    self.fluid.send("noteoff 15 83\n")
                elif kind == "pause":
                    self.fluid.send("noteon 15 76 55\n")
                    time.sleep(0.08)
                    self.fluid.send("noteoff 15 76\nnoteon 15 72 50\n")
                    time.sleep(0.1)
                    self.fluid.send("noteoff 15 72\n")
                elif kind == "track_mute":
                    # Tono grave suave apagado (Do grave)
                    self.fluid.send("noteon 15 48 60\n")
                    time.sleep(0.08)
                    self.fluid.send("noteoff 15 48\n")
                elif kind == "track_unmute":
                    # Tono agudo brillante (Do agudo)
                    self.fluid.send("noteon 15 72 65\n")
                    time.sleep(0.08)
                    self.fluid.send("noteoff 15 72\n")
                elif kind == "track_deleted":
                    # Acorde suave de disolución (Mi-Do grave)
                    self.fluid.send("noteon 15 64 60\n")
                    time.sleep(0.07)
                    self.fluid.send("noteoff 15 64\nnoteon 15 52 55\n")
                    time.sleep(0.12)
                    self.fluid.send("noteoff 15 52\n")
                elif kind == "undo":
                    # Chime suave descendente de acción deshecha (Sol -> Mi)
                    self.fluid.send("noteon 15 79 60\n")
                    time.sleep(0.06)
                    self.fluid.send("noteoff 15 79\nnoteon 15 76 55\n")
                    time.sleep(0.08)
                    self.fluid.send("noteoff 15 76\n")
                elif kind == "redo":
                    # Chime ascendente brillante de acción recuperada (Mi -> Sol)
                    self.fluid.send("noteon 15 76 60\n")
                    time.sleep(0.06)
                    self.fluid.send("noteoff 15 76\nnoteon 15 79 65\n")
                    time.sleep(0.08)
                    self.fluid.send("noteoff 15 79\n")
                elif kind == "clear":
                    self.fluid.send("noteon 15 64 55\n")
                    time.sleep(0.08)
                    self.fluid.send("noteoff 15 64\nnoteon 15 60 50\n")
                    time.sleep(0.1)
                    self.fluid.send("noteoff 15 60\n")
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

class AdvancedAkaiController:
    def __init__(self):
        self.held_keyboard_notes: Dict[int, float] = {}
        self.current_melodic_idx: int = 0
        self.current_drum_idx: int = 0
        self.pad_bank: str = "A"
        self.drum_muted: bool = False
        self.keys_muted: bool = False
        self.sustain_active: bool = False
        self.portamento_active: bool = False
        self.last_sustain_press: float = 0.0
        self.last_portamento_press: float = 0.0
        self.last_drum_mute_press: float = 0.0
        self.last_keys_mute_press: float = 0.0
        self.shutdown_timer: Optional[threading.Timer] = None
        self.full_level_timer: Optional[threading.Timer] = None
        self.modifier_timer: Optional[threading.Timer] = None
        self.modifier_active_mode: Optional[str] = None
        self.startup_sound_played: bool = False
        self.running = True
        self.keys_full_level: bool = False
        self.mute_function_sounds: bool = False
        self.master_knob_val: int = 127
        self.drum_knob_val: int = 100
        self.current_drum_volume: int = 100
        self.sustain_decay_seconds: float = 5.0
        self.active_note_timers: Dict[int, threading.Timer] = {}
        self.lowest_base_c: Optional[int] = 48  # C1 físico por defecto en MPK Mini
        self.looper_pad_press_times: Dict[int, float] = {}
        self.looper_pad_hold_timers: Dict[int, threading.Timer] = {}
        self.last_undo_tap_time: float = 0.0
        self.looper = LiveMidiLooper(fluid, controller=self)
        # Enable FluidSynth effects engines & set responsive velocity curve
        fluid.send("reverb on\nchorus on\n")
        self.apply_key_velocity_router()

    def apply_key_velocity_router(self):
        if self.keys_full_level:
            # FULL LEVEL: Fuerza 127 de velocidad en todas las teclas (Canal 1 / index 0)
            # BLOQUEA por completo el paso directo de notas en los canales 1..15 por ALSA.
            # Los pads de batería (Canal 10 / index 9) son reenviados exclusivamente por Python
            # cuando no hay modificador presionado. ¡Cero fugas de sonido!
            cmds = [
                'router_clear',
                'router_begin cc', 'router_end',
                'router_begin prog', 'router_end',
                'router_begin pbend', 'router_end',
                'router_begin cpress', 'router_end',
                'router_begin note',
                'router_chan 0 0 1 0',
                'router_par2 1 127 0 127',
                'router_end'
            ]
        else:
            # Modo dinámico con curva mejorada (para no tener que aporrear las teclas)
            cmds = [
                'router_clear',
                'router_begin cc', 'router_end',
                'router_begin prog', 'router_end',
                'router_begin pbend', 'router_end',
                'router_begin cpress', 'router_end',
                'router_begin note',
                'router_chan 0 0 1 0',
                'router_par2 1 127 0.75 32',
                'router_end'
            ]
        for c in cmds:
            fluid.send(c)

    def play_chime(self, active: bool):
        """Play elegant, soft musical chime on isolated Channel 15 (Celesta) for system feedback."""
        if getattr(self, "mute_function_sounds", False):
            return
        def _worker():
            try:
                fluid.send("prog 15 8")       # Celesta / Campanas suaves
                fluid.send("cc 15 7 55")      # Volumen suave calibrado para feedback discreto (no estridente)
                fluid.send("cc 15 91 85")     # Reverb cálida
                if active:
                    # Chime ascendente cristalino y suave (Do-Mi-Sol-Do)
                    for n in [72, 76, 79, 84]:
                        fluid.send(f"noteon 15 {n} 65")
                        time.sleep(0.055)
                        fluid.send(f"noteoff 15 {n}")
                else:
                    # Chime descendente tenue y relajante (Sol-Mi-Do)
                    for n in [79, 76, 72]:
                        fluid.send(f"noteon 15 {n} 55")
                        time.sleep(0.075)
                        fluid.send(f"noteoff 15 {n}")
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def toggle_keys_full_level(self, base_c: int):
        self.keys_full_level = not self.keys_full_level
        self.apply_key_velocity_router()
        # Silenciar de inmediato el choque disonante de graves de las dos teclas C1 y C#1
        try:
            fluid.send(f"noteoff 0 {base_c}")
            fluid.send(f"noteoff 0 {base_c + 1}")
        except Exception:
            pass

        if self.keys_full_level:
            print("\n[FULL LEVEL TECLADO] -> ACTIVADO (Todas las teclas al 100% de fuerza)", flush=True)
            self.play_chime(active=True)
        else:
            print("\n[FULL LEVEL TECLADO] -> DESACTIVADO (Modo dinámico expresivo)", flush=True)
            self.play_chime(active=False)

    def play_startup_sound(self):
        """Play elegant ascending musical startup chime through Roland S-1 to signal system readiness."""
        def _worker():
            try:
                time.sleep(0.5)
                chime_notes = [60, 64, 67, 72, 76, 84]
                for n in chime_notes:
                    fluid.send(f"noteon 0 {n} 70")
                    time.sleep(0.12)
                time.sleep(1.0)
                for n in chime_notes:
                    fluid.send(f"noteoff 0 {n}")
                print("[STARTUP CHIME] Sistema listo y audio activo.", flush=True)
            except Exception as e:
                print(f"[STARTUP CHIME ERROR] {e}", flush=True)
        threading.Thread(target=_worker, daemon=True).start()

    def start_shutdown_timer(self):
        if self.shutdown_timer is None:
            # Silenciar de inmediato las notas extremas C1 y C3 en el piano para evitar el choque sonoro estridente
            try:
                active = sorted(list(self.held_keyboard_notes.keys()))
                if len(active) >= 2:
                    fluid.send(f"noteoff 0 {active[0]}\nnoteoff 0 {active[-1]}")
            except Exception:
                pass

            print("\n[AVISO APAGADO] Mantén pulsadas ambas teclas C1 y C3 durante 2 segundos para apagar el sistema...", flush=True)

            # Toque sutil de aviso (Do central apagado en canal 15 Celesta)
            def _subtle_warning():
                if getattr(self, "mute_function_sounds", False):
                    return
                try:
                    fluid.send("prog 15 8\ncc 15 91 80\nnoteon 15 67 60")
                    time.sleep(0.08)
                    fluid.send("noteoff 15 67")
                except Exception:
                    pass
            threading.Thread(target=_subtle_warning, daemon=True).start()

            self.shutdown_timer = threading.Timer(2.0, self.execute_safe_shutdown)
            self.shutdown_timer.daemon = True
            self.shutdown_timer.start()

    def cancel_shutdown_timer(self):
        if self.shutdown_timer is not None:
            self.shutdown_timer.cancel()
            self.shutdown_timer = None

    def start_full_level_timer(self, base_c: int):
        if self.full_level_timer is None:
            def _toggle():
                self.toggle_keys_full_level(base_c)
                self.full_level_timer = None

            self.full_level_timer = threading.Timer(2.0, _toggle)
            self.full_level_timer.daemon = True
            self.full_level_timer.start()

    def cancel_full_level_timer(self):
        if self.full_level_timer is not None:
            self.full_level_timer.cancel()
            self.full_level_timer = None

    def start_modifier_timer(self, key_type: str, note: int):
        if self.modifier_timer is None:
            def _on_selection_ready():
                self.modifier_active_mode = key_type
                # Fijar explícitamente el Do base activo de esta octava
                base = note if (key_type == "melodic") else (note - 1)
                self.lowest_base_c = base

                # Silenciar de inmediato en FluidSynth la nota que se estaba manteniendo para dejar paso limpio al chime
                try:
                    fluid.send(f"noteoff 0 {note}\ncc 0 120 0\ncc 0 123 0")
                except Exception:
                    pass
                # Sonido de confirmación: chime cristalino notificando que está en Modo Selección
                if key_type == "melodic":
                    print("\n[MODO SELECCIÓN ACTIVADO] Teclado -> Toca cualquier tecla para elegir Instrumento Melódico", flush=True)
                    self.play_chime(active=True)
                else:
                    print("\n[MODO SELECCIÓN ACTIVADO] Batería -> Toca cualquier tecla para elegir Kit de Batería", flush=True)
                    self.play_chime(active=True)
                self.modifier_timer = None

            self.modifier_timer = threading.Timer(2.0, _on_selection_ready)
            self.modifier_timer.daemon = True
            self.modifier_timer.start()

    def cancel_modifier_timer(self):
        if self.modifier_timer is not None:
            self.modifier_timer.cancel()
            self.modifier_timer = None
        self.modifier_active_mode = None

    def execute_safe_shutdown(self):
        print("\n" + "="*65, flush=True)
        print(" [APAGADO SEGURO] Secuencia de apagado confirmada desde el Akai", flush=True)
        print(" Guardando datos y cerrando sistema operativo...", flush=True)
        print("="*65, flush=True)

        # Chime sutil descendente de despedida (lo opuesto exacto a la música de inicio)
        # La música de inicio es: [60, 64, 67, 72, 76, 84] (C4 ascendente)
        # La música de apagado es: [84, 76, 72, 67, 64, 60] suave y gradual en celesta
        try:
            fluid.send("prog 15 8\ncc 15 91 85")
            shutdown_notes = [84, 76, 72, 67, 64, 60]
            for n in shutdown_notes:
                fluid.send(f"noteon 15 {n} 80")
                time.sleep(0.12)
                fluid.send(f"noteoff 15 {n}")
            time.sleep(0.3)
        except Exception:
            pass

        # Ejecutar apagado ordenado del sistema Linux (protegiendo la tarjeta SD)
        subprocess.run(["sudo", "systemctl", "poweroff"])

    def find_mpk_port(self) -> Optional[str]:
        try:
            for port in mido.get_input_names():
                if "mpk" in port.lower() or "akai" in port.lower():
                    return port
        except Exception:
            pass
        return None

    def trigger_looper_pad_press(self, pad_num: int):
        self.looper_pad_press_times[pad_num] = time.time()
        # PAD 1: Rec / Play / Overdub (RPO)
        if pad_num == 0:
            self.looper.tap_rec_button()
        # PAD 2: Re-Voice Mode Toggle (Multi-Instrument Lock vs Re-Voice All)
        elif pad_num == 1:
            self.looper.toggle_revoice_mode()
        # PAD 3: Metronome Toggle (Mute/Unmute)
        elif pad_num == 2:
            self.looper.toggle_metronome()
        # PAD 4: Play/Pause (Tap) / Hold > 1.5s: Clear All Tracks
        elif pad_num == 3:
            now = time.time()
            self.last_undo_tap_time = now
            print("\n[PAD 4 ⏯/🗑] Pulsado (Tap: Play/Pause | Mantén >1.5s: Borrar Todo)", flush=True)

            def _clear_all_action():
                self.looper.clear()
                self.looper_pad_press_times.pop(pad_num, None)

            timer = threading.Timer(1.5, _clear_all_action)
            timer.daemon = True
            self.looper_pad_hold_timers[pad_num] = timer
            timer.start()

        elif pad_num in [4, 5, 6, 7]:  # Pads 5..8: Capas (Bank A: 1..4 | Bank B: 5..8)
            base_slot = 0 if self.pad_bank == "A" else 4
            trk_idx = base_slot + (pad_num - 4)
            print(f"\n[PAD {pad_num + 1} (Bank {self.pad_bank}) 🎚] Pista {trk_idx + 1} (Tap: Mute/Unmute | Mantén >1.0s: Borrar Pista)", flush=True)

            def _delete_action():
                self.looper.delete_track(trk_idx)
                self.looper_pad_press_times.pop(pad_num, None)

            timer = threading.Timer(1.0, _delete_action)
            timer.daemon = True
            self.looper_pad_hold_timers[pad_num] = timer
            timer.start()

    def trigger_looper_pad_release(self, pad_num: int):
        # Cancelar timer de pulsación larga si se suelta antes de cumplirse
        timer = self.looper_pad_hold_timers.pop(pad_num, None)
        if timer is not None:
            timer.cancel()

        press_t = self.looper_pad_press_times.pop(pad_num, None)
        if press_t is not None:
            if pad_num == 3:
                # Pulsación corta (< 1.5s) en Pad 4: Conmutar Play / Pause
                self.looper.toggle_play_pause()
            elif pad_num in [4, 5, 6, 7]:
                # Pulsación corta (< 1.0s): Conmutar Silenciar / Activar (Mute Toggle)
                base_slot = 0 if self.pad_bank == "A" else 4
                trk_idx = base_slot + (pad_num - 4)
                self.looper.toggle_track_mute(trk_idx)

    def trigger_preset_pad(self, pad_num: int):
        # Bank A (Pads 1..8): Presets 0..7 | Bank B (Pads 1..8): Presets 8..15
        base_idx = 0 if self.pad_bank == "A" else 8
        preset_idx = base_idx + pad_num
        if 0 <= preset_idx < len(self.looper.preset_patterns):
            self.looper.play_preset(preset_idx)
        else:
            self.looper.stop_all()

    def handle_note_on(self, note: int, velocity: int, channel: int):
        # Only process keys (Channel 1, which is channel index 0)
        if channel == 0:
            now = time.time()
            self.held_keyboard_notes[note] = now

            # Actualizar la tecla base Do (C) del extremo izquierdo físico adaptándose
            # a cualquier transposición por OCT- / OCT+ (teclado de 25 teclas: base_c .. base_c + 24, rango -4 .. +4 octavas)
            valid_bases = [0, 12, 24, 36, 48, 60, 72, 84, 96]
            if self.lowest_base_c is None:
                self.lowest_base_c = (note // 12) * 12
            else:
                # Ajustar base_c ÚNICAMENTE si la nota física tocada cae fuera de los límites de la ventana actual de 25 teclas.
                # NUNCA reajustar base_c si la nota cae dentro de [lowest_base_c, lowest_base_c + 24]!
                if note < self.lowest_base_c:
                    shift = ((self.lowest_base_c - note + 11) // 12) * 12
                    self.lowest_base_c = max(0, self.lowest_base_c - shift)
                elif note > (self.lowest_base_c + 24):
                    shift = ((note - (self.lowest_base_c + 24) + 11) // 12) * 12
                    self.lowest_base_c = min(96, self.lowest_base_c + shift)

            base_c = self.lowest_base_c

            # Check for Safe Shutdown Key Combo:
            # Hold Lowest C (C1) and Highest C (C3) together for 3.0 seconds (extremos físicos reales)
            active_notes = sorted(list(self.held_keyboard_notes.keys()))
            if len(active_notes) >= 2:
                if (base_c in self.held_keyboard_notes) and ((base_c + 24) in self.held_keyboard_notes):
                    self.start_shutdown_timer()

            # Iniciar temporizador ÚNICAMENTE si se pulsa la tecla Do o Do# del extremo izquierdo físico real (base_c / base_c + 1)
            # NUNCA para Middle C (base_c + 12) ni Middle C# (base_c + 13)
            if note == base_c:
                self.start_modifier_timer("melodic", note)
            elif note == (base_c + 1):
                self.start_modifier_timer("drum", note)

            # SHORTCUT: Mantener C + C# a la vez durante 2.0 segundos para Full Level (extremo izquierdo real)
            if self.looper.state not in ["RECORDING", "OVERDUBBING"] and len(active_notes) >= 2:
                if (base_c in self.held_keyboard_notes) and ((base_c + 1) in self.held_keyboard_notes):
                    self.start_full_level_timer(base_c)

            # SELECCIÓN DE INSTRUMENTO / KIT (Modo Selección confirmado tras 2s de hold):
            if self.looper.state not in ["RECORDING", "OVERDUBBING"] and len(active_notes) >= 2:
                lowest_note = active_notes[0]
                modifier_hold_time = now - self.held_keyboard_notes.get(lowest_note, now)

                # Actúa como modificador ÚNICAMENTE si la nota más grave sostenida es C o C# del extremo izquierdo real
                is_physical_modifier = (lowest_note in [base_c, base_c + 1])
                is_mode_ready = (self.modifier_active_mode is not None or modifier_hold_time >= 2.0)
                if is_physical_modifier and is_mode_ready and note >= (base_c + 2):
                    # MODIFIER 1: Tecla C (Blanca del extremo izquierdo) sostenida >= 2.0s -> CAMBIO MELÓDICO
                    if lowest_note == base_c:
                        fluid.send(f"noteoff 0 {note}\nnoteoff 0 {base_c}")
                        # Calcular índice de octava activa (-3 a +3) respecto a Do base neutral (48)
                        oct_shift = max(-3, min(3, (base_c - 48) // 12))
                        library = OCTAVE_INSTRUMENT_LIBRARIES.get(oct_shift, OCTAVE_INSTRUMENT_LIBRARIES[0])
                        idx = (note - (base_c + 2)) % len(library)
                        self.current_melodic_idx = idx
                        prog_num, name = library[idx]
                        fluid.send(f"prog 0 {prog_num}")
                        print(f"\n[KEYBOARD SELECT] (OCT {oct_shift:+d}) -> Tecla {idx + 1}: {name} (Prog {prog_num})")
                        play_preview(chan=0, note=72, vel=110, duration=0.35)
                        return

                    # MODIFIER 2: Tecla C# (Negra contigua al extremo izquierdo) sostenida >= 2.0s -> CAMBIO BATERÍAS
                    if lowest_note == (base_c + 1):
                        fluid.send(f"noteoff 0 {note}\nnoteoff 0 {base_c + 1}")
                        idx = (note - (base_c + 2)) % len(DRUM_KITS)
                        self.current_drum_idx = idx
                        kit_num, name = DRUM_KITS[idx]
                        fluid.send(f"prog 9 {kit_num}")
                        print(f"\n[DRUM KIT SELECT] -> Tecla {idx + 1}: {name} (Kit {kit_num})")
                        play_preview(chan=9, note=36, vel=120, duration=0.35)
                        return

            # Continuous Instruments Drone Prevention & Re-trigger cut:
            # (Trumpet, Organs, Strings, Synth Basses, Synth Leads, Warm Pad)
            continuous_progs = {16, 19, 38, 39, 48, 50, 56, 65, 80, 81, 88}
            curr_prog = MELODIC_INSTRUMENTS[self.current_melodic_idx][0]
            is_continuous = (curr_prog in continuous_progs)

            # Re-trigger cut: silenciar de inmediato si se vuelve a tocar la misma nota
            old_timer = self.active_note_timers.pop(note, None)
            if old_timer:
                old_timer.cancel()
                fluid.send(f"noteoff 0 {note}")

            if self.sustain_active:
                def _decay_noteoff(target_note: int):
                    # FluidSynth SoundFont voices require explicit noteoff + CC 64 drop to release sustained loop
                    fluid.send(f"noteoff 0 {target_note}")
                    fluid.send("cc 0 64 0")
                    self.active_note_timers.pop(target_note, None)
                    # Restaurar CC 64 a 127 tras 80ms para que el motor de audio procese el fin de ciclo
                    if self.sustain_active:
                        threading.Timer(0.08, lambda: fluid.send("cc 0 64 127") if self.sustain_active else None).start()

                decay_timer = threading.Timer(self.sustain_decay_seconds, _decay_noteoff, args=[note])
                decay_timer.daemon = True
                self.active_note_timers[note] = decay_timer
                decay_timer.start()

            # Registrar la nota para auto-detección de tempo del arpegiador
            self.looper.register_key_note(note)

            # Grabar notas de teclado en el Looper (incluso si está en ARMED para disparar la grabación):
            # IMPORTANTE: Las teclas modificadoras físicas del extremo izquierdo (D = base_c + 2, D# = base_c + 3)
            # NUNCA deben grabarse en el loop ni disparar la grabación durante modo ARMED.
            is_modifier_key = (base_c is not None and note in [base_c + 2, base_c + 3])
            if not is_modifier_key and self.looper.state in ["ARMED", "RECORDING", "OVERDUBBING"]:
                rec_vel = 127 if self.keys_full_level else velocity
                self.looper.record_event(0, note, rec_vel, True)

        # Si se tocan los pads (Canal 10 / index 9 en FluidSynth):
        elif channel == 9:
            # Detectar si estamos en Banco A (< 44) o Banco B (>= 44)
            if note >= 44:
                self.pad_bank = "B"
            else:
                self.pad_bank = "A"

            pad_num = (note - 36) % 8 if note < 44 else (note - 44) % 8

            # Modificadores de teclado para controlar ritmos con los pads:
            # D1  (segunda tecla blanca, base_c + 2) -> LIVE LOOPER (8 pads dedicados)
            # D#1 (segunda tecla negra, base_c + 3)  -> 7 RITMOS PREGRABADOS + STOP
            base_c = self.lowest_base_c
            if self.held_keyboard_notes and base_c is not None:
                is_d_held = (base_c + 2) in self.held_keyboard_notes
                is_ds_held = (base_c + 3) in self.held_keyboard_notes

                if is_d_held:
                    # Mute instantáneo del canal 9 para suprimir cualquier fuga del golpe de percusión
                    fluid.send("cc 9 7 0")
                    for h in [(base_c + 2)]:
                        if h in self.held_keyboard_notes:
                            fluid.send(f"noteoff 0 {h}")
                            self.looper.remove_recent_note(0, h, window=1.0)
                    fluid.send(f"noteoff 9 {note}")
                    self.trigger_looper_pad_press(pad_num)
                    # Restaurar volumen normal de percusión de fondo tras silenciar el golpe
                    threading.Timer(0.04, lambda: fluid.send(f"cc 9 7 {self.current_drum_volume}")).start()
                    return

                if is_ds_held:
                    fluid.send("cc 9 7 0")
                    for h in [(base_c + 3)]:
                        if h in self.held_keyboard_notes:
                            fluid.send(f"noteoff 0 {h}")
                            self.looper.remove_recent_note(0, h, window=1.0)
                    fluid.send(f"noteoff 9 {note}")
                    self.trigger_preset_pad(pad_num)
                    threading.Timer(0.04, lambda: fluid.send(f"cc 9 7 {self.current_drum_volume}")).start()
                    return

            # Si no hay modificador (tocar batería libremente con los pads):
            # Como ALSA Sequencer ya no filtra al canal 9 directo, Python envía la nota con latencia cero:
            fluid.send(f"noteon 9 {note} {velocity}")
            # Grabar golpe de pad en el Looper (incluso si está en ARMED para disparar la grabación):
            if self.looper.state in ["ARMED", "RECORDING", "OVERDUBBING"]:
                self.looper.record_event(9, note, velocity, True)
                # Duración uniforme para percusión de pad (120ms)
                def _pad_noteoff(p_note: int):
                    time.sleep(0.12)
                    if self.looper.state in ["RECORDING", "OVERDUBBING"]:
                        self.looper.record_event(9, p_note, 0, False)
                threading.Thread(target=_pad_noteoff, args=[note], daemon=True).start()

    def handle_note_off(self, note: int, channel: int):
        base_c = self.lowest_base_c
        if channel == 0:
            self.held_keyboard_notes.pop(note, None)
            self.cancel_shutdown_timer()
            self.cancel_full_level_timer()
            if base_c is not None and note in [base_c, base_c + 1]:
                self.cancel_modifier_timer()
            if not self.sustain_active:
                timer = self.active_note_timers.pop(note, None)
                if timer:
                    timer.cancel()
            # Grabar liberación de tecla para mantener duración exacta de notas
            is_modifier_key = (base_c is not None and note in [base_c + 2, base_c + 3])
            if not is_modifier_key and self.looper.state in ["RECORDING", "OVERDUBBING"]:
                self.looper.record_event(0, note, 0, False)
        elif channel == 9:
            pad_num = (note - 36) % 8 if note < 44 else (note - 44) % 8
            # Si se suelta un pad mientras D1 del extremo izquierdo está sostenido (o estaba activo el looper):
            d_held = (base_c is not None and (base_c + 2) in self.held_keyboard_notes)
            if self.held_keyboard_notes and d_held:
                self.trigger_looper_pad_release(pad_num)
            elif pad_num in self.looper_pad_press_times or pad_num in self.looper_pad_hold_timers:
                self.trigger_looper_pad_release(pad_num)

            fluid.send(f"noteoff 9 {note}")
            if self.looper.state in ["RECORDING", "OVERDUBBING"]:
                self.looper.record_event(9, note, 0, False)

    def handle_control_change(self, cc: int, value: int, channel: int = 0):
        # ======================================================================
        # 1. PERILLAS GIRATORIAS (KNOBS): CC 70..77 y CC 1..8
        # ======================================================================
        is_knob = (70 <= cc <= 77) or (channel == 0 and (1 <= cc <= 8))
        if is_knob:
            if 70 <= cc <= 77:
                knob_idx = cc - 70
            else:
                knob_idx = cc - 1

            # ======================================================================
            # 8 PERILLAS DEDICADAS: FILA SUPERIOR = BATERÍA & BEAT | FILA INFERIOR = TECLADO
            # ======================================================================
            # --- FILA SUPERIOR: BATERÍA & BEAT LOOPER ---
            if knob_idx == 0:    # K1: Drum Reverb Splash (Reverb en Caja y Platos)
                fluid.send(f"cc 9 91 {value}")
                if value > 0:
                    fluid.send("rev_setlevel 0.85")
                print(f"[KNOB 1 - BATERÍA] Reverb Splash (Caja/Platos): {value}/127", flush=True)

            elif knob_idx == 1:  # K2: Drum Pitch / Afinación de Batería (+/- 12 semitonos)
                # 0 = Pitch grave 808 sub, 8192 = normal, 16383 = Pitch agudo trap/jungle
                pb_val = int((value / 127.0) * 16383)
                fluid.send("pitch_bend_range 9 12")
                fluid.send(f"pitch_bend 9 {pb_val}")
                semis = int(((value - 64) / 64.0) * 12)
                print(f"[KNOB 2 - BATERÍA] Afinación/Pitch: {semis:+d} semitonos", flush=True)

            elif knob_idx == 2:  # K3: Beat Looper & Metronome Tempo (BPM)
                # Rango de 30 BPM a 210 BPM
                bpm = int(30 + (value / 127.0) * 180)
                self.looper.set_bpm(bpm)
                print(f"[KNOB 3 - TEMPO LOOPER] BPM: {bpm} (Rango 30-210 BPM)", flush=True)

            elif knob_idx == 3:  # K4: Drum & Looper Volume Balance (Volumen Mezcla Batería / Looper)
                self.drum_knob_val = value
                # El volumen máximo de K4 queda estrictamente acotado por el estado actual de Knob 8 (Master)
                effective_vol = int((value / 127.0) * self.master_knob_val)
                self.current_drum_volume = effective_vol
                # Paridad total de volumen: Canal 10 (batería) y Canal 1 (teclado / looper)
                fluid.send(f"cc 9 7 {effective_vol}\ncc 0 7 {effective_vol}")
                print(f"[KNOB 4 - BATERÍA/LOOP] Mezcla Batería/Loop: {int((value/127)*100)}% (Tope Master K8: {self.master_knob_val} -> CC 7: {effective_vol})", flush=True)

            # --- FILA INFERIOR: TECLADO & MASTER (KEYS & OUTPUT) ---
            elif knob_idx == 4:  # K5: Keyboard Reverb Echo (Reverb en Teclado)
                rev_lvl = (value / 127.0) * 0.95
                room = 0.2 + (value / 127.0) * 0.95
                fluid.send(f"rev_setlevel {rev_lvl:.2f}")
                fluid.send(f"rev_setroomsize {room:.2f}")
                fluid.send(f"cc 0 91 {value}")
                print(f"[KNOB 5 - TECLADO] Reverb Eco Catedral: {int(rev_lvl*100)}% (Room {room:.2f})", flush=True)

            elif knob_idx == 5:  # K6: Keyboard Chorus & Lush (Chorus en Teclado)
                cho_lvl = (value / 127.0) * 1.0
                cho_dep = (value / 127.0) * 18.0
                fluid.send(f"cho_set_level {cho_lvl:.2f}")
                fluid.send(f"cho_set_depth {cho_dep:.2f}")
                fluid.send(f"cc 0 93 {value}")
                print(f"[KNOB 6 - TECLADO] Chorus Grosor & Lush: {int(cho_lvl*100)}%", flush=True)

            elif knob_idx == 6:  # K7: Dual Mode - Sustain Decay (when Sustain ON) / Rotary Speed (when Sustain OFF)
                norm = value / 127.0
                if self.sustain_active:
                    continuous_progs = {16, 19, 38, 39, 48, 50, 56, 65, 80, 81, 88}
                    curr_prog = MELODIC_INSTRUMENTS[self.current_melodic_idx][0]
                    is_continuous = (curr_prog in continuous_progs)

                    if is_continuous:
                        # Órganos y pads continuos: 1.0s a 35.0s
                        decay_sec = 1.0 + (norm ** 2.0) * 34.0
                        self.sustain_decay_seconds = round(decay_sec, 1)
                        print(f"[KNOB 7 - SUSTAIN ÓRGANO/PAD] Caída: {self.sustain_decay_seconds}s (Rango 1s - 35s)", flush=True)
                    else:
                        # Pianos, guitarras y percusión tonal: 1.0s a 60.0s (cola natural de cuerda)
                        decay_sec = 1.0 + (norm ** 2.2) * 59.0
                        self.sustain_decay_seconds = round(decay_sec, 1)
                        print(f"[KNOB 7 - SUSTAIN PIANO/KEYS] Caída: {self.sustain_decay_seconds}s (Rango 1s - 60s)", flush=True)
                else:
                    # FluidSynth cho_set_speed rango estricto: [0.10 a 5.00 Hz]
                    speed_hz = 0.2 + (norm ** 1.3) * 4.8
                    fluid.send(f"cho_set_speed {speed_hz:.2f}")
                    if value > 0:
                        # Asegurar profundidad y nivel audibles de giro Rotary aunque K6 esté bajo
                        fluid.send(f"cho_set_depth {8.0 + norm * 12.0:.1f}")
                        fluid.send(f"cho_set_level {0.4 + norm * 0.55:.2f}")
                        fluid.send(f"cc 0 93 {max(80, value)}")
                        fluid.send(f"cc 0 1 {int(norm * 90)}")
                    else:
                        fluid.send("cc 0 93 0")
                        fluid.send("cc 0 1 0")
                    print(f"[KNOB 7 - ROTARY VIBRATO] Velocidad Leslie: {speed_hz:.1f} Hz | Modulación: {int(norm*100)}%", flush=True)

            elif knob_idx == 7:  # K8: Master Volume (Volumen General)
                self.master_knob_val = value
                # Calibración real-time de FluidSynth setting synth.gain (0.00 a 2.50):
                # Afecta a TODOS los canales de forma global (teclado, pads, looper, metrónomo y chimes)
                norm = value / 127.0
                gain = (norm ** 1.25) * 2.50
                fluid.send(f"set synth.gain {gain:.3f}")

                # Actualizar dinámicamente el tope de volumen en los canales para respetar el límite de K8 sobre K4
                effective_vol = int((self.drum_knob_val / 127.0) * self.master_knob_val)
                self.current_drum_volume = effective_vol
                fluid.send(f"cc 9 7 {effective_vol}\ncc 0 7 {effective_vol}")

                print(f"[KNOB 8 - MASTER] Volumen General: {int(norm * 100)}% (synth.gain {gain:.2f} | Tope K4: {effective_vol})", flush=True)

            return

        # ======================================================================
        # 2. PADS EN MODO CC:
        # Banco A: CC 24..31 (Predeterminado Akai MPK Mini MK3) o CC 16..23 / CC 20..27
        # Banco B: CC 32..39
        # ======================================================================
        is_pad_bank_b = (32 <= cc <= 39) or (28 <= cc <= 35 and channel != 9)
        is_pad_bank_a = (24 <= cc <= 31) or (16 <= cc <= 23) or (20 <= cc <= 27)

        # PADS BANCO A (LIVE FX TECLADO)
        if is_pad_bank_a:
            self.pad_bank = "A"
            if 24 <= cc <= 31:
                pad_idx = cc - 24
            elif 16 <= cc <= 23:
                pad_idx = cc - 16
            else:
                pad_idx = cc - 20
            now = time.time()
            if pad_idx == 0:    # Pad 1: Sustain Pedal Toggle (Damper CC 64)
                if value > 0:
                    self.last_sustain_press = now
                    self.sustain_active = not self.sustain_active
                    if self.sustain_active:
                        fluid.send("cc 0 64 127")
                        status = "ACTIVADO (Notas sostenidas libres)"
                    else:
                        for t in self.active_note_timers.values():
                            t.cancel()
                        self.active_note_timers.clear()
                        fluid.send("cc 0 64 0\ncc 0 123 0")
                        status = "DESACTIVADO (Silenciadas notas sostenidas)"
                    print(f"\n[PAD CC A-1] SUSTAIN PEDAL -> {status}", flush=True)
                else:
                    if (now - self.last_sustain_press) > 0.4:
                        self.sustain_active = False
                        for t in self.active_note_timers.values():
                            t.cancel()
                        self.active_note_timers.clear()
                        fluid.send("cc 0 64 0\ncc 0 123 0")
                        print("\n[PAD CC A-1] SUSTAIN PEDAL -> DESACTIVADO (Hardware Toggle)", flush=True)
            elif pad_idx == 1:  # Pad 2: Portamento / Glide Toggle (CC 65 + CC 5)
                if value > 0:
                    self.last_portamento_press = now
                    self.portamento_active = not self.portamento_active
                    if self.portamento_active:
                        fluid.send("setportamentomode 0 1\ncc 0 5 75\ncc 0 65 127")
                    else:
                        fluid.send("setportamentomode 0 0\ncc 0 65 0")
                    status = "ACTIVADO (Glide activo)" if self.portamento_active else "DESACTIVADO"
                    print(f"\n[PAD CC A-2] Portamento/Glide -> {status}", flush=True)
                else:
                    if (now - self.last_portamento_press) > 0.4:
                        self.portamento_active = False
                        fluid.send("setportamentomode 0 0\ncc 0 65 0")
                        print("\n[PAD CC A-2] Portamento/Glide -> DESACTIVADO (Hardware Toggle)", flush=True)
            elif pad_idx == 2:  # Pad 3: Filter Cutoff Boost
                fluid.send(f"cc 0 74 {127 if value > 0 else 85}")
                print(f"[PAD CC A-3] Filter Cutoff Boost: {'100% (Brillo Máximo)' if value > 0 else 'Normal'}", flush=True)
            elif pad_idx == 3:  # Pad 4: Reverb Kill / Mute
                fluid.send("reverb off" if value > 0 else "reverb on")
                print(f"[PAD CC A-4] Reverb: {'MUTED (Seco)' if value > 0 else 'ON'}", flush=True)
            elif pad_idx == 4:  # Pad 5: Chorus Splash
                if value > 0:
                    fluid.send("chorus on\ncho_set_level 1.0\ncho_set_depth 18.0\ncho_set_speed 2.5\ncc 0 93 127")
                    print("[PAD CC A-5] Chorus Boost: MÁXIMO (DSP Activo)", flush=True)
                else:
                    fluid.send("cho_set_level 0.45\ncho_set_depth 6.0\ncho_set_speed 0.6\ncc 0 93 25")
                    print("[PAD CC A-5] Chorus Boost: Normal", flush=True)
            elif pad_idx == 5:  # Pad 6: Instrumento Anterior (Teclado)
                if value > 0:
                    fluid.send("cc 0 123 0")
                    oct_shift = max(-3, min(3, (self.lowest_base_c - 48) // 12)) if self.lowest_base_c else 0
                    active_lib = OCTAVE_INSTRUMENT_LIBRARIES.get(oct_shift, OCTAVE_INSTRUMENT_LIBRARIES[0])
                    self.current_melodic_idx = (self.current_melodic_idx - 1) % len(active_lib)
                    prog_num, name = active_lib[self.current_melodic_idx]
                    fluid.send(f"prog 0 {prog_num}")
                    print(f"\n[PAD CC A-6] Instrumento Anterior (OCT {oct_shift:+d}) -> ({self.current_melodic_idx + 1}/{len(active_lib)}): {name} (Prog {prog_num})", flush=True)
                    play_preview(chan=0, note=72, vel=110, duration=0.35)
            elif pad_idx == 6:  # Pad 7: Instrumento Siguiente (Teclado)
                if value > 0:
                    fluid.send("cc 0 123 0")
                    oct_shift = max(-3, min(3, (self.lowest_base_c - 48) // 12)) if self.lowest_base_c else 0
                    active_lib = OCTAVE_INSTRUMENT_LIBRARIES.get(oct_shift, OCTAVE_INSTRUMENT_LIBRARIES[0])
                    self.current_melodic_idx = (self.current_melodic_idx + 1) % len(active_lib)
                    prog_num, name = active_lib[self.current_melodic_idx]
                    fluid.send(f"prog 0 {prog_num}")
                    print(f"\n[PAD CC A-7] Instrumento Siguiente (OCT {oct_shift:+d}) -> ({self.current_melodic_idx + 1}/{len(active_lib)}): {name} (Prog {prog_num})", flush=True)
                    play_preview(chan=0, note=72, vel=110, duration=0.35)
            elif pad_idx == 7:  # Pad 8: Pánico / Hard-Cut (Silencia todo sonido inmediatamente)
                if value > 0:
                    # 1. Silenciar temporizadores de decaimiento activos
                    for t in self.active_note_timers.values():
                        t.cancel()
                    self.active_note_timers.clear()

                    # 2. Detener looper y metrónomo
                    self.looper.stop_all()

                    # 3. Corte total en FluidSynth: silenciar notas y todos los sonidos en todos los canales
                    kill_cmds = []
                    for c in range(16):
                        kill_cmds.append(f"cc {c} 120 0\ncc {c} 123 0\ncc {c} 91 0")
                    fluid.send("\n".join(kill_cmds))

                    # 4. Mantener el estado de sustain (Pad 1): si estaba activo, restablecer CC 64 para notas siguientes
                    if self.sustain_active:
                        fluid.send("cc 0 64 127")
                    else:
                        fluid.send("cc 0 64 0")

                    # 5. Enviar noteoff explícito a cualquier tecla física que siga sostenida
                    if self.held_keyboard_notes:
                        offs = "\n".join(f"noteoff 0 {k}" for k in list(self.held_keyboard_notes.keys()))
                        fluid.send(offs)

                    # 6. Drenar la cola de reverb residual y restaurar nivel predeterminado tras corte
                    def _restore_reverb_dsp():
                        time.sleep(0.04)
                        fluid.send("cc 0 91 40\ncc 9 91 60\ncc 15 91 80")
                    threading.Thread(target=_restore_reverb_dsp, daemon=True).start()

                    print(f"\n[PAD CC A-8] ¡PÁNICO TOTAL! Silenciadas todas las notas, drenada la reverb y looper detenido (Sustain activo: {self.sustain_active}).", flush=True)

        # PADS BANCO B (LIVE LOOPER & GROOVE ENGINE)
        elif is_pad_bank_b:
            self.pad_bank = "B"
            pad_idx = (cc - 32) if (32 <= cc <= 39) else (cc - 28)
            if value > 0:
                self.trigger_looper_pad(pad_idx)

        # ======================================================================
        # 3. PEDAL DE SUSTAIN FÍSICO TRASERO (JACK 1/4" DEL AKAI): CC 64
        # ======================================================================
        elif cc == 64:
            self.sustain_active = (value > 63)
            fluid.send(f"cc 0 64 {value}")
            print(f"[PEDAL SUSTAIN TRASERO CC 64] -> {'ACTIVADO' if value > 63 else 'DESACTIVADO'}", flush=True)

    def run(self):
        print("==================================================================")
        print(" Akai MPK Mini - Live Beat Looper & Standalone Synth Workstation  ")
        print("==================================================================")
        print(" • MANTÉN C1 + TECLAS (1-24)  -> 24 Sonidos de Teclado (Pianos, Sintes)")
        print(" • MANTÉN C#1 + TECLAS (1-24) -> 24 Kits de Batería (808, 909, Rock, Jazz)")
        print(" • MANTÉN D1 + PADS (1-4)     -> LIVE LOOPER (P1:Rec/Overdub, P2:Pausa, P3:Clear, P4:Metro)")
        print(" • MANTÉN D1 + PADS (5-8)     -> STOP ALL")
        print(" • MANTÉN D#1 + PADS (1-8)    -> 8 RITMOS PREGRABADOS (Lo-Fi, Trap, House, Afrobeat...)")
        print(" • C1 + C#1 (Ambas juntas)    -> Full Level Teclado ON/OFF (100% vs dinámico)")
        print(" • C1 + C3 (3 segundos)       -> Apagado Seguro de la Raspberry Pi")
        print(" • KNOB 1: Drum Reverb Splash | KNOB 2: Drum Pitch Tuning (±12 st)")
        print(" • KNOB 3: Looper Tempo (30-210 BPM) | KNOB 4: Drum & Loop Volume Mix")
        print(" • KNOB 5: Keys Reverb Echo   | KNOB 6: Keys Chorus Lush")
        print(" • KNOB 7: Keys Brillo/Filter | KNOB 8: Master Volume")
        print("==================================================================")

        while self.running:
            port_name = self.find_mpk_port()
            if not port_name:
                time.sleep(2.0)
                continue

            try:
                # Asegurar enlace ALSA Sequencer directo con FluidSynth al conectar
                subprocess.run("aconnect 'MPK mini':0 'FLUID Synth':0 2>/dev/null || true", shell=True)
                fluid.send("set synth.gain 1.25\ncc 0 7 127\ncc 9 7 100\ncc 15 7 55\n")
                print(f"[+] Conectado a {port_name}. Listo para tocar (Volumen inicial synth.gain 1.25, CC 7: 127).", flush=True)

                if not self.startup_sound_played:
                    self.startup_sound_played = True
                    self.play_startup_sound()

                with mido.open_input(port_name) as inport:
                    last_check = time.time()
                    while self.running:
                        msg = inport.poll()
                        if msg:
                            if msg.type == "note_on":
                                if msg.velocity > 0:
                                    self.handle_note_on(msg.note, msg.velocity, msg.channel)
                                else:
                                    self.handle_note_off(msg.note, msg.channel)
                            elif msg.type == "note_off":
                                self.handle_note_off(msg.note, msg.channel)
                            elif msg.type == "control_change":
                                self.handle_control_change(msg.control, msg.value, msg.channel)
                            elif msg.type == "program_change":
                                # Conmutar mute de sonidos de función al presionar PROG CHANGE / PROG SELECT
                                self.mute_function_sounds = not self.mute_function_sounds
                                st = "MUTED (Silencio)" if self.mute_function_sounds else "ACTIVOS (Chimes on)"
                                print(f"\n[PROG CHANGE] Sonidos de función auxiliares: {st} (Canal {msg.channel + 1} Prog {msg.program})", flush=True)
                            continue

                        now = time.time()
                        if (now - last_check) > 1.0:
                            last_check = now
                            try:
                                ports = mido.get_input_names()
                                if not any("mpk" in p.lower() or "akai" in p.lower() for p in ports):
                                    print("[-] Desconexión física detectada (USB desconectado). Reiniciando escucha...", flush=True)
                                    break
                            except Exception:
                                break

                        time.sleep(0.002)
            except Exception as e:
                print(f"[-] Teclado desconectado: {e}. Esperando reconexión automática...", flush=True)
                self.held_keyboard_notes.clear()
                self.sustain_active = False
                time.sleep(1.5)

if __name__ == "__main__":
    controller = AdvancedAkaiController()
    controller.run()
