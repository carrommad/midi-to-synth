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
    # OCT -3 (Pad 1): Deep Basses & Low End (24 distinct GM instruments)
    -3: [
        (32, "Acoustic Upright Bass"),
        (33, "Fingered Electric Bass"),
        (34, "Picked Electric Bass"),
        (35, "Fretless Bass"),
        (36, "Slap Bass 1 (Funk Pop)"),
        (37, "Slap Bass 2 (Heavy Thumb)"),
        (38, "Synth Bass 1 (Classic Sub)"),
        (39, "Synth Bass 2 (Acid 303 Resonant)"),
        (43, "Contrabass Strings"),
        (58, "Tuba Deep Brass"),
        (70, "Bassoon Deep Reed"),
        (67, "Baritone Saxophone"),
        (19, "Church Pipe Organ Bass"),
        (16, "Drawbar 16ft Sub Organ"),
        (117, "Melodic Deep Tom"),
        (118, "Synth Percussion Drum"),
        (116, "Taiko Low Drum"),
        (47, "Timpani Orchestral Drum"),
        (60, "French Horn Low"),
        (57, "Trombone Bass"),
        (23, "Tango Bandoneon Low"),
        (20, "Reed Organ Low"),
        (28, "Muted Clean Bass Pluck"),
        (87, "Bass + Lead Synth"),
        (42, "Cello Low Bass")
    ],
    # OCT -2 (Pad 2): World & Ethnic Instruments (24 distinct GM instruments)
    -2: [
        (104, "Sitar (Classic Indian)"),
        (105, "Banjo (5-String Americana)"),
        (106, "Shamisen (Japanese Plucked)"),
        (107, "Koto (Japanese Traditional)"),
        (108, "Kalimba (Thumb Piano)"),
        (109, "Bagpipe (Scottish Highlands)"),
        (110, "Fiddle (Irish Celtic)"),
        (111, "Shanai (Indian Oboe)"),
        (112, "Tinkle Bell"),
        (113, "Agogo Percussion"),
        (114, "Steel Drums (Caribbean)"),
        (115, "Woodblock Percussion"),
        (116, "Taiko Drum"),
        (75,  "Pan Flute (Andean Zampona)"),
        (76,  "Blown Bottle Flute"),
        (77,  "Shakuhachi (Bamboo Flute)"),
        (78,  "Whistle Folk"),
        (79,  "Ocarina Legend"),
        (15,  "Santur / Hammered Dulcimer"),
        (12,  "Marimba (Wood Mallet)"),
        (14,  "Tubular Bells Carillon"),
        (21,  "Accordion (French Musette)"),
        (22,  "Harmonica (Blues Harp)"),
        (23,  "Bandoneon (Tango Expressive)"),
        (13,  "Xylophone Folk Bright")
    ],
    # OCT -1 (Pad 3): Synths, Leads & Warm Pads (24 distinct GM instruments)
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
        (55, "Orchestra Hit / Stabs"),
        (98, "Crystal Bells Synth"),
        (100, "Brightness Synth Shimmer"),
        (99, "Space Atmosphere Dark Synth")
    ],
    # Neutral OCT (0) (Pad 4): Pianos, Organs & Keyboards (24 distinct GM instruments)
    0: [
        (0,  "Yamaha Grand Piano"),
        (1,  "Bright Acoustic Piano"),
        (2,  "Electric Piano (Rhodes MK1)"),
        (3,  "Honky-Tonk Bar Piano"),
        (4,  "Electric Piano 2 (FM DX7)"),
        (5,  "Electric Piano (Wurlitzer Warm)"),
        (6,  "Harpsichord Baroque"),
        (7,  "Clavinet (Funk Groove)"),
        (8,  "Celesta (Cristal Bell)"),
        (9,  "Glockenspiel Orchestral"),
        (10, "Music Box Chiming"),
        (11, "Vibraphone (Jazz Vibes)"),
        (12, "Marimba Resonant"),
        (13, "Xylophone Bright Mallet"),
        (14, "Tubular Bells Chimes"),
        (16, "Drawbar Organ (Hammond B3)"),
        (17, "Percussive Organ (Rock Jazz)"),
        (18, "Rock Rotary Organ"),
        (19, "Church Pipe Organ Majestic"),
        (20, "Reed Organ Warm Harmonium"),
        (21, "Accordion (French Musette)"),
        (22, "Harmonica (Blues Harp)"),
        (23, "Tango Bandoneon"),
        (46, "Orchestral Harp Plucked"),
        (15, "Dulcimer / Zither Folk")
    ],
    # OCT +1 (Pad 5): Guitars & Plucked Strings (24 distinct GM instruments)
    1: [
        (24, "Nylon Spanish Guitar (Flamenco)"),
        (25, "Steel String Acoustic Guitar"),
        (26, "Jazz Electric Archtop Guitar"),
        (27, "Clean Electric Guitar (Strat)"),
        (28, "Muted Electric Guitar (Funk Chank)"),
        (29, "Overdrive Rock Guitar"),
        (30, "Distortion Lead Guitar"),
        (31, "Guitar Harmonics & Feedback"),
        (45, "Pizzicato Strings Plucked"),
        (46, "Orchestral Concert Harp"),
        (104, "Indian Sitar Plucked"),
        (105, "5-String Banjo"),
        (106, "Japanese Shamisen"),
        (107, "Japanese Koto Pluck"),
        (108, "Kalimba Thumb Pluck"),
        (15,  "Hammered Dulcimer / Santur"),
        (33,  "Fingered Bass Pluck"),
        (34,  'Picked Bass Pluck'),
        (36,  "Slap Bass Funk"),
        (110, "Fiddle Celtic Pluck"),
        (40,  "Solo Violin Soloist"),
        (42,  "Solo Cello Resonant"),
        (114, "Steel Drums Calypso"),
        (115, "Woodblock Wooden Pluck"),
        (109, "Highland Bagpipe Pluck")
    ],
    # OCT +2 (Pad 6): Orchestral Strings, Brass & Reeds (24 distinct GM instruments)
    2: [
        (40, "Solo Violin"),
        (41, "Solo Viola"),
        (42, "Solo Cello"),
        (43, "Contrabass Strings"),
        (44, "Tremolo Strings Ensemble"),
        (45, "Pizzicato Strings"),
        (46, "Orchestral Harp"),
        (47, "Timpani Orchestral"),
        (48, "Full String Ensemble 1"),
        (49, "Full String Ensemble 2 (Slow)"),
        (56, "Trumpet (Fanfare & Classical)"),
        (57, "Trombone Tenor"),
        (58, "Tuba Deep Brass"),
        (59, "Muted Trumpet (Miles Jazz)"),
        (60, "French Horn Section"),
        (61, "Brass Section (Orchestral)"),
        (64, "Soprano Saxophone"),
        (65, "Alto Saxophone (Jazz Solo)"),
        (66, "Tenor Saxophone Warm"),
        (67, "Baritone Saxophone Deep"),
        (68, "Oboe Classical"),
        (69, "English Horn Expressive"),
        (70, "Bassoon Orchestral"),
        (71, "Clarinet Warm Woodwind"),
        (72, "Piccolo Orchestral Flute")
    ],
    # OCT +3 (Pad 7): Retro 8-Bit Chiptune & Sound FX (24 distinct GM instruments)
    3: [
        (80,  "NES 25% Pulse Wave Lead"),
        (81,  "Game Boy Saw Arp Lead"),
        (82,  "Chiptune Calliope Lead"),
        (83,  "8-Bit Chiff Synth"),
        (84,  "Charang Synth Lead"),
        (85,  "Voice Synth Solo"),
        (86,  "Fifths Saw Lead"),
        (118, "8-Bit Synth Tom Percussion"),
        (119, "Reverse Cymbal Whoosh FX"),
        (120, "Guitar Fret Noise / Scratch"),
        (121, "Breath Noise FX"),
        (122, "Seashore Ocean Wave FX"),
        (123, "Bird Tweet Ambient FX"),
        (124, "Telephone Ring Retro"),
        (125, "Helicopter Rotor Blade FX"),
        (126, "Applause & Cheering Crowd"),
        (127, "Gunshot / Impact Hit FX"),
        (96,  "FX 1 (Sci-Fi Raindrop)"),
        (97,  "FX 2 (Soundtrack Ambient)"),
        (98,  "FX 3 (Crystal Chimes)"),
        (99,  "FX 4 (Atmosphere Space Drone)"),
        (100, "FX 5 (Brightness Bell Shimmer)"),
        (101, "FX 6 (Goblins Alien Creature)"),
        (102, "FX 7 (Echo Drops Deep Cave)"),
        (103, "FX 8 (Star Theme Sci-Fi)")
    ],
    # SET 8 (Pad 8): Ambient Drones, Textures & Soundscapes (24 distinct GM instruments)
    4: [
        (88,  "Deep Space Drone Pad (Warm)"),
        (89,  "Polysynth Cosmic Atmosphere"),
        (90,  "Choir Ethereal Pad"),
        (91,  "Bowed Glass Shimmer Pad"),
        (92,  "Metallic Texture Pad"),
        (93,  "Halo Angelic Pad"),
        (94,  "Sweep Resonant Filter Pad"),
        (95,  "Space Ice Rain Ambient Pad"),
        (48,  "Slow Majestic Strings Pad"),
        (49,  "Warm Chamber Strings"),
        (50,  "Dark Synth Strings"),
        (51,  "Slow Synth Strings Swell"),
        (52,  "Ahh Choir Vocal Drone"),
        (53,  "Ohh Voices Mystic Choir"),
        (54,  "Synth Voice Ethereal Aaah"),
        (96,  "Sci-Fi Raindrop Texture"),
        (97,  "Soundtrack Ambient Atmosphere"),
        (98,  "Crystal Chimes Resonator"),
        (99,  "Space Atmosphere Dark Drone"),
        (100, "Brightness Bell Ambient"),
        (101, "Alien Goblins Texture"),
        (102, "Echo Drops Cavern FX"),
        (103, "Star Theme Sci-Fi Lead"),
        (75,  "Pan Flute Ambient Breath"),
        (55,  "Orchestral Hit / Stabs Ambient")
    ]
}

# 8 Library Keys in Order for Pad 1..8 selection
LIBRARY_ORDER = [-3, -2, -1, 0, 1, 2, 3, 4]
LIBRARY_NAMES = [
    "1. Deep Basses & 808s",
    "2. World & Ethnic Instruments",
    "3. Synths, Leads & Warm Pads",
    "4. Pianos, Organs & Keys",
    "5. Guitars & Plucked Strings",
    "6. Orchestral, Brass & Winds",
    "7. Retro 8-Bit Chiptune & FX",
    "8. Ambient Drones & Soundscapes"
]

# Compatibility reference fallback
MELODIC_INSTRUMENTS = OCTAVE_INSTRUMENT_LIBRARIES[0]

# 16 Drum Kits (Mapped to Pads 1..8 while holding [D] C#2 modifier: Bank A 1..8, Bank B 9..16)
# Full Symmetric Architecture: Bank A (Acoustic/Classic) <-> Bank B (World/Exotic Counterpart)
# Pad 1: Acoustic Rock & Pop (Standard vs Room Rock)
# Pad 2: Electronic Dance (909 Techno vs TR-808 Trap)
# Pad 3: Jazz & Sticks (Jazz Drum vs Brush Escobillas)
# Pad 4: Orchestral & Cinematic (Orchestra Timpani vs Cinematic Taiko & Asian Drums)
# Pad 5: African Percussion (Afro-Tribal Djembe/Dunun vs Afro-Cuban Batá/Shakers)
# Pad 6: Asian & Middle East (East Asian Percussion vs Middle Eastern Derbake/Darbuka)
# Pad 7: Latin & Tropical (Latin Salsa/Congas vs Carnaval Samba & Whistles)
# Pad 8: Flamenco (Flamenco Cajón & Palmas 1 vs Flamenco Castañuelas & Taconeo 2)
DRUM_KITS = [
    # Bank A: 8 Core & Classic Kits (Pads 1..8)
    (0,  "Standard Acoustic Drum Kit"),             # Pad 1 (A1)
    (24, "Electronic 909 Dance Kit"),               # Pad 2 (A2)
    (32, "Jazz Drum Kit"),                          # Pad 3 (A3)
    (48, "Orchestra Percussion & Timpani"),         # Pad 4 (A4)
    (0,  "Afro-Tribal Djembe & Dunun Kit"),         # Pad 5 (A5: Dedicated acoustic mapping)
    (0,  "East Asian Taiko & Bells Kit"),           # Pad 6 (A6: Dedicated acoustic mapping)
    (0,  "Latin & Salsa Percussion Kit"),           # Pad 7 (A7: Congas, Bongós, Timbales, Cowbell)
    (0,  "Flamenco Cajón & Palmas Kit 1"),          # Pad 8 (A8: Cajón grave/agudo, Palmas)
    # Bank B: 8 Exotic & World Counterparts (Pads 1..8 -> Kits 9..16)
    (8,  "Room Rock & Gated Drum Kit"),             # Pad 9  (B1)
    (25, "Roland TR-808 Classic Trap Kit"),         # Pad 10 (B2)
    (40, "Brush Drum Kit (Escobillas)"),            # Pad 11 (B3)
    (48, "Cinematic Taiko & Asian Gongs"),          # Pad 12 (B4: Dedicated acoustic mapping)
    (0,  "Afro-Cuban Batá & Shakers Kit"),          # Pad 13 (B5: Dedicated acoustic mapping)
    (0,  "Middle Eastern Derbake & Riq Kit"),       # Pad 14 (B6: Dedicated acoustic mapping)
    (0,  "Carnaval & Samba Percussion Kit"),        # Pad 15 (B7: Apito Whistles, Cuíca, Agogô, Surdo)
    (0,  "Flamenco Castañuelas & Fusión Kit 2")     # Pad 16 (B8: Castañuelas, Taconeo, Bastón)
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
        self.metronome_active: bool = False  # Silencio en reproducción por defecto (solo suena al grabar en ARMED/REC)
        # 8 Pistas independientes (Layers 1..8): cada pista es una lista de (phase_sec, channel, note, velocity, is_note_on, orig_prog)
        self.tracks: list = [[] for _ in range(8)]
        self.track_muted: list = [False for _ in range(8)]
        self.track_prog: list = [None for _ in range(8)]  # Voice lock per track
        self.track_duration: list = [0.0 for _ in range(8)]  # Duración individual por pista (loops independientes)
        self.base_track_duration: list = [0.0 for _ in range(8)]
        self.track_rec_start: float = 0.0
        self.revoice_mode: bool = False  # False: Multi-Instrument Lock per track (default) | True: Re-voice all melodic tracks to current
        self.selected_loop_bars: Optional[int] = None  # Compases elegidos para la toma actual (1..8) o None (Libre)
        self.persistent_fixed_bars: Optional[int] = None  # Compases fijados permanentemente (1..8) o None (Libre)
        self.bar_selection_ready: bool = False  # True tras pulsar Pad 1 mientras se mantiene [L]
        self.overdub_pending: bool = False
        self.overdub_countdown_beats: int = 0
        self.overdub_start_bar: int = 0
        self.current_playback_beat: int = 0
        self.current_track: int = 0
        self.first_note_time: Optional[float] = None
        self.loop_duration: float = 0.0
        self.rec_start_time: float = 0.0
        self.cycle_start_time: float = 0.0
        self.finish_pending: bool = False
        self.stop_event = threading.Event()
        self.preset_stop_event = threading.Event()
        self.play_thread: Optional[threading.Thread] = None
        self.preset_thread: Optional[threading.Thread] = None
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

    def toggle_revoice_mode(self):
        """Conmuta el modo de re-instrumentación de las pistas grabadas:
        - Modo Bloqueo (False, por defecto): Cada pista conserva el instrumento con el que se grabó.
        - Modo Re-Voice Última Pista (True): La ÚLTIMA pista de teclas grabada adopta en vivo el instrumento activo del teclado.
        """
        self.revoice_mode = not self.revoice_mode
        st = "RE-VOICE ÚLTIMA PISTA (La última pista de teclas sigue el sonido activo)" if self.revoice_mode else "MULTI-INSTRUMENT LOCK (Todas las pistas bloqueadas a su instrumento original)"
        print(f"\n[LOOPER 🔀 RE-VOICE MODE] -> {st}", flush=True)
        self._play_chime("play" if self.revoice_mode else "pause")

    def set_bpm(self, new_bpm: int):
        self.bpm = max(30, min(210, new_bpm))
        if self.base_bpm > 0:
            scale = self.base_bpm / float(self.bpm)
            if self.base_loop_duration > 0:
                self.loop_duration = self.base_loop_duration * scale
            for i in range(8):
                if self.base_track_duration[i] > 0:
                    self.track_duration[i] = self.base_track_duration[i] * scale
        if self.state in ["PLAYING", "OVERDUBBING"]:
            print(f"[LOOPER] BPM ajustado en vivo: {self.bpm} BPM (Duración Pista 1: {self.track_duration[0]:.2f}s)", flush=True)

    def clear_persistent_fixed_bars(self):
        """Cancela cualquier fijación de compases y devuelve el looper al modo LIBRE."""
        self.persistent_fixed_bars = None
        self.selected_loop_bars = None
        self.bar_selection_ready = False
        print("\n[LOOPER ⏱ COMPASES] -> RESET A MODO LIBRE (Sin límite fijo de compases)", flush=True)
        # Chime descendente sutil de vuelta a modo libre
        self._play_chime("free_reset")

    def select_bar_count(self, bars: int, hold_persistent: bool = False, play_clicks: bool = True):
        """Asigna los compases elegidos (1..8) para el bucle actual o permanentemente si se mantiene pulsado."""
        self.bar_selection_ready = False
        self.selected_loop_bars = bars
        if hold_persistent:
            self.persistent_fixed_bars = bars
            print(f"\n[LOOPER ⏱ COMPASES] -> FIJADO PERMANENTE A {bars} COMPÁS(ES) PARA TODOS LOS BUCLES", flush=True)
            if play_clicks:
                self._play_bar_clicks(bars, persistent_tone=True)
        else:
            print(f"\n[LOOPER ⏱ COMPASES] -> SELECCIONADOS {bars} COMPÁS(ES) PARA ESTA TOMA", flush=True)
            if play_clicks:
                self._play_bar_clicks(bars, persistent_tone=False)

    def _play_bar_clicks(self, count: int, persistent_tone: bool = False):
        """Emite 'count' clics acústicos de madera y opcionalmente un tono grave si queda bloqueado."""
        def _worker():
            try:
                self.fluid.send("prog 15 115\ncc 15 7 90\n")
                for _ in range(count):
                    self.fluid.send("noteon 15 76 90\n")
                    time.sleep(0.04)
                    self.fluid.send("noteoff 15 76\n")
                    time.sleep(0.06)
                if persistent_tone:
                    time.sleep(0.08)
                    self.fluid.send("prog 15 8\ncc 15 7 85\nnoteon 15 60 75\n")
                    time.sleep(0.35)
                    self.fluid.send("noteoff 15 60\n")
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

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
        3. Cierre Inteligente / Auto-Cierre: Si fixed_4_bars está activo, se fija exactamente a 4 compases.
        4. Overdub con Pre-Roll: Espera al tiempo 1 del Compás 1 garantizando >= 1 compás entero de claqueta.
        """
        if self.state in ["IDLE", "PAUSED"]:
            # ENTRAR EN MODO ARMED (8 pistas limpias)
            with self.lock:
                for i in range(8):
                    self.tracks[i].clear()
                    self.track_muted[i] = False
                    self.track_prog[i] = None
                    self.track_duration[i] = 0.0
                    self.base_track_duration[i] = 0.0
                self.current_track = 0
                self.state = "ARMED"
                self.overdub_pending = False
                self.loop_duration = 0.0
                self.base_loop_duration = 0.0
                self.stop_event.clear()

            # Al pulsar [L] + Pad 1, activar preparación de selección de compás mientras se mantenga [L]
            # SILENCIO TOTAL mientras [L] esté pulsado: no arrancar metrónomo todavía.
            self.selected_loop_bars = self.persistent_fixed_bars
            self.bar_selection_ready = True

            print(f"\n[LOOPER ⏱ ARMED PENDING] Preparando toma a {self.bpm} BPM. Sin soltar [L], puedes elegir o rectificar compases (Pads 1..8). Al soltar [L] comenzará la claqueta...", flush=True)

        elif self.state == "ARMED":
            self.bar_selection_ready = False
            self.stop_all()

        elif self.state == "RECORDING":
            self.bar_selection_ready = False

            # CIERRE MANUAL O FORZADO
            now = time.perf_counter()
            elapsed = max(0.01, now - self.rec_start_time)
            beat_dur = 60.0 / self.bpm
            bar_dur = 4.0 * beat_dur

            raw_bars = elapsed / bar_dur
            target_b = self.selected_loop_bars or self.persistent_fixed_bars
            bars = target_b if target_b is not None else max(1, round(raw_bars))
            self.base_loop_duration = bars * bar_dur
            self.loop_duration = self.base_loop_duration
            self.base_track_duration[0] = self.base_loop_duration
            self.track_duration[0] = self.loop_duration

            # Registrar programa activo para esta pista
            if self.controller:
                self.track_prog[0] = self.controller.get_current_melodic_program()

            step_grid = 60.0 / (self.bpm * 4.0)
            with self.lock:
                clean_events = []
                step_tol = step_grid * 0.5
                for ev in self.tracks[0]:
                    t, ch, n, v, is_on = ev[:5]
                    prg = ev[5] if len(ev) > 5 else self.track_prog[0]
                    if t < self.base_loop_duration:
                        clean_events.append([t, ch, n, v, is_on, prg])
                    elif t <= (self.base_loop_duration + step_tol) and is_on:
                        clean_events.append([0.0, ch, n, v, is_on, prg])

                clean_events.sort(key=lambda x: (x[0], 0 if x[4] else 1))

                min_gate = 0.040  # 40ms
                active_ons = {}
                for ev in clean_events:
                    t, ch, n, v, is_on, prg = ev
                    key = (ch, n)
                    if is_on:
                        active_ons[key] = t
                    else:
                        if key in active_ons:
                            start_t = active_ons.pop(key)
                            if (t - start_t) < min_gate:
                                ev[0] = start_t + min_gate

                clean_events = [tuple(e) for e in clean_events]
                clean_events.sort(key=lambda x: (x[0], 0 if x[4] else 1))
                self.tracks[0] = clean_events
                self.state = "PLAYING"
                self.overdub_pending = False
                self.overdub_countdown_beats = 0

            total_evs = len(self.tracks[0])
            total_beats = bars * 4
            self.metronome_active = False  # Silenciar al 100% el metrónomo en reproducción
            print(f"\n[LOOPER ▶ PLAY] Bucle cerrado limpiamente: {bars} compás(es) ({total_beats} pulsos, {self.loop_duration:.2f}s) con {total_evs} notas grabadas.", flush=True)
            self._start_playback_thread()

        elif self.state == "PLAYING":
            if self.overdub_pending:
                self.overdub_pending = False
                self.overdub_countdown_beats = 0
                self.bar_selection_ready = False
                print(f"\n[LOOPER] Overdub pendiente cancelado.", flush=True)
                self._play_chime("pause")
                return

            # ENTER OVERDUB PENDING (Esperando al Compás 1 con cuenta atrás de 4 clics previos)
            self.overdub_pending = True
            self.overdub_countdown_beats = 4  # 4 pulsos enteros de pre-roll

            # Sin soltar [L], se pueden elegir compases para este overdub
            self.selected_loop_bars = self.persistent_fixed_bars
            self.bar_selection_ready = True

            print(f"\n[LOOPER ⏱ OVERDUB EN ESPERA] Preparando claqueta de 4 clics. Sin soltar [L], puedes elegir compases (Pads 1..8)...", flush=True)
            self._play_chime("armed")

        elif self.state == "OVERDUBBING":
            self.bar_selection_ready = False
            self._finish_overdub()

    def _start_actual_overdub(self):
        """Inicia físicamente la grabación de la capa de overdub justo en el Compás 1."""
        self._push_history()
        next_trk = None
        for idx in range(1, 8):
            if len(self.tracks[idx]) == 0:
                next_trk = idx
                break
        if next_trk is None:
            next_trk = (self.current_track + 1) % 8
            if next_trk == 0:
                next_trk = 1

        self.current_track = next_trk
        self.track_muted[self.current_track] = False
        self.track_duration[self.current_track] = 0.0
        self.base_track_duration[self.current_track] = 0.0
        self.track_rec_start = time.perf_counter()
        self.tracks[self.current_track].clear()
        if self.controller:
            self.track_prog[self.current_track] = self.controller.get_current_melodic_program()
        self.state = "OVERDUBBING"
        self.overdub_pending = False
        print(f"\n[LOOPER 🔴 OVERDUB ACTIVO] ¡Grabando en Pista {self.current_track + 1} de 8 sincronizado al Compás 1!", flush=True)
        self._play_chime("start_rec")

        # Si hay compases definidos (seleccionados u obligatorios), auto-cerrar overdub al completarlos
        target_bars = self.selected_loop_bars or self.persistent_fixed_bars
        if target_bars is not None:
            def _watchdog_overdub_autoclose(start_t: float, trk_num: int, b_count: int):
                beat_dur = 60.0 / self.bpm
                dur = float(b_count) * 4.0 * beat_dur
                time.sleep(dur)
                if self.state == "OVERDUBBING" and self.track_rec_start == start_t and self.current_track == trk_num:
                    print(f"\n[LOOPER ⏱ AUTO-CIERRE OVERDUB] Completados {b_count} compás(es) de Overdub. Uniendo al loop maestro...", flush=True)
                    self._finish_overdub()

            threading.Thread(target=_watchdog_overdub_autoclose, args=[self.track_rec_start, self.current_track, target_bars], daemon=True).start()

    def _finish_overdub(self):
        """Cierra la capa de overdub y pasa a PLAYING con duración cuantizada."""
        now = time.perf_counter()
        elapsed_trk = max(0.01, now - self.track_rec_start)
        beat_dur = 60.0 / self.bpm
        bar_dur = 4.0 * beat_dur
        raw_bars = elapsed_trk / bar_dur
        target_b = self.selected_loop_bars or self.persistent_fixed_bars
        bars = target_b if target_b is not None else max(1, round(raw_bars))
        trk_dur = bars * bar_dur

        with self.lock:
            trk = self.current_track
            self.base_track_duration[trk] = trk_dur
            self.track_duration[trk] = trk_dur
            step_grid = 60.0 / (self.bpm * 4.0)
            step_tol = step_grid * 0.5
            clean_events = []
            for ev in self.tracks[trk]:
                t, ch, n, v, is_on = ev[:5]
                prg = ev[5] if len(ev) > 5 else self.track_prog[trk]
                if t < trk_dur:
                    clean_events.append([t, ch, n, v, is_on, prg])
                elif t <= (trk_dur + step_tol) and is_on:
                    clean_events.append([0.0, ch, n, v, is_on, prg])

            clean_events.sort(key=lambda x: (x[0], 0 if x[4] else 1))

            min_gate = 0.040  # 40ms
            active_ons = {}
            for ev in clean_events:
                t, ch, n, v, is_on, prg = ev
                key = (ch, n)
                if is_on:
                    active_ons[key] = t
                else:
                    if key in active_ons:
                        on_t = active_ons.pop(key)
                        if (t - on_t) < min_gate:
                            ev[0] = min(trk_dur - 0.005, on_t + min_gate)

            clean_events = [tuple(e) for e in clean_events]
            clean_events.sort(key=lambda x: (x[0], 0 if x[4] else 1))
            self.tracks[trk] = clean_events
            self.state = "PLAYING"
            self.overdub_pending = False

        n_notes = len(self.tracks[self.current_track])
        if n_notes == 0:
            # Si no se tocó nada durante el overdub, reactivar overdub en espera para el próximo compás 1
            print(f"\n[LOOPER ⏱ OVERDUB VACÍO] No se detectaron notas en la toma. Reactivando cuenta atrás para el próximo ciclo...", flush=True)
            self.overdub_pending = True
            self.overdub_countdown_beats = 4
            self._play_chime("armed")
        else:
            print(f"\n[LOOPER ▶ PLAY] Pista {self.current_track + 1} completada: {bars} compás(es) ({trk_dur:.2f}s, {n_notes} notas).", flush=True)
            self._play_chime("play")

    def record_event(self, channel: int, note: int, velocity: int, is_note_on: bool):
        now = time.perf_counter()
        trk_prog = None
        if channel == 0 and self.controller:
            trk_prog = self.controller.get_current_melodic_program()

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

            # Disparo por primera nota:
            # IMPORTANTE: El metrónomo sonará como guía mientras se mantenga [L] o tras soltarlo.
            # En Modo Libre (target_b is None), NO existe auto-cierre: graba hasta pulsar [L]+Pad 1.
            target_b = self.selected_loop_bars or self.persistent_fixed_bars
            if target_b is not None:
                def _watchdog_autoclose(gen_id: float, b_count: int):
                    beat_dur = 60.0 / self.bpm
                    max_rec_dur = float(b_count) * 4.0 * beat_dur
                    time.sleep(max_rec_dur)
                    if self.state == "RECORDING" and self.rec_start_time == gen_id:
                        print(f"\n[LOOPER ⏱ AUTO-CIERRE TEMPORIZADO] Alcanzado límite exacto de {b_count} compases. Cerrando loop...", flush=True)
                        self.tap_rec_button()

                threading.Thread(target=_watchdog_autoclose, args=[now, target_b], daemon=True).start()
            return

        elif self.state == "RECORDING":
            raw_offset = max(0.0, now - self.rec_start_time)

            # Auto-cierre de grabación si hay compases objetivo definidos
            target_b = self.selected_loop_bars or self.persistent_fixed_bars
            if target_b is not None:
                beat_dur = 60.0 / self.bpm
                max_rec_dur = float(target_b) * 4.0 * beat_dur
                if raw_offset >= max_rec_dur and is_note_on:
                    print(f"\n[LOOPER ⏱ AUTO-CIERRE] Alcanzado límite de {target_b} compases. Cerrando loop automáticamente...", flush=True)
                    self.tap_rec_button()
                    return

            with self.lock:
                self.tracks[0].append((raw_offset, channel, note, velocity, is_note_on, trk_prog))

        elif self.state == "OVERDUBBING":
            raw_trk_offset = max(0.0, now - self.track_rec_start)
            scale = float(self.bpm) / self.base_bpm if self.base_bpm > 0 else 1.0
            base_offset = raw_trk_offset * scale

            # Input snap window (±75ms): si entra unas décimas tarde en la primera nota, ajustar a t=0.0
            snap_tolerance = 0.075
            if len(self.tracks[self.current_track]) == 0 and is_note_on and base_offset <= snap_tolerance:
                base_offset = 0.0

            with self.lock:
                trk = self.current_track
                self.tracks[trk].append((base_offset, channel, note, velocity, is_note_on, trk_prog))

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
            # Durante ARMED y RECORDING siempre suena para dar el pulso
            click_note = 76 if (beat_idx % 4 == 0) else 77
            click_vel = 90 if (beat_idx % 4 == 0) else 65
            self.fluid.send(f"prog 15 115\ncc 15 7 95\nnoteon 15 {click_note} {click_vel}\n")
            def _click_off(c_note: int):
                time.sleep(0.04)
                self.fluid.send(f"noteoff 15 {c_note}\n")
            threading.Thread(target=_click_off, args=[click_note], daemon=True).start()

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
                # Si todas las 8 pistas quedan vacías, resetear a IDLE para que la próxima grabación tenga metrónomo
                all_empty = all(len(trk) == 0 for trk in self.tracks)
                if all_empty:
                    self.stop_internal()
                    self.state = "IDLE"
                    self.loop_duration = 0.0
                    self.base_loop_duration = 0.0
                    self.current_track = 0

            self.fluid.send("cc 0 123 0\ncc 9 123 0")
            status = " Todas las pistas vacías -> Looper en espera (IDLE)." if all_empty else ""
            print(f"\n[LOOPER 🗑 BORRADO] Pista {track_idx + 1} vaciada por completo. Slot liberado.{status}", flush=True)
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
                    # Actualizar inmediatamente el tempo activo del Looper y del Knob 3
                    if abs(self.bpm - detected) >= 1:
                        self.set_bpm(detected)
                        if self.controller:
                            self.controller.calibrate_knob3_baseline(detected)
                        print(f"\n[AUTO-SYNC TEMPO AKAI -> PI] BPM sincronizado a {detected} BPM (Presets & Metrónomo actualizados)", flush=True)

    def play_preset(self, idx: int):
        if idx >= len(self.preset_patterns):
            return
        # Si se vuelve a pulsar el mismo preset activo, se detiene únicamente el ritmo preset
        if self.preset_idx == idx:
            self.stop_preset()
            return

        self.stop_preset()
        self.preset_idx = idx

        # Always honor the user's active/detected BPM if set, or fall back to preset default
        now = time.time()
        if self.detected_arp_bpm is not None and (now - self.last_arp_detected_time) < 15.0:
            self.bpm = self.detected_arp_bpm
            bpm_source = f"Auto-Sync Arpegiador ({self.detected_arp_bpm} BPM)"
        elif self.bpm != 90:
            # User manually set BPM (via Knob 3 or sync), preserve it for preset
            bpm_source = f"Tempo Activo ({self.bpm} BPM)"
        else:
            self.bpm = self.preset_patterns[idx]["bpm"]
            bpm_source = f"Preset Default ({self.bpm} BPM)"

        self.preset_stop_event.clear()
        self.preset_thread = threading.Thread(target=self._run_preset_loop, daemon=True)
        self.preset_thread.start()
        name = self.preset_patterns[idx]["name"]
        print(f"\n[PRESET BEAT ▶] '{name}' a {self.bpm} BPM [{bpm_source}] (Looper libre para grabar/reproducir encima)", flush=True)

    def stop_preset(self):
        self.preset_stop_event.set()
        self.preset_idx = None
        self.fluid.send("cc 9 123 0\ncc 9 120 0")

    def stop_all(self):
        self.stop_preset()
        self.stop_internal()
        if self.state in ["RECORDING", "OVERDUBBING", "PLAYING"]:
            self.state = "PAUSED"
        elif self.state == "ARMED":
            self.state = "IDLE"
        print("\n[LOOPER & PRESET ⏹ STOP] Todo detenido.", flush=True)

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
                click_vel = 90 if (beat_idx % 4 == 0) else 65
                self.fluid.send(f"prog 15 115\ncc 15 7 95\nnoteon 15 {click_note} {click_vel}\n")
                def _click_rec_off(c_note: int):
                    time.sleep(0.04)
                    self.fluid.send(f"noteoff 15 {c_note}\n")
                threading.Thread(target=_click_rec_off, args=[click_note], daemon=True).start()
            beat_idx += 1

    def _run_playback(self):
        # Rastrear notas activas e índice de eventos por pista de forma independiente
        active_sounding_notes = set()
        track_next_idx = [0 for _ in range(8)]
        track_cycle_start = [time.perf_counter() for _ in range(8)]
        last_played_prog = None

        # Inicializar tiempos de ciclo y claqueta de metrónomo sincronizada
        now_init = time.perf_counter()
        for i in range(8):
            track_cycle_start[i] = now_init

        metro_beat_idx = 0
        metro_next_time = now_init

        while not self.stop_event.is_set() and self.state in ["PLAYING", "OVERDUBBING"]:
            now = time.perf_counter()
            beat_dur = 60.0 / self.bpm

            # ------------------------------------------------------------------
            # METRÓNOMO AUDIBLE SINCRONIZADO AL BUCLE BASE (Si está activado)
            # ------------------------------------------------------------------
            if now >= metro_next_time:
                base_len = self.track_duration[0] if self.track_duration[0] > 0 else (4.0 * beat_dur)
                total_beats_loop = max(4, int(round(base_len / beat_dur)))
                current_loop_beat = metro_beat_idx % total_beats_loop

                # GESTIÓN DE PRE-ROLL DE OVERDUB:
                # Solo emitir la cuenta atrás de 4 clics en los 4 beats EXACTOS antes de volver al Compás 1
                if self.overdub_pending and self.state == "PLAYING":
                    # ¿Estamos en los últimos 4 beats del ciclo base? (desde total_beats_loop - 4 hasta total_beats_loop - 1)
                    beats_until_loop_restart = (total_beats_loop - current_loop_beat) % total_beats_loop
                    if 0 < beats_until_loop_restart <= 4:
                        # Disparar clic de cuenta atrás diferenciado (clic de madera agudo y brillante)
                        countdown_note = 84  # Nota alta y clara de aviso
                        countdown_vel = 95
                        self.fluid.send(f"prog 15 115\ncc 15 7 90\nnoteon 15 {countdown_note} {countdown_vel}\n")
                        def _play_cd_off(cn: int):
                            time.sleep(0.04)
                            self.fluid.send(f"noteoff 15 {cn}\n")
                        threading.Thread(target=_play_cd_off, args=[countdown_note], daemon=True).start()

                        if beats_until_loop_restart == 1:
                            # En el siguiente beat entramos exactamente al Compás 1: programar inicio inmediato
                            threading.Timer(beat_dur * 0.95, self._start_actual_overdub).start()
                    else:
                        # Si aún no estamos en los últimos 4 beats, suena el metrónomo normal
                        if self.metronome_active:
                            is_downbeat = (current_loop_beat == 0)
                            click_note = 76 if is_downbeat else 77
                            click_vel = 85 if is_downbeat else 55
                            self.fluid.send(f"prog 15 115\ncc 15 7 80\nnoteon 15 {click_note} {click_vel}\n")
                            def _play_click_off(cn: int):
                                time.sleep(0.04)
                                self.fluid.send(f"noteoff 15 {cn}\n")
                            threading.Thread(target=_play_click_off, args=[click_note], daemon=True).start()
                else:
                    # Metrónomo estándar durante reproducción normal
                    if self.metronome_active:
                        is_downbeat = (current_loop_beat == 0)
                        click_note = 76 if is_downbeat else 77
                        click_vel = 85 if is_downbeat else 55
                        self.fluid.send(f"prog 15 115\ncc 15 7 80\nnoteon 15 {click_note} {click_vel}\n")
                        def _play_click_off(cn: int):
                            time.sleep(0.04)
                            self.fluid.send(f"noteoff 15 {cn}\n")
                        threading.Thread(target=_play_click_off, args=[click_note], daemon=True).start()

                metro_beat_idx += 1
                metro_next_time += beat_dur

            scale = (self.base_bpm / float(self.bpm)) if (self.base_bpm > 0 and self.bpm > 0) else 1.0
            is_full = bool(self.controller and getattr(self.controller, "keys_full_level", False))

            # Identificar la última pista de teclado (Canal 0) grabada
            last_melodic_trk_idx = None
            if self.revoice_mode:
                for idx_check in reversed(range(8)):
                    if self.tracks[idx_check] and any(e[1] == 0 for e in self.tracks[idx_check]):
                        last_melodic_trk_idx = idx_check
                        break

            with self.lock:
                for trk_idx in range(8):
                    # No reproducir pistas silenciadas ni la pista que actualmente se está grabando en OVERDUB
                    if self.track_muted[trk_idx] or (self.state == "OVERDUBBING" and trk_idx == self.current_track):
                        continue

                    trk_dur = self.track_duration[trk_idx]
                    if trk_dur <= 0 or not self.tracks[trk_idx]:
                        continue

                    elapsed_trk = now - track_cycle_start[trk_idx]

                    # Fin de ciclo de esta pista particular: reiniciar puntero y ciclo de esta pista sin deriva
                    if elapsed_trk >= trk_dur:
                        # Anclaje drift-free: sumar duración exacta en lugar de now
                        track_cycle_start[trk_idx] += trk_dur
                        if (now - track_cycle_start[trk_idx]) >= trk_dur:
                            track_cycle_start[trk_idx] = now
                        track_next_idx[trk_idx] = 0
                        elapsed_trk = max(0.0, now - track_cycle_start[trk_idx])

                    idx = track_next_idx[trk_idx]
                    n_evs = len(self.tracks[trk_idx])
                    while idx < n_evs:
                        ev = self.tracks[trk_idx][idx]
                        scaled_t = ev[0] * scale
                        if scaled_t <= elapsed_trk:
                            t, ch, n, v, is_on = ev[:5]
                            ev_prog = ev[5] if len(ev) > 5 else None

                            # Re-Voice exclusivo de la ÚLTIMA pista melódica grabada:
                            # Las pistas anteriores siempre conservan su ev_prog original.
                            # Solo si trk_idx es last_melodic_trk_idx y self.revoice_mode es True, se omite forzar ev_prog.
                            is_target_revoice = (self.revoice_mode and trk_idx == last_melodic_trk_idx)
                            if ch == 0 and not is_target_revoice and ev_prog is not None:
                                if ev_prog != last_played_prog:
                                    self.fluid.send(f"prog 0 {ev_prog}")
                                    last_played_prog = ev_prog

                            if is_on:
                                if is_full and ch == 0:
                                    play_v = 127
                                else:
                                    play_v = v
                                self.fluid.send(f"noteon {ch} {n} {play_v}")
                                active_sounding_notes.add((ch, n))
                            else:
                                self.fluid.send(f"noteoff {ch} {n}")
                                active_sounding_notes.discard((ch, n))
                            idx += 1
                        else:
                            break
                    track_next_idx[trk_idx] = idx

            time.sleep(0.001)

        # Al salir de reproducción, silenciar cualquier nota restante
        for ch, n in active_sounding_notes:
            self.fluid.send(f"noteoff {ch} {n}")

    def _run_preset_loop(self):
        step_idx = 0
        next_step_time = time.perf_counter()
        while not self.preset_stop_event.is_set():
            if self.preset_idx is None or self.preset_idx >= len(self.preset_patterns):
                break
            pat = self.preset_patterns[self.preset_idx]["steps"]
            step_dur = (60.0 / self.bpm) / 4.0
            notes = pat[step_idx]
            for note, vel in notes:
                self.fluid.send(f"noteon 9 {note} {vel}")
            step_idx = (step_idx + 1) % len(pat)
            next_step_time += step_dur
            delay = next_step_time - time.perf_counter()
            if delay > 0:
                if self.preset_stop_event.wait(delay):
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
                elif kind == "free_reset":
                    # Tono grave descendente confirmando vuelta a MODO LIBRE permanente
                    self.fluid.send("noteon 15 72 65\n")
                    time.sleep(0.08)
                    self.fluid.send("noteoff 15 72\nnoteon 15 60 70\n")
                    time.sleep(0.2)
                    self.fluid.send("noteoff 15 60\n")
                elif kind == "free_timeout":
                    # Caída suave marimba confirmando toma en MODO LIBRE
                    self.fluid.send("noteon 15 76 50\n")
                    time.sleep(0.07)
                    self.fluid.send("noteoff 15 76\nnoteon 15 71 45\n")
                    time.sleep(0.1)
                    self.fluid.send("noteoff 15 71\n")
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
        self.harmonic_fifth_active: bool = False
        self.last_sustain_press: float = 0.0
        self.last_portamento_press: float = 0.0
        self.last_drum_mute_press: float = 0.0
        self.last_keys_mute_press: float = 0.0
        self.reset_default_timer: Optional[threading.Timer] = None
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
        self.reverb_knob_val: int = 50
        self.reverb_level: float = 0.35
        self.reverb_room: float = 0.55
        self.reverb_muted_by_panic: bool = False
        self.sustain_decay_seconds: float = 5.0
        self.active_note_timers: Dict[int, threading.Timer] = {}
        self.lowest_base_c: Optional[int] = 48  # C1 físico por defecto en MPK Mini
        self.active_library_idx: int = 3       # Índice 3 = 0 (Neutral: Pianos, Organs & Keys)
        self.pad_cc_press_times: Dict[int, float] = {}
        self.pad_cc_hold_timers: Dict[int, threading.Timer] = {}
        self.looper_pad_press_times: Dict[int, float] = {}
        self.looper_pad_hold_timers: Dict[int, threading.Timer] = {}
        self.held_cc_pads: Dict[int, float] = {}
        self.dual_pad_selection_timer: Optional[threading.Timer] = None
        self.dual_pad_selection_active: bool = False
        self.dual_pad_selection_mode: Optional[str] = None
        self.last_undo_tap_time: float = 0.0
        self.knob3_last_raw_val: Optional[int] = None
        self.knob3_base_bpm: int = 90
        self.knob3_base_raw: Optional[int] = None
        self.recent_released_notes: Dict[int, float] = {}  # Anti-arpeggiator grace window for modifiers
        self.looper = LiveMidiLooper(fluid, controller=self)
        # Enable FluidSynth effects engines & set responsive velocity curve
        fluid.send("reverb on\nchorus on\n")
        self.apply_key_velocity_router()

    def calibrate_knob3_baseline(self, current_bpm: int):
        """Centra el Knob 3 en el BPM recién configurado o sincronizado."""
        self.knob3_base_bpm = current_bpm
        # Al recalibrar por Arp/sync, el próximo giro físico de Knob 3 arranca exactamente desde este nuevo centro
        self.knob3_base_raw = None

    def apply_key_velocity_router(self):
        if self.keys_full_level:
            # FULL LEVEL: Fuerza 127 de velocidad en todas las teclas (Canal 1 / index 0)
            # BLOQUEA por completo el paso directo de notas en los canales 1..15 por ALSA.
            # Permite el paso de CCs y Pitchbend directamente al motor de síntesis
            cmds = [
                'router_clear',
                'router_begin cc',
                'router_chan 0 15 1 0',
                'router_end',
                'router_begin pbend',
                'router_chan 0 15 1 0',
                'router_end',
                'router_begin prog', 'router_end',
                'router_begin cpress', 'router_end',
                'router_begin note',
                'router_chan 0 0 1 0',
                'router_par2 1 127 0 127',
                'router_end'
            ]
        else:
            # Modo dinámico con curva mejorada (para no tener que aporrear las teclas)
            # Permite el paso de CCs (Pan CC 10, Mod CC 1) y Pitchbend directamente
            cmds = [
                'router_clear',
                'router_begin cc',
                'router_chan 0 15 1 0',
                'router_end',
                'router_begin pbend',
                'router_chan 0 15 1 0',
                'router_end',
                'router_begin prog', 'router_end',
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

    def get_current_melodic_program(self) -> int:
        """Obtiene el número de programa MIDI del instrumento activo según el set seleccionado."""
        try:
            lib_key = LIBRARY_ORDER[self.active_library_idx]
            library = OCTAVE_INSTRUMENT_LIBRARIES.get(lib_key, OCTAVE_INSTRUMENT_LIBRARIES[0])
            prog_num, _ = library[self.current_melodic_idx % len(library)]
            return prog_num
        except Exception:
            return 0

    def start_full_level_timer(self, base_c: int):
        if self.full_level_timer is None:
            def _trigger():
                self.toggle_keys_full_level(base_c)
                self.full_level_timer = None
            self.full_level_timer = threading.Timer(2.0, _trigger)
            self.full_level_timer.daemon = True
            self.full_level_timer.start()

    def cancel_full_level_timer(self):
        if self.full_level_timer is not None:
            self.full_level_timer.cancel()
            self.full_level_timer = None

    def toggle_keys_full_level(self, base_c: int):
        self.keys_full_level = not self.keys_full_level
        self.apply_key_velocity_router()
        # Silenciar de inmediato las dos notas del combo (Lowest C y High B)
        try:
            fluid.send(f"noteoff 0 {base_c}")
            fluid.send(f"noteoff 0 {base_c + 23}")
        except Exception:
            pass

        if self.keys_full_level:
            print("\n[FULL LEVEL TECLADO] -> ACTIVADO (Todas las teclas al 100% de fuerza)", flush=True)
            self.play_chime(active=True)
        else:
            print("\n[FULL LEVEL TECLADO] -> DESACTIVADO (Modo dinámico expresivo)", flush=True)
            self.play_chime(active=False)

    def play_startup_sound(self):
        """Play elegant, soft ascending musical startup chime on isolated Channel 15 (Celesta)."""
        def _worker():
            try:
                time.sleep(0.5)
                # Usar Canal 15 (Celesta) atenuado para no sonar estridente ni saturar
                fluid.send("prog 15 8\ncc 15 7 48\ncc 15 91 80\n")
                chime_notes = [60, 64, 67, 72, 76, 84]
                for n in chime_notes:
                    fluid.send(f"noteon 15 {n} 50\n")
                    time.sleep(0.09)
                    fluid.send(f"noteoff 15 {n}\n")
                print("[STARTUP CHIME] Sistema listo y audio activo.", flush=True)
            except Exception as e:
                print(f"[STARTUP CHIME ERROR] {e}", flush=True)
        threading.Thread(target=_worker, daemon=True).start()

    def start_reset_default_timer(self):
        if self.reset_default_timer is None:
            # Silenciar de inmediato las notas extremas en el piano para evitar choque sonoro
            try:
                active = sorted(list(self.held_keyboard_notes.keys()))
                if len(active) >= 2:
                    fluid.send(f"noteoff 0 {active[0]}\nnoteoff 0 {active[-1]}")
            except Exception:
                pass

            print("\n[AVISO RESET DEFAULT] Mantén pulsadas ambas teclas C extremo izquierdo y C extremo derecho durante 2s para resetear todo a default...", flush=True)

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

            self.reset_default_timer = threading.Timer(2.0, self.execute_reset_default)
            self.reset_default_timer.daemon = True
            self.reset_default_timer.start()

    def cancel_reset_default_timer(self):
        if self.reset_default_timer is not None:
            self.reset_default_timer.cancel()
            self.reset_default_timer = None

    def execute_reset_default(self):
        print("\n" + "="*65, flush=True)
        print(" [RESET DEFAULT] Restaurando sintetizador y controlador a valores por defecto", flush=True)
        print("="*65, flush=True)

        # 1. Silenciar todas las notas y parar looper y presets
        self.looper.stop_all()
        fluid.send("cc 0 120 0\ncc 0 123 0\ncc 9 120 0\ncc 9 123 0")

        # 2. Desactivar todos los efectos (Reverb normal, Chorus OFF, Sustain OFF, Portamento OFF, Quinta OFF)
        self.sustain_active = False
        self.portamento_active = False
        self.harmonic_fifth_active = False
        self.keys_full_level = False
        fluid.send("cc 0 64 0\ncc 0 65 0\nsetportamentomode 0 0\n")
        fluid.send("set synth.chorus.active False\ncc 0 93 0\ncc 0 1 0\n")
        fluid.send("set synth.reverb.active True\ncc 0 91 50\ncc 9 91 50\n")

        # 3. Restablecer instrumentos melódicos y batería a Set 1 Prog 1
        self.active_library_idx = 0  # Set 1 (Grand Piano & Keys)
        self.current_melodic_idx = 0
        first_prog, first_name = OCTAVE_INSTRUMENT_LIBRARIES[LIBRARY_ORDER[0]][0]
        fluid.send(f"prog 0 {first_prog}\nprog 9 0\n")

        # 4. Volúmenes al 100%
        self.current_keys_volume = 127
        self.current_drum_volume = 127
        fluid.send("cc 0 7 127\ncc 9 7 127\n")

        # Chime cristalino de confirmación de Reset Total (Do-Mi-Sol-Do mayor)
        try:
            fluid.send("prog 15 8\ncc 15 7 50\ncc 15 91 80\n")
            for n in [72, 76, 79, 84]:
                fluid.send(f"noteon 15 {n} 55\n")
                time.sleep(0.06)
                fluid.send(f"noteoff 15 {n}\n")
        except Exception:
            pass
        print(f"[RESET DEFAULT COMPLETADO] 1er Instrumento: {first_name} | Efectos limpios | Vol 100%", flush=True)

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

        # CASO 1: SELECCIÓN DE COMPASES (1..8) ACTIVA
        # Si bar_selection_ready está activo tras pulsar Pad 1 con [L] sostenido:
        # Los 8 pads físicos seleccionan estrictamente de 1 a 8 compases (sin activar metrónomo ni pause)
        if self.looper.bar_selection_ready:
            bars_chosen = pad_num + 1

            # Emitir inmediatamente los N clics acústicos de madera al pulsar el pad,
            # antes de soltar [L], evitando solapamiento con la claqueta
            self.looper._play_bar_clicks(bars_chosen, persistent_tone=False)
            self.looper.selected_loop_bars = bars_chosen

            # Si se mantiene pulsado >= 2.0s:
            # Pad 1: reset a MODO LIBRE permanente
            # Pads 2..8: fijar ese número de compases permanentemente
            def _hold_bar_action():
                if pad_num == 0:
                    self.looper.clear_persistent_fixed_bars()
                else:
                    self.looper.select_bar_count(bars_chosen, hold_persistent=True, play_clicks=True)
                self.looper_pad_press_times.pop(pad_num, None)

            timer = threading.Timer(2.0, _hold_bar_action)
            timer.daemon = True
            self.looper_pad_hold_timers[pad_num] = timer
            timer.start()

            print(f"\n[LOOPER ⏱ COMPASES PREVIOS] Pad {pad_num + 1} pulsado -> {bars_chosen} compás(es) elegidos. (Suelta [L] para confirmar e iniciar claqueta)", flush=True)
            return

        # CASO 2: CONTROLES GENERALES DEL LOOPER (cuando NO se están eligiendo compases)
        # PAD 4: Play/Pause inmediato (Tap) / Hold > 1.5s: Clear All Tracks
        if pad_num == 3:
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
            return

        # PAD 3: Metronome Toggle (Tap inmediato limpio)
        elif pad_num == 2:
            self.looper.toggle_metronome()
            return

        # PAD 2: Re-Voice Mode Toggle (Multi-Instrument Lock vs Re-Voice All)
        elif pad_num == 1:
            self.looper.toggle_revoice_mode()
            return

        # PAD 1: Rec / Play / Overdub (RPO) / Hold >= 2.0s: Reset permanente a Modo Libre
        elif pad_num == 0:
            def _hold_pad1_reset_free():
                self.looper.clear_persistent_fixed_bars()
                self.looper_pad_press_times.pop(0, None)

            timer = threading.Timer(2.0, _hold_pad1_reset_free)
            timer.daemon = True
            self.looper_pad_hold_timers[0] = timer
            timer.start()

            self.looper.tap_rec_button()

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
            # Si estaba listo para elegir compases y fue un tap corto (< 2.0s):
            if self.looper.bar_selection_ready:
                bars_chosen = pad_num + 1
                if pad_num > 0:
                    self.looper.selected_loop_bars = bars_chosen
                return

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
            if self.lowest_base_c is None:
                self.lowest_base_c = (note // 12) * 12
            else:
                if note < 48:
                    # Inequívocamente desplazado hacia los graves (OCT-1 base 36, OCT-2 base 24, etc.)
                    target_base = (note // 12) * 12
                    self.lowest_base_c = min(self.lowest_base_c, target_base) if self.lowest_base_c < 48 else target_base
                elif note > 72:
                    # Inequívocamente desplazado hacia los agudos (OCT+1 base 60, OCT+2 base 72, etc.)
                    target_base = ((note - 24 + 11) // 12) * 12
                    self.lowest_base_c = max(self.lowest_base_c, target_base) if self.lowest_base_c > 48 else target_base
                elif 61 <= note <= 72:
                    # Rango exclusivo de octava neutral o superior (imposible en OCT-1 cuyo rango máximo es 60)
                    if self.lowest_base_c < 48:
                        self.lowest_base_c = 48
                elif 48 <= note <= 59:
                    # Rango exclusivo de octava neutral o inferior (imposible en OCT+1 cuyo rango mínimo es 60)
                    if self.lowest_base_c > 48:
                        self.lowest_base_c = 48

            base_c = self.lowest_base_c
            is_neutral_octave = (self.lowest_base_c == 48 and 48 <= note <= 72)

            # Si la reverb fue apagada por pánico de Pad 8, reactivarla limpiamente al tocar la siguiente nota
            if self.reverb_muted_by_panic:
                self.reverb_muted_by_panic = False
                fluid.send(f"set synth.reverb.active True\ncc 0 91 {self.reverb_knob_val}\ncc 9 91 60\ncc 15 91 80")

            # Check for Reset Default Key Combo & Full Level:
            # (Anulados por completo si mute_function_sounds / Performance Lock está activo)
            active_notes = sorted(list(self.held_keyboard_notes.keys()))
            if len(active_notes) >= 2 and not self.mute_function_sounds:
                # Comprobar Tecla 1 (Do más grave del teclado físico) y Tecla 25 (Do más agudo, 2 octavas arriba = +24 semitonos)
                is_lowest_c = any((k % 12 == base_c % 12 and (k - base_c) in [0, -24, 24]) or k == base_c for k in active_notes)
                if (base_c in self.held_keyboard_notes) and ((base_c + 24) in self.held_keyboard_notes):
                    self.start_reset_default_timer()
                # SHORTCUT FULL LEVEL: Mantener pulsado Lowest C (C1) y High B (B3, base_c + 23) a la vez durante 2.0s
                elif (base_c in self.held_keyboard_notes) and ((base_c + 23) in self.held_keyboard_notes):
                    self.start_full_level_timer(base_c)

            # SELECCIÓN CROMÁTICA VÍA TECLADO (Activa mientras Pad 6 y Pad 7 estén ambos pulsados >= 2.0s):
            # Elige entre los 25 instrumentos melódicos del set activo (1:1 con las 25 teclas físicas).
            # (Anulado si Performance Lock está activo)
            if self.dual_pad_selection_active and self.dual_pad_selection_mode == "melodic" and not self.mute_function_sounds:
                fluid.send(f"noteoff 0 {note}")
                key_idx = (note - base_c) % 25
                lib_key = LIBRARY_ORDER[self.active_library_idx]
                library = OCTAVE_INSTRUMENT_LIBRARIES.get(lib_key, OCTAVE_INSTRUMENT_LIBRARIES[0])
                idx = key_idx % len(library)
                self.current_melodic_idx = idx
                prog_num, name = library[idx]
                fluid.send(f"prog 0 {prog_num}")
                print(f"\n[KEYBOARD SELECT] [{LIBRARY_NAMES[self.active_library_idx]}] -> Tecla {key_idx + 1}: {name} (Prog {prog_num})", flush=True)
                play_preview(chan=0, note=72, vel=110, duration=0.35)
                return

            # Continuous Instruments Drone Prevention & Re-trigger cut:
            # (Trumpet, Organs, Strings, Synth Basses, Synth Leads, Warm Pad)
            continuous_progs = {16, 19, 38, 39, 48, 50, 56, 65, 80, 81, 88}
            curr_prog = self.get_current_melodic_program()
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

            # Armonizador de Quinta Justa (+7 semitonos) si Pad 3 está activo:
            if self.harmonic_fifth_active and not self.dual_pad_selection_active:
                fifth_note = note + 7
                if fifth_note <= 127:
                    play_vel = 127 if self.keys_full_level else velocity
                    fluid.send(f"noteon 0 {fifth_note} {play_vel}")

            # Registrar la nota para auto-detección de tempo del arpegiador
            self.looper.register_key_note(note)

            # Grabar notas de teclado en el Looper (incluso si está en ARMED para disparar la grabación):
            # IMPORTANTE: Las teclas modificadoras (C, C#, D, D# en cualquier octava activa)
            # NUNCA deben grabarse en el loop ni disparar la grabación durante modo ARMED.
            is_modifier_key = (note in [48, 49, 50, 51]) or (base_c is not None and note in [base_c, base_c + 1, base_c + 2, base_c + 3])
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

            # Modificadores de teclado para controlar ritmos y sonidos con los pads:
            # Soportan cualquier transposición por OCT-/OCT+, arpegiador activo y Full Level.
            # C1  (48 o base_c + 0) -> SET DE INSTRUMENTOS (Pads 1..8)
            # C#1 (49 o base_c + 1) -> 16 DRUM KITS (Bank A / Bank B)
            # D1  (50 o base_c + 2) -> LIVE LOOPER (8 pads dedicados)
            # D#1 (51 o base_c + 3) -> 16 RITMOS PREGRABADOS + STOP
            base_c = self.lowest_base_c if self.lowest_base_c is not None else 48
            now = time.time()
            # Conjunto de notas activas considerando ventana de gracia (0.35s) anti-corte por arpegiador:
            active_keys = set(self.held_keyboard_notes.keys())
            for n_rel, t_rel in list(self.recent_released_notes.items()):
                if (now - t_rel) < 0.35:
                    active_keys.add(n_rel)
                else:
                    self.recent_released_notes.pop(n_rel, None)

            # Determinar si alguna tecla física de las 4 primeras (C, C#, D, D#) está pulsada
            # en cualquier octava transpuesta (OCT- / neutral / OCT+):
            def _is_physical_key_held(key_index_0_to_3: int) -> bool:
                # Comprobar en base neutral (48 + offset) o base actual transpuesta (base_c + offset)
                target_pitch_mod = (48 + key_index_0_to_3) % 12
                for k in active_keys:
                    if k % 12 == target_pitch_mod:
                        # Si está en el rango de 2 octavas de las 25 teclas
                        if (base_c <= k <= base_c + 24) or (48 <= k <= 72):
                            if (k - base_c) == key_index_0_to_3 or (k - 48) == key_index_0_to_3:
                                return True
                return False

            is_c_held = _is_physical_key_held(0)
            is_cs_held = _is_physical_key_held(1)
            is_d_held = _is_physical_key_held(2)
            is_ds_held = _is_physical_key_held(3)

            if active_keys:
                # MODIFICADOR [K] C + Pads 1..8: Selecciona 8 Melodic Sets (200 sonidos)
                if is_c_held:
                    fluid.send("cc 9 7 0\n" + f"noteoff 9 {note}")
                    self.active_library_idx = pad_num % len(LIBRARY_ORDER)
                    self.current_melodic_idx = 0
                    lib_key = LIBRARY_ORDER[self.active_library_idx]
                    first_prog, first_name = OCTAVE_INSTRUMENT_LIBRARIES[lib_key][0]
                    fluid.send(f"prog 0 {first_prog}")
                    print(f"\n[SET MELÓDICO SELECCIONADO] Pad {pad_num + 1} -> {LIBRARY_NAMES[self.active_library_idx]} (1er Sonido: {first_name})", flush=True)
                    play_preview(chan=0, note=72, vel=110, duration=0.35)
                    vol = max(10, self.current_drum_volume)
                    threading.Timer(0.04, lambda: fluid.send(f"cc 9 7 {vol}")).start()
                    return

                # MODIFICADOR [D] C# + Pads 1..8: Selecciona 16 Drum Sets (Bank A: 1..8 | Bank B: 9..16)
                if is_cs_held:
                    fluid.send("cc 9 7 0\n" + f"noteoff 9 {note}")
                    base_idx = 0 if self.pad_bank == "A" else 8
                    kit_idx = base_idx + pad_num
                    if kit_idx < len(DRUM_KITS):
                        self.current_drum_idx = kit_idx
                        kit_num, name = DRUM_KITS[kit_idx]
                        fluid.send(f"prog 9 {kit_num}")
                        print(f"\n[DRUM SET SELECCIONADO] Pad {pad_num + 1} (Bank {self.pad_bank}) -> Kit {kit_idx + 1}: {name} (Kit {kit_num})", flush=True)
                        play_preview(chan=9, note=36, vel=120, duration=0.35)
                    vol = max(10, self.current_drum_volume)
                    threading.Timer(0.04, lambda: fluid.send(f"cc 9 7 {vol}")).start()
                    return

                # MODIFICADOR [L] D + Pads 1..8: Live Looper
                if is_d_held:
                    # Mute instantáneo del canal 9 para suprimir cualquier fuga del golpe de percusión
                    fluid.send("cc 9 7 0")
                    for h in [50, base_c + 2]:
                        if h in self.held_keyboard_notes:
                            fluid.send(f"noteoff 0 {h}")
                            self.looper.remove_recent_note(0, h, window=1.0)
                    fluid.send(f"noteoff 9 {note}")
                    self.trigger_looper_pad_press(pad_num)
                    vol = max(10, self.current_drum_volume)
                    threading.Timer(0.04, lambda: fluid.send(f"cc 9 7 {vol}")).start()
                    return

                # MODIFICADOR [P] D# + Pads 1..8: 16 Presets de ritmo
                if is_ds_held:
                    fluid.send("cc 9 7 0")
                    for h in [51, base_c + 3]:
                        if h in self.held_keyboard_notes:
                            fluid.send(f"noteoff 0 {h}")
                            self.looper.remove_recent_note(0, h, window=1.0)
                    fluid.send(f"noteoff 9 {note}")
                    self.trigger_preset_pad(pad_num)
                    vol = max(10, self.current_drum_volume)
                    threading.Timer(0.04, lambda: fluid.send(f"cc 9 7 {vol}")).start()
                    return

            # Si no hay modificador (tocar batería libremente con los pads):
            # Mapeos dedicados de percusión simétrica (Bank A <-> Bank B):
            # Pad 4 (idx 11): Cinematic Taiko & Asian Gongs
            # Pad 5 (idx 4 & 12): Afro-Tribal Djembe / Afro-Cuban Batá & Shakers
            # Pad 6 (idx 5 & 13): East Asian Taiko / Middle Eastern Derbake
            # Pad 7 (idx 6 & 14): Latin Salsa / Carnaval Samba & Whistles
            # Pad 8 (idx 7 & 15): Flamenco Cajón 1 / Flamenco Castañuelas 2
            target_note = note
            if self.current_drum_idx == 7:
                # Kit 8 (Pad 8 Bank A): Flamenco Cajón & Palmas 1
                flamenco1_map_a = {36: 36, 37: 38, 38: 37, 39: 39, 40: 75, 41: 76, 42: 77, 43: 67}
                flamenco1_map_b = {44: 44, 45: 54, 46: 69, 47: 70, 48: 80, 49: 81, 50: 73, 51: 74}
                target_note = flamenco1_map_a.get(note, note) if self.pad_bank == "A" else flamenco1_map_b.get(note, note)
            elif self.current_drum_idx == 15:
                # Kit 16 (Pad 8 Bank B): Flamenco Castañuelas & Fusión 2
                # Banco A: Castañuelas, Taconeo, Palmas agudas y Bastón
                # 85: Castanets, 35: Bass Drum / Taconeo, 37: Side Stick / Bastón, 39: Palmas / Clap
                flamenco2_map_a = {36: 35, 37: 37, 38: 85, 39: 39, 40: 75, 41: 76, 42: 54, 43: 58}
                # Banco B: Efectos percusivos, Pandereta, Campana y Jaleos
                flamenco2_map_b = {44: 54, 45: 85, 46: 80, 47: 81, 48: 69, 49: 70, 50: 67, 51: 68}
                target_note = flamenco2_map_a.get(note, note) if self.pad_bank == "A" else flamenco2_map_b.get(note, note)
            elif self.current_drum_idx == 6:
                # Kit 7 (Pad 7 Bank A): Latin & Salsa Percussion
                # Banco A: Congas, Bongós, Timbales y Cencerro
                latin_map_a = {36: 63, 37: 62, 38: 64, 39: 56, 40: 60, 41: 61, 42: 65, 43: 66}
                # Banco B: Percusión Menor y Efectos (Pandereta, Maracas, Cabasa, Güiro, Claves)
                latin_map_b = {44: 54, 45: 70, 46: 69, 47: 73, 48: 74, 49: 75, 50: 67, 51: 68}
                target_note = latin_map_a.get(note, note) if self.pad_bank == "A" else latin_map_b.get(note, note)
            elif self.current_drum_idx == 14:
                # Kit 15 (Pad 7 Bank B): Carnaval & Samba Percussion (Whistles, Cuíca, Agogô, Surdo)
                # Banco A: Surdo grave/mudo, Tamborim/Caixa, Silbato Apito (Short 71 / Long 72), Agogô (67/68)
                samba_map_a = {36: 87, 37: 86, 38: 40, 39: 39, 40: 71, 41: 72, 42: 67, 43: 68}
                # Banco B: Cuíca (78 mute / 79 open), Pandeiro/Tambourine (54), Maracas (70), Cabasa (69), Güiro (74), Triángulo (80/81)
                samba_map_b = {44: 78, 45: 79, 46: 54, 47: 70, 48: 69, 49: 74, 50: 80, 51: 81}
                target_note = samba_map_a.get(note, note) if self.pad_bank == "A" else samba_map_b.get(note, note)
            elif self.current_drum_idx == 4:
                # Kit 5 (Pad 5 Bank A): Afro-Tribal Djembe & Dunun
                # Banco A: Dunun grave (35), Djembe bass (36), Djembe tone (41), Djembe slap (28), Woodblocks (76/77), Shaker (82)
                afro1_map_a = {36: 35, 37: 36, 38: 41, 39: 28, 40: 76, 41: 77, 42: 82, 43: 56}
                # Banco B: Toms tribales, Slap mute, Bell (34/83), Tambores africanos
                afro1_map_b = {44: 43, 45: 45, 46: 47, 47: 48, 48: 27, 49: 75, 50: 67, 51: 68}
                target_note = afro1_map_a.get(note, note) if self.pad_bank == "A" else afro1_map_b.get(note, note)
            elif self.current_drum_idx == 12:
                # Kit 13 (Pad 5 Bank B): Afro-Cuban Batá & Shakers
                # Banco A: Batá Iyá (Low 64), Itótele (Mid 63), Okónkolo (High 62), Cabasa (69), Maracas (70), Shaker (82), Claves (75), Cowbell (56)
                afro2_map_a = {36: 64, 37: 63, 38: 62, 39: 56, 40: 69, 41: 70, 42: 82, 43: 75}
                # Banco B: Vibraslap (58), Güiro (73/74), Agogô (67/68), Bongó (60/61), Slap (28)
                afro2_map_b = {44: 58, 45: 73, 46: 74, 47: 67, 48: 68, 49: 60, 50: 61, 51: 28}
                target_note = afro2_map_a.get(note, note) if self.pad_bank == "A" else afro2_map_b.get(note, note)
            elif self.current_drum_idx == 5:
                # Kit 6 (Pad 6 Bank A): East Asian Taiko & Bells
                # Banco A: Taiko Deep (116), Taiko Rim (37), Woodblocks (76/77), Temple Bells / Triangle (80/81), Chinese Cymbal (52), Gong
                asian1_map_a = {36: 116, 37: 37, 38: 76, 39: 77, 40: 80, 41: 81, 42: 52, 43: 55}
                # Banco B: Melodic Tom (117), Low/High Wood percussion, Finger Snap (31), Reverse Cymbal (119), Belltree (84)
                asian1_map_b = {44: 117, 45: 118, 46: 31, 47: 84, 48: 119, 49: 75, 50: 34, 51: 53}
                target_note = asian1_map_a.get(note, note) if self.pad_bank == "A" else asian1_map_b.get(note, note)
            elif self.current_drum_idx == 13:
                # Kit 14 (Pad 6 Bank B): Middle Eastern Derbake & Riq
                # Banco A: Derbake Dum (Low 36), Tak (High rim 38), Sak (Slap 28), Riq / Def (Tambourine 54), Finger Cymbals / Zills (80/81)
                mideast_map_a = {36: 36, 37: 38, 38: 28, 39: 54, 40: 80, 41: 81, 42: 60, 43: 61}
                # Banco B: Bongós orientales, Shakers (82), Claves (75), Campana (53), Acentos
                mideast_map_b = {44: 54, 45: 82, 46: 62, 47: 63, 48: 69, 49: 70, 50: 67, 51: 68}
                target_note = mideast_map_a.get(note, note) if self.pad_bank == "A" else mideast_map_b.get(note, note)
            elif self.current_drum_idx == 11:
                # Kit 12 (Pad 4 Bank B): Cinematic Taiko & Asian Gongs
                # Banco A: Heavy Taiko (116), Melodic Heavy Tom (117), Synth Impact (118), Chinese Gong Cymbal (52), Splash (55), Crash (49), Ride Bell (53), Reverse Cymbal (119)
                cinematic_map_a = {36: 116, 37: 117, 38: 118, 39: 52, 40: 55, 41: 49, 42: 53, 43: 119}
                # Banco B: Belltree (84), Timpani Low/High, Orchestral Crash, Gong FX
                cinematic_map_b = {44: 84, 45: 80, 46: 81, 47: 119, 48: 57, 49: 58, 50: 34, 51: 28}
                target_note = cinematic_map_a.get(note, note) if self.pad_bank == "A" else cinematic_map_b.get(note, note)

            effective_vel = max(45, velocity)
            fluid.send(f"noteon 9 {target_note} {effective_vel}")
            # Grabar golpe de pad en el Looper (incluso si está en ARMED para disparar la grabación):
            if self.looper.state in ["ARMED", "RECORDING", "OVERDUBBING"]:
                self.looper.record_event(9, target_note, effective_vel, True)
                # Duración uniforme para percusión de pad (120ms)
                def _pad_noteoff(p_note: int):
                    time.sleep(0.12)
                    if self.looper.state in ["RECORDING", "OVERDUBBING"]:
                        self.looper.record_event(9, p_note, 0, False)
                threading.Thread(target=_pad_noteoff, args=[target_note], daemon=True).start()

    def handle_note_off(self, note: int, channel: int):
        base_c = self.lowest_base_c if self.lowest_base_c is not None else 48
        if channel == 0:
            if self.harmonic_fifth_active:
                fluid.send(f"noteoff 0 {note + 7}")
            self.held_keyboard_notes.pop(note, None)
            self.recent_released_notes[note] = time.time()
            self.cancel_reset_default_timer()
            self.cancel_full_level_timer()

            # Si se libera la tecla [L] (D1: 50 o base_c + 2), confirmar selección y arrancar claqueta:
            if note in [50, base_c + 2]:
                if self.looper.bar_selection_ready:
                    self.looper.bar_selection_ready = False
                    # Confirmación definitiva al soltar [L]:
                    chosen = self.looper.selected_loop_bars or self.looper.persistent_fixed_bars
                    if chosen is not None:
                        print(f"\n[LOOPER ⏱ COMPASES CONFIRMADOS] -> {chosen} compás(es). Arrancando claqueta a {self.looper.bpm} BPM...", flush=True)
                    else:
                        print(f"\n[LOOPER ⏱ COMPASES CONFIRMADOS] -> MODO LIBRE puro. Arrancando claqueta a {self.looper.bpm} BPM...", flush=True)

                    # Arrancar metrónomo únicamente AHORA tras soltar [L] si está en ARMED
                    if self.looper.state == "ARMED":
                        if not self.looper.metro_thread or not self.looper.metro_thread.is_alive():
                            self.looper.metro_thread = threading.Thread(target=self.looper._run_armed_metronome, daemon=True)
                            self.looper.metro_thread.start()

            if not self.sustain_active:
                timer = self.active_note_timers.pop(note, None)
                if timer:
                    timer.cancel()
            # Grabar liberación de tecla para mantener duración exacta de notas
            is_modifier_key = (note in [48, 49, 50, 51]) or (note in [base_c, base_c + 1, base_c + 2, base_c + 3])
            if not is_modifier_key and self.looper.state in ["RECORDING", "OVERDUBBING"]:
                self.looper.record_event(0, note, 0, False)
        elif channel == 9:
            pad_num = (note - 36) % 8 if note < 44 else (note - 44) % 8
            # Si se suelta un pad mientras D (50 o base_c + 2) está activo:
            d_held = (50 in self.held_keyboard_notes) or ((base_c + 2) in self.held_keyboard_notes)
            if d_held or pad_num in self.looper_pad_press_times or pad_num in self.looper_pad_hold_timers:
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
                # Si es el primer movimiento tras un auto-sync o inicio, enganchar en la posición física actual
                if self.knob3_base_raw is None:
                    self.knob3_base_raw = value

                self.knob3_last_raw_val = value
                delta_raw = value - self.knob3_base_raw
                # Cada paso de CC desplaza exactamente 1 BPM entero
                bpm = max(30, min(210, self.knob3_base_bpm + delta_raw))
                self.looper.set_bpm(bpm)
                print(f"[KNOB 3 - TEMPO LOOPER] BPM: {bpm} (Paso entero 1 BPM | Base: {self.knob3_base_bpm} BPM)", flush=True)

            elif knob_idx == 3:  # K4: Drum & Loop Beats Volume (Solo Batería y Loops de Percusión - Independiente)
                self.drum_knob_val = value
                self.current_drum_volume = value
                fluid.send(f"cc 9 7 {value}")
                print(f"[KNOB 4 - BATERÍA/LOOPS] Volumen Batería: {int((value / 127.0) * 100)}% (CC 9 7: {value})", flush=True)

            # --- FILA INFERIOR: TECLADO & MASTER (KEYS & OUTPUT) ---
            elif knob_idx == 4:  # K5: Keyboard Reverb Echo (Reverb en Teclado)
                self.reverb_knob_val = value
                rev_lvl = min(1.0, (value / 127.0) * 0.95)
                room = min(1.0, 0.2 + (value / 127.0) * 0.78)
                self.reverb_level = rev_lvl
                self.reverb_room = room
                self.reverb_muted_by_panic = False
                fluid.send(f"reverb 1\nrev_setlevel {rev_lvl:.2f}\nrev_setroomsize {room:.2f}\ncc 0 91 {value}")
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
                    curr_prog = self.get_current_melodic_program()
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

            elif knob_idx == 7:  # K8: Keys / Keyboard Volume (Solo Teclado - Independiente de Batería)
                self.master_knob_val = value
                self.current_keys_volume = value
                fluid.send(f"cc 0 7 {value}")
                print(f"[KNOB 8 - TECLADO] Volumen Keys: {int((value / 127.0) * 100)}% (CC 0 7: {value})", flush=True)

            return

        # ======================================================================
        # 2. PADS EN MODO CC:
        # Banco A: CC 24..31 (Predeterminado Akai MPK Mini MK3) o CC 16..23 / CC 20..27
        # Banco B: CC 32..39
        # ======================================================================
        is_pad_bank_b = (32 <= cc <= 39) or (28 <= cc <= 35 and channel != 9)
        is_pad_bank_a = (24 <= cc <= 31) or (16 <= cc <= 23) or (20 <= cc <= 27)

        if is_pad_bank_a or is_pad_bank_b:
            active_bank = "B" if is_pad_bank_b else "A"
            self.pad_bank = active_bank

            if is_pad_bank_a:
                if 24 <= cc <= 31:
                    pad_idx = cc - 24
                elif 16 <= cc <= 23:
                    pad_idx = cc - 16
                else:
                    pad_idx = cc - 20
            else:
                pad_idx = (cc - 32) if (32 <= cc <= 39) else (cc - 28)

            now = time.time()

            # Si la tecla [L] (50 o base_c + 2) está sostenida, los pads CC dirigen
            # estrictamente el Live Looper (Play/Pause, Mute capas, compases, etc.)
            base_c = self.lowest_base_c if self.lowest_base_c is not None else 48
            is_d_held = (50 in self.held_keyboard_notes) or ((base_c + 2) in self.held_keyboard_notes)
            if is_d_held:
                if value > 0:
                    self.trigger_looper_pad_press(pad_idx)
                else:
                    self.trigger_looper_pad_release(pad_idx)
                return

            # Rastreo dual de Pads 6 (idx 5) y 7 (idx 6) sostenidos juntos >= 2.0s:
            # Mientras estén ambos pulsados >= 2s, las 25 teclas del piano seleccionan:
            # - En Banco A: Instrumento melódico (1 de 25 en el set activo)
            # Detección de doble pulsación simultánea Pad 6 + Pad 7 (sostener 2.0s):
            # Activa Selección Cromática de Instrumentos Melódicos vía teclas (1 de 25 sonidos del set activo)
            if value > 0:
                self.held_cc_pads[pad_idx] = now
                if 5 in self.held_cc_pads and 6 in self.held_cc_pads:
                    if self.dual_pad_selection_timer is None and not self.dual_pad_selection_active:
                        def _activate_dual_selection():
                            self.dual_pad_selection_active = True
                            self.dual_pad_selection_mode = "melodic"
                            mode_label = f"Instrumento Melódico ({LIBRARY_NAMES[self.active_library_idx]})"
                            print(f"\n[MODO SELECCIÓN ACTIVADO - PADS 6+7] Toca cualquiera de las 25 teclas para elegir {mode_label}.", flush=True)
                            self.play_chime(active=True)

                        self.dual_pad_selection_timer = threading.Timer(2.0, _activate_dual_selection)
                        self.dual_pad_selection_timer.daemon = True
                        self.dual_pad_selection_timer.start()
            else:
                self.held_cc_pads.pop(pad_idx, None)
                if pad_idx in [5, 6]:
                    if self.dual_pad_selection_timer is not None:
                        self.dual_pad_selection_timer.cancel()
                        self.dual_pad_selection_timer = None
                    if self.dual_pad_selection_active:
                        self.dual_pad_selection_active = False
                        self.dual_pad_selection_mode = None
                        print(f"\n[MODO SELECCIÓN FINALIZADO] Teclado restaurado a modo notas normal.", flush=True)

            # PAD 1 (Ambos Bancos): Sustain Pedal Toggle (Damper CC 64)
            if pad_idx == 0:
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
                    print(f"\n[PAD CC {active_bank}-1] SUSTAIN PEDAL -> {status}", flush=True)
                else:
                    if (now - self.last_sustain_press) > 0.4:
                        self.sustain_active = False
                        for t in self.active_note_timers.values():
                            t.cancel()
                        self.active_note_timers.clear()
                        fluid.send("cc 0 64 0\ncc 0 123 0")
                        print(f"\n[PAD CC {active_bank}-1] SUSTAIN PEDAL -> DESACTIVADO (Hardware Toggle)", flush=True)

            # PAD 2 (Ambos Bancos): Portamento / Glide Toggle (CC 65 + CC 5)
            elif pad_idx == 1:
                if value > 0:
                    self.last_portamento_press = now
                    self.portamento_active = not self.portamento_active
                    if self.portamento_active:
                        fluid.send("setportamentomode 0 1\ncc 0 5 75\ncc 0 65 127")
                    else:
                        fluid.send("setportamentomode 0 0\ncc 0 65 0")
                    status = "ACTIVADO (Glide activo)" if self.portamento_active else "DESACTIVADO"
                    print(f"\n[PAD CC {active_bank}-2] Portamento/Glide -> {status}", flush=True)
                else:
                    if (now - self.last_portamento_press) > 0.4:
                        self.portamento_active = False
                        fluid.send("setportamentomode 0 0\ncc 0 65 0")
                        print(f"\n[PAD CC {active_bank}-2] Portamento/Glide -> DESACTIVADO (Hardware Toggle)", flush=True)

            # PAD 3 (Ambos Bancos): Armonizador de Quinta Justa (+7 semitonos) Toggle
            elif pad_idx == 2:
                if value > 0:
                    self.harmonic_fifth_active = not self.harmonic_fifth_active
                    status = "ACTIVADO (Voz + Quinta Justa +7 st)" if self.harmonic_fifth_active else "DESACTIVADO (Voz Única)"
                    print(f"\n[PAD CC {active_bank}-3] Armonizador Quinta (+7 st) -> {status}", flush=True)
                    if not self.harmonic_fifth_active:
                        # Silenciar quintas que pudieran haber quedado sonando
                        for n in list(self.held_keyboard_notes.keys()):
                            fluid.send(f"noteoff 0 {n + 7}")

            # PAD 4 (Ambos Bancos): Reverb Kill / Mute
            elif pad_idx == 3:
                fluid.send("reverb off" if value > 0 else "reverb on")
                print(f"[PAD CC {active_bank}-4] Reverb: {'MUTED (Seco)' if value > 0 else 'ON'}", flush=True)

            # PAD 5 (Ambos Bancos): Chorus Splash
            elif pad_idx == 4:
                if value > 0:
                    fluid.send("chorus on\ncho_set_level 1.0\ncho_set_depth 18.0\ncho_set_speed 2.5\ncc 0 93 127")
                    print(f"[PAD CC {active_bank}-5] Chorus Boost: MÁXIMO (DSP Activo)", flush=True)
                else:
                    fluid.send("cho_set_level 0.45\ncho_set_depth 6.0\ncho_set_speed 0.6\ncc 0 93 25")
                    print(f"[PAD CC {active_bank}-5] Chorus Boost: Normal", flush=True)

            # PAD 6 (Ambos Bancos): Instrumento Melódico Anterior / Mantener >0.5s: Set Melódico Anterior
            elif pad_idx == 5:
                if value > 0:
                    self.pad_cc_press_times[5] = now
                    def _hold_pad6_action():
                        if 6 in self.held_cc_pads or self.dual_pad_selection_active:
                            return  # Si Pad 7 también está pulsado, no disparar acción de pad individual
                        self.active_library_idx = (self.active_library_idx - 1) % len(LIBRARY_ORDER)
                        self.current_melodic_idx = 0
                        lib_key = LIBRARY_ORDER[self.active_library_idx]
                        prog_num, name = OCTAVE_INSTRUMENT_LIBRARIES[lib_key][0]
                        fluid.send(f"prog 0 {prog_num}")
                        print(f"\n[PAD CC {active_bank}-6 MANTENIDO >0.5s] -> Set Anterior: {LIBRARY_NAMES[self.active_library_idx]} ({name})", flush=True)
                        play_preview(chan=0, note=60, vel=110, duration=0.35)
                        self.pad_cc_press_times.pop(5, None)

                    # Si el Pad 7 ya está pulsado, cancelar cualquier timer pendiente de Pad 6/7
                    if 6 in self.held_cc_pads:
                        timer7 = self.pad_cc_hold_timers.pop(6, None)
                        if timer7:
                            timer7.cancel()
                    else:
                        timer = threading.Timer(0.5, _hold_pad6_action)
                        timer.daemon = True
                        self.pad_cc_hold_timers[5] = timer
                        timer.start()
                else:
                    timer = self.pad_cc_hold_timers.pop(5, None)
                    if timer:
                        timer.cancel()
                    press_t = self.pad_cc_press_times.pop(5, None)
                    if press_t is not None and not self.dual_pad_selection_active and 6 not in self.held_cc_pads:
                        fluid.send("cc 0 123 0")
                        lib_key = LIBRARY_ORDER[self.active_library_idx]
                        active_lib = OCTAVE_INSTRUMENT_LIBRARIES.get(lib_key, OCTAVE_INSTRUMENT_LIBRARIES[0])
                        self.current_melodic_idx = (self.current_melodic_idx - 1) % len(active_lib)
                        prog_num, name = active_lib[self.current_melodic_idx]
                        fluid.send(f"prog 0 {prog_num}")
                        print(f"\n[PAD CC {active_bank}-6 TAP] Instrumento Anterior ({self.current_melodic_idx + 1}/{len(active_lib)}): {name} (Prog {prog_num})", flush=True)
                        play_preview(chan=0, note=72, vel=110, duration=0.35)

            # PAD 7 (Ambos Bancos): Instrumento Melódico Siguiente / Mantener >0.5s: Set Melódico Siguiente
            elif pad_idx == 6:
                if value > 0:
                    self.pad_cc_press_times[6] = now
                    def _hold_pad7_action():
                        if 5 in self.held_cc_pads or self.dual_pad_selection_active:
                            return  # Si Pad 6 también está pulsado, no disparar acción de pad individual
                        self.active_library_idx = (self.active_library_idx + 1) % len(LIBRARY_ORDER)
                        self.current_melodic_idx = 0
                        lib_key = LIBRARY_ORDER[self.active_library_idx]
                        prog_num, name = OCTAVE_INSTRUMENT_LIBRARIES[lib_key][0]
                        fluid.send(f"prog 0 {prog_num}")
                        print(f"\n[PAD CC {active_bank}-7 MANTENIDO >0.5s] -> Set Siguiente: {LIBRARY_NAMES[self.active_library_idx]} ({name})", flush=True)
                        play_preview(chan=0, note=84, vel=110, duration=0.35)
                        self.pad_cc_press_times.pop(6, None)

                    # Si el Pad 6 ya está pulsado, cancelar cualquier timer pendiente de Pad 6/7
                    if 5 in self.held_cc_pads:
                        timer6 = self.pad_cc_hold_timers.pop(5, None)
                        if timer6:
                            timer6.cancel()
                    else:
                        timer = threading.Timer(0.5, _hold_pad7_action)
                        timer.daemon = True
                        self.pad_cc_hold_timers[6] = timer
                        timer.start()
                else:
                    timer = self.pad_cc_hold_timers.pop(6, None)
                    if timer:
                        timer.cancel()
                    press_t = self.pad_cc_press_times.pop(6, None)
                    if press_t is not None and not self.dual_pad_selection_active and 5 not in self.held_cc_pads:
                        fluid.send("cc 0 123 0")
                        lib_key = LIBRARY_ORDER[self.active_library_idx]
                        active_lib = OCTAVE_INSTRUMENT_LIBRARIES.get(lib_key, OCTAVE_INSTRUMENT_LIBRARIES[0])
                        self.current_melodic_idx = (self.current_melodic_idx + 1) % len(active_lib)
                        prog_num, name = active_lib[self.current_melodic_idx]
                        fluid.send(f"prog 0 {prog_num}")
                        print(f"\n[PAD CC {active_bank}-7 TAP] Instrumento Siguiente ({self.current_melodic_idx + 1}/{len(active_lib)}): {name} (Prog {prog_num})", flush=True)
                        play_preview(chan=0, note=72, vel=110, duration=0.35)

            # PAD 8 (Ambos Bancos): Pánico (<2s) / Mantener >=2s: Toggle Mute Sonidos Auxiliares
            elif pad_idx == 7:
                if value > 0:
                    self.pad_cc_press_times[7] = now
                    def _hold_toggle_chime_mute():
                        if not self.mute_function_sounds:
                            fluid.send("prog 15 8\ncc 15 91 60\nnoteon 15 76 70\n")
                            time.sleep(0.09)
                            fluid.send("noteoff 15 76\nnoteon 15 69 65\n")
                            time.sleep(0.12)
                            fluid.send("noteoff 15 69\n")
                            self.mute_function_sounds = True
                            st = "BLOQUEADAS / LOCK (Chimes OFF y Teclas 100% notas puras, sin funciones ni apagado)"
                        else:
                            self.mute_function_sounds = False
                            fluid.send("prog 15 8\ncc 15 91 80\nnoteon 15 84 75\n")
                            time.sleep(0.08)
                            fluid.send("noteoff 15 84\nnoteon 15 88 80\n")
                            time.sleep(0.1)
                            fluid.send("noteoff 15 88\n")
                            st = "ACTIVAS / UNLOCKED (Chimes ON y funciones de teclado [S], [L], [P], [F], [—] operativas)"
                        print(f"\n[PAD CC {active_bank}-8 MANTENIDO 2s] -> Funciones de Teclado: {st}", flush=True)
                        self.pad_cc_press_times.pop(7, None)

                    timer = threading.Timer(2.0, _hold_toggle_chime_mute)
                    timer.daemon = True
                    self.pad_cc_hold_timers[7] = timer
                    timer.start()

                else:
                    timer = self.pad_cc_hold_timers.pop(7, None)
                    if timer:
                        timer.cancel()
                    press_t = self.pad_cc_press_times.pop(7, None)
                    if press_t is not None:
                        for t in self.active_note_timers.values():
                            t.cancel()
                        self.active_note_timers.clear()

                        self.looper.stop_all()

                        kill_cmds = []
                        for c in range(16):
                            kill_cmds.append(f"cc {c} 120 0\ncc {c} 123 0")
                        kill_cmds.append("set synth.reverb.active False")
                        self.reverb_muted_by_panic = True
                        fluid.send("\n".join(kill_cmds))

                        if self.held_keyboard_notes:
                            offs = "\n".join(f"noteoff 0 {k}" for k in list(self.held_keyboard_notes.keys()))
                            fluid.send(offs)
                            self.held_keyboard_notes.clear()

                        if self.sustain_active:
                            fluid.send("cc 0 64 127")
                        else:
                            fluid.send("cc 0 64 0")

                        print(f"\n[PAD CC {active_bank}-8 TAP] ¡PÁNICO TOTAL! Silencio absoluto en seco (Reverb OFF hasta la siguiente nota).", flush=True)

        # ======================================================================
        # 3. PEDAL DE SUSTAIN FÍSICO TRASERO (JACK 1/4" DEL AKAI): CC 64
        # ======================================================================
        elif cc == 64:
            self.sustain_active = (value > 63)
            fluid.send(f"cc 0 64 {value}")
            print(f"[PEDAL SUSTAIN TRASERO CC 64] -> {'ACTIVADO' if value > 63 else 'DESACTIVADO'}", flush=True)

        # ======================================================================
        # 4. JOYSTICK 4-VÍAS EN MODO CC:
        # X: CC 10 (Pan Stereo Izquierda / Derecha)
        # Y: CC 1 (Modulation Wheel) y CC 74 (Brillo / Filtro Cutoff)
        # ======================================================================
        elif cc == 10:  # Pan horizontal
            # Enviar pan a todos los canales de instrumento
            fluid.send(f"cc 0 10 {value}\ncc 1 10 {value}\ncc 2 10 {value}\ncc 3 10 {value}")
            pan_pct = int(((value - 64) / 64.0) * 100)
            side = f"R {pan_pct}%" if pan_pct > 0 else (f"L {abs(pan_pct)}%" if pan_pct < 0 else "Centro")
            print(f"[JOYSTICK CC 10 - PAN STEREO] -> {side} (CC: {value})", flush=True)

        elif cc in [1, 74]:  # Modulación / Filtro vertical
            fluid.send(f"cc 0 1 {value}\ncc 0 74 {value}")
            print(f"[JOYSTICK CC {cc} - MOD/FILTRO] -> {int((value/127.0)*100)}%", flush=True)

    def run(self):
        print("==================================================================")
        print(" Akai MPK Mini - Live Beat Looper & Standalone Synth Workstation  ")
        print("==================================================================")
        print(" • ● (Big Dot Full Volume): Mantén [●] C2 + [●] B3 (2s) -> 100% vs dinámico")
        print(" • — (Line Reset Default): Mantén [—] C2 + [—] C4 (2s) -> Reset fábrica sintetizador")
        print(" • K (Keys - Melodic Sets): Mantén [K] C2 + Pads 1..8 -> 8 Sets Melódicos (200 sonidos)")
        print(" • D (Drums - Drum Sets): Mantén [D] C#2 + Pads 1..8 -> 16 Drum Sets (P8 Bank A: Flamenco)")
        print(" • L (Looper): Mantén [L] D2 + Pads 1..8 -> 8-Track Beat Looper")
        print(" • P (Presets): Mantén [P] D#2 + Pads 1..8 -> 16 Beat Grooves")
        print(" • PADS 6+7 (2s en CC): Modo Selección Teclas (25 sonidos melódicos)")
        print(" • PAD 8 (2s en CC): Performance Lock (Silencia chimes y anula 100% funciones de teclas)")
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
                            elif msg.type == "pitchwheel":
                                # Pitch Bend estándar del joystick
                                fluid.send(f"pitch_bend {msg.channel} {msg.pitch}")
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
