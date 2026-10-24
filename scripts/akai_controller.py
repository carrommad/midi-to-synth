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
from typing import Optional, Set
import mido

FLUID_HOST = "localhost"
FLUID_PORT = 9800

# 24 Melodic Instruments (Mapped to Keys 1..24 while holding Lowest Key)
MELODIC_INSTRUMENTS = [
    (0, "Yamaha Grand Piano"),
    (1, "Bright Acoustic Piano"),
    (2, "Electric Piano (Rhodes)"),
    (4, "Electric Piano (FM DX7)"),
    (6, "Harpsichord"),
    (7, "Clavinet"),
    (16, "Drawbar Organ (Hammond B3)"),
    (19, "Church Pipe Organ"),
    (24, "Nylon Acoustic Guitar"),
    (25, "Steel String Acoustic Guitar"),
    (27, "Clean Electric Guitar"),
    (29, "Overdrive Rock Guitar"),
    (32, "Acoustic Upright Bass"),
    (33, "Fingered Electric Bass"),
    (36, "Slap Funk Bass"),
    (38, "Synth Bass 1 (Classic 808 Sub)"),
    (39, "Synth Bass 2 (Acid 303 Bass)"),
    (48, "String Ensemble"),
    (50, "Synth Strings"),
    (56, "Trumpet (Trompeta)"),
    (65, "Alto Saxophone"),
    (80, "Synth Lead 1 (Square Wave)"),
    (81, "Synth Lead 2 (Sawtooth Wave)"),
    (88, "Warm Synth Pad"),
]

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
    def __init__(self, fluid_client: FluidClient):
        self.fluid = fluid_client
        self.state: str = "IDLE"  # "IDLE", "RECORDING", "PLAYING", "OVERDUBBING", "PAUSED", "PRESET"
        self.bpm: int = 90
        self.metronome_active: bool = True
        # 4 Pistas independientes (Layers 1..4): cada pista es una lista de (phase_sec, channel, note, velocity, is_note_on)
        self.tracks: list = [[], [], [], []]
        self.track_muted: list = [False, False, False, False]
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

        # 7 Preset groove templates for instant jamming (Pads 1 to 7)
        self.preset_idx: Optional[int] = None
        self.preset_patterns = [
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
            {
                "name": "Afrobeat / Latin Groove",
                "bpm": 108,
                "steps": [
                    [(36, 120), (42, 85)], [(37, 100)], [(42, 75)], [(36, 95)],
                    [(37, 105), (42, 85)], [], [(36, 110), (42, 75)], [(37, 95)],
                    [(42, 85)], [(36, 100), (37, 100)], [(42, 75)], [],
                    [(37, 110), (42, 85)], [(36, 90)], [(46, 85)], [(37, 95)]
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

    def remove_recent_note(self, channel: int, note: int, window: float = 1.0):
        with self.lock:
            for trk in range(4):
                if not self.tracks[trk]:
                    continue
                max_t = max(ev[0] for ev in self.tracks[trk])
                threshold = max(0.0, max_t - window)
                self.tracks[trk] = [
                    ev for ev in self.tracks[trk]
                    if not (ev[1] == channel and ev[2] == note and ev[0] >= threshold)
                ]

    def tap_rec_button(self):
        """Workflow profesional HÍBRIDO (B + C):
        1. Estado ARMED (Aclimatación): Suena el metrónomo continuo a BPM de K3. El usuario escucha y se aclimata.
        2. Disparo por Primera Nota (Filosofía C): En cuanto tocas la primera nota/pad, arranca la grabación como Tiempo 0 con chime agudo.
        3. Cierre Inteligente (Tolerancia generosa ~0.5 compases): Al pulsar D1 + Pad 1 para cerrar, si terminaste tu frase
           en el compás N y pulsas un poco después (hasta medio compás más), se redondea limpiamente al compás N y arranca
           el loop al instante sin esperar otro compás entero en silencio.
        4. Overdub (Capas 2, 3 y 4 con Pad 1 alternado):
           - Pulsar Pad 1 en PLAYING -> Graba capa 2 (o siguiente libre).
           - Pulsar Pad 1 en OVERDUBBING -> Cierra esa capa y vuelve a PLAYING.
        """
        self.preset_idx = None

        if self.state in ["IDLE", "PAUSED"]:
            # ENTRAR EN MODO ARMED (Escuchar metrónomo sin límite de compases para coger el compás)
            with self.lock:
                for i in range(4):
                    self.tracks[i].clear()
                    self.track_muted[i] = False
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
            # Si el usuario vuelve a pulsar Pad 1 sin haber tocado nada, cancela
            self.stop_all()

        elif self.state == "RECORDING":
            # CIERRE CON REDONDEO INTELIGENTE (Ventana generosa de 0.5 compases)
            # No esperamos otro compás entero en silencio: calculamos compases de inmediato
            now = time.perf_counter()
            elapsed = max(0.01, now - self.rec_start_time)
            beat_dur = 60.0 / self.bpm
            bar_dur = 4.0 * beat_dur

            # Cuántos compases han transcurrido en decimal
            raw_bars = elapsed / bar_dur
            # Si se pasa un poco del compás (ej: 1.1 compases o 1.4 compases), redondea al compás anterior (1 compás).
            # Si lleva 1.6 compases, se asume que iba a por el compás 2.
            # max(1, ...) asegura que como mínimo sea 1 compás completo.
            bars = max(1, round(raw_bars))
            self.base_loop_duration = bars * bar_dur
            self.loop_duration = self.base_loop_duration

            with self.lock:
                wrapped = []
                for t, ch, n, v, is_on in self.tracks[0]:
                    # Notas que entraron ligeramente después del cierre se envuelven o truncan
                    if t <= self.base_loop_duration:
                        wrapped.append((t, ch, n, v, is_on))
                    elif t <= (self.base_loop_duration + 0.35 * bar_dur):
                        # Nota de final de frase tocada ligeramente tarde: envolver al inicio de compás
                        wrapped.append((t % self.base_loop_duration, ch, n, v, is_on))
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
            # ENTER OVERDUB MODE (Buscar la siguiente capa libre entre 2, 3 y 4)
            next_trk = None
            for idx in range(1, 4):
                if len(self.tracks[idx]) == 0:
                    next_trk = idx
                    break
            if next_trk is None:
                # Si todas tienen notas, rota entre capas 1..3
                next_trk = (self.current_track + 1) % 4
                if next_trk == 0:
                    next_trk = 1

            self.current_track = next_trk
            self.track_muted[self.current_track] = False
            self.state = "OVERDUBBING"
            print(f"\n[LOOPER 🟠 OVERDUB] ¡Grabando en Capa {self.current_track + 1} de 4! Pulsa D1+Pad 1 para cerrar la capa.", flush=True)
            self._play_chime("overdub")

        elif self.state == "OVERDUBBING":
            # FINISH OVERDUB -> RETURN TO PLAY
            self.state = "PLAYING"
            with self.lock:
                self.tracks[self.current_track].sort(key=lambda x: x[0])
            n_notes = len(self.tracks[self.current_track])
            print(f"\n[LOOPER ▶ PLAY] Capa {self.current_track + 1} completada ({n_notes} notas grabadas).", flush=True)
            self._play_chime("play")

    def record_event(self, channel: int, note: int, velocity: int, is_note_on: bool):
        now = time.perf_counter()

        # Si el Looper está en modo ARMED y el músico toca la primera nota:
        if self.state == "ARMED" and is_note_on:
            with self.lock:
                self.state = "RECORDING"
                self.rec_start_time = now
                self.base_bpm = self.bpm
                self.finish_pending = False
                self.tracks[0].clear()
                # Registrar el primer evento exactamente en t = 0.0
                self.tracks[0].append((0.0, channel, note, velocity, is_note_on))
            print(f"\n[LOOPER 🔴 REC] ¡Primera nota detectada! Grabación iniciada a {self.bpm} BPM...", flush=True)
            self._play_chime("start_rec")
            return

        elif self.state == "RECORDING":
            offset = max(0.0, now - self.rec_start_time)
            with self.lock:
                self.tracks[0].append((offset, channel, note, velocity, is_note_on))

        elif self.state == "OVERDUBBING" and self.loop_duration > 0:
            phase = (now - self.cycle_start_time) % self.loop_duration
            scale = float(self.bpm) / self.base_bpm if self.base_bpm > 0 else 1.0
            base_phase = phase * scale
            with self.lock:
                trk = self.current_track
                self.tracks[trk].append((base_phase, channel, note, velocity, is_note_on))

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

            # Sonido de claqueta durante ARMED y RECORDING
            if self.metronome_active:
                click_note = 76 if (beat_idx % 4 == 0) else 77
                click_vel = 100 if (beat_idx % 4 == 0) else 65
                self.fluid.send(f"noteon 9 {click_note} {click_vel}")

            beat_idx += 1

    def toggle_track_mute(self, track_idx: int):
        """Silenciar o activar una de las 4 pistas (Pads 5..8 con D1 pulsado corto)."""
        if 0 <= track_idx < 4:
            self.track_muted[track_idx] = not self.track_muted[track_idx]
            status = "🔇 MUTEADA" if self.track_muted[track_idx] else "🔊 ACTIVA"
            n_notes = len(self.tracks[track_idx])
            print(f"\n[LOOPER CAPA {track_idx + 1}] -> {status} ({n_notes} notas grabadas)", flush=True)
            if self.track_muted[track_idx]:
                # Chime grave tenue (Mute)
                self.fluid.send("cc 0 123 0\ncc 9 123 0")
                self._play_chime("track_mute")
            else:
                # Chime agudo brillante (Unmute)
                self._play_chime("track_unmute")

    def delete_track(self, track_idx: int):
        """Borrar individualmente una de las 4 pistas (Pads 5..8 sostenido > 1.0s con D1)."""
        if 0 <= track_idx < 4:
            with self.lock:
                self.tracks[track_idx].clear()
                self.track_muted[track_idx] = False
            self.fluid.send("cc 0 123 0\ncc 9 123 0")
            print(f"\n[LOOPER 🗑 BORRADO] Capa {track_idx + 1} vaciada por completo.", flush=True)
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

    def clear(self):
        with self.lock:
            self.stop_internal()
            for i in range(4):
                self.tracks[i].clear()
                self.track_muted[i] = False
            self.current_track = 0
            self.loop_duration = 0.0
            self.state = "IDLE"
            self.preset_idx = None
        print("\n[LOOPER 🗑 RESET TOTAL] Todas las 4 capas borradas. Sesión reseteada.", flush=True)
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
                click_vel = 100 if (beat_idx % 4 == 0) else 70
                self.fluid.send(f"noteon 9 {click_note} {click_vel}")
            beat_idx += 1

    def _run_playback(self):
        while not self.stop_event.is_set() and self.state in ["PLAYING", "OVERDUBBING"]:
            self.cycle_start_time = time.perf_counter()
            dur = self.loop_duration
            if dur <= 0:
                time.sleep(0.01)
                continue

            # Recolectar notas activas de las pistas no silenciadas
            evs = []
            with self.lock:
                for trk_idx in range(4):
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
                while idx < n_evs:
                    scaled_t = evs[idx][0] * scale
                    if scaled_t <= elapsed:
                        _, ch, n, v, is_on = evs[idx]
                        if is_on:
                            self.fluid.send(f"noteon {ch} {n} {v}")
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
        def _worker():
            try:
                self.fluid.send("prog 15 8\ncc 15 91 80")
                if kind in ["rec", "start_rec"]:
                    # Chime ascendente brillante de inicio de grabación (Do-Mi agudos)
                    self.fluid.send("noteon 15 84 90\n")
                    time.sleep(0.06)
                    self.fluid.send("noteoff 15 84\nnoteon 15 88 95\n")
                    time.sleep(0.1)
                    self.fluid.send("noteoff 15 88\n")
                elif kind in ["play", "end_rec"]:
                    # Chime resolutivo cristalino de cierre de bucle y loop activo
                    self.fluid.send("noteon 15 72 85\n")
                    time.sleep(0.06)
                    self.fluid.send("noteoff 15 72\nnoteon 15 76 85\n")
                    time.sleep(0.08)
                    self.fluid.send("noteoff 15 76\n")
                elif kind == "armed":
                    # Toque suave de preparación para escuchar la claqueta
                    self.fluid.send("noteon 15 79 80\n")
                    time.sleep(0.06)
                    self.fluid.send("noteoff 15 79\n")
                elif kind == "overdub":
                    self.fluid.send("noteon 15 79 90\n")
                    time.sleep(0.06)
                    self.fluid.send("noteoff 15 79\nnoteon 15 83 90\n")
                    time.sleep(0.1)
                    self.fluid.send("noteoff 15 83\n")
                elif kind == "pause":
                    self.fluid.send("noteon 15 76 75\n")
                    time.sleep(0.08)
                    self.fluid.send("noteoff 15 76\nnoteon 15 72 70\n")
                    time.sleep(0.1)
                    self.fluid.send("noteoff 15 72\n")
                elif kind == "track_mute":
                    # Tono grave suave apagado (Do grave)
                    self.fluid.send("noteon 15 48 85\n")
                    time.sleep(0.08)
                    self.fluid.send("noteoff 15 48\n")
                elif kind == "track_unmute":
                    # Tono agudo brillante (Do agudo)
                    self.fluid.send("noteon 15 72 90\n")
                    time.sleep(0.08)
                    self.fluid.send("noteoff 15 72\n")
                elif kind == "track_deleted":
                    # Acorde suave de disolución (Mi-Do grave)
                    self.fluid.send("noteon 15 64 80\n")
                    time.sleep(0.07)
                    self.fluid.send("noteoff 15 64\nnoteon 15 52 75\n")
                    time.sleep(0.12)
                    self.fluid.send("noteoff 15 52\n")
                elif kind == "clear":
                    self.fluid.send("noteon 15 64 75\n")
                    time.sleep(0.08)
                    self.fluid.send("noteoff 15 64\nnoteon 15 60 70\n")
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
        self.startup_sound_played: bool = False
        self.running = True
        self.keys_full_level: bool = False
        self.current_drum_volume: int = 100
        self.lowest_base_c: Optional[int] = 48  # C1 físico por defecto en MPK Mini
        self.looper_pad_press_times: Dict[int, float] = {}
        self.looper_pad_hold_timers: Dict[int, threading.Timer] = {}
        self.looper = LiveMidiLooper(fluid)
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
        def _worker():
            try:
                fluid.send("prog 15 8")     # Celesta / Campanas suaves
                fluid.send("cc 15 91 85")   # Reverb cálida
                if active:
                    # Chime ascendente cristalino y suave (Do-Mi-Sol-Do)
                    for n in [72, 76, 79, 84]:
                        fluid.send(f"noteon 15 {n} 78")
                        time.sleep(0.055)
                        fluid.send(f"noteoff 15 {n}")
                else:
                    # Chime descendente tenue y relajante (Sol-Mi-Do)
                    for n in [79, 76, 72]:
                        fluid.send(f"noteon 15 {n} 65")
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
                    fluid.send(f"noteon 0 {n} 115")
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

            print("\n[AVISO APAGADO] Mantén pulsadas ambas teclas C1 y C3 durante 3 segundos para apagar el sistema...", flush=True)

            # Toque sutil de aviso (Do central apagado en canal 15 Celesta)
            def _subtle_warning():
                try:
                    fluid.send("prog 15 8\ncc 15 91 80\nnoteon 15 67 60")
                    time.sleep(0.08)
                    fluid.send("noteoff 15 67")
                except Exception:
                    pass
            threading.Thread(target=_subtle_warning, daemon=True).start()

            self.shutdown_timer = threading.Timer(3.0, self.execute_safe_shutdown)
            self.shutdown_timer.daemon = True
            self.shutdown_timer.start()

    def cancel_shutdown_timer(self):
        if self.shutdown_timer is not None:
            self.shutdown_timer.cancel()
            self.shutdown_timer = None

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
        if pad_num == 0:    # Pad 1: Rec / Play / Overdub (RPO)
            self.looper.tap_rec_button()
        elif pad_num == 1:  # Pad 2: Play / Pause
            self.looper.toggle_play_pause()
        elif pad_num == 2:  # Pad 3: Metronome Toggle (Mute/Unmute)
            self.looper.toggle_metronome()
        elif pad_num == 3:  # Pad 4: Borrar todo el bucle
            self.looper.clear()
        elif pad_num in [4, 5, 6, 7]:  # Pads 5..8: Capas 1..4
            trk_idx = pad_num - 4
            # Programar temporizador de pulsación larga (> 1.0s) para borrado de capa
            def _delete_action():
                self.looper.delete_track(trk_idx)
                # Marcar que se ejecutó el borrado largo para no alternar mute al soltar
                self.looper_pad_press_times.pop(pad_num, None)

            timer = threading.Timer(1.0, _delete_action)
            timer.daemon = True
            self.looper_pad_hold_timers[pad_num] = timer
            timer.start()

    def trigger_looper_pad_release(self, pad_num: int):
        # Cancelar timer de borrado si se suelta antes de 1.0s
        timer = self.looper_pad_hold_timers.pop(pad_num, None)
        if timer is not None:
            timer.cancel()

        press_t = self.looper_pad_press_times.pop(pad_num, None)
        if press_t is not None and pad_num in [4, 5, 6, 7]:
            # Pulsación corta (< 1.0s): Conmutar Silenciar / Activar (Mute Toggle)
            trk_idx = pad_num - 4
            self.looper.toggle_track_mute(trk_idx)

    def trigger_preset_pad(self, pad_num: int):
        if 0 <= pad_num < len(self.looper.preset_patterns):  # Pads 1..8: 8 Ritmos Pregrabados
            self.looper.play_preset(pad_num)
        else:
            self.looper.stop_all()

    def handle_note_on(self, note: int, velocity: int, channel: int):
        # Only process keys (Channel 1, which is channel index 0)
        if channel == 0:
            now = time.time()
            self.held_keyboard_notes[note] = now

            # Actualizar la tecla base más grave física (C1) de forma adaptativa
            if self.lowest_base_c is None or note < self.lowest_base_c:
                # La tecla más grave del Akai es siempre una nota Do (múltiplo de 12)
                if (note % 12) == 0:
                    self.lowest_base_c = note

            # Check for Safe Shutdown Key Combo:
            # Hold Lowest C (C1) and Highest C (C3) together for 3.0 seconds
            active_notes = sorted(list(self.held_keyboard_notes.keys()))
            if len(active_notes) >= 2:
                lowest_k = active_notes[0]
                highest_k = active_notes[-1]
                if (highest_k - lowest_k == 24) and (lowest_k % 12 == 0) and (highest_k % 12 == 0):
                    self.start_shutdown_timer()

            # SHORTCUT: Pulsar C1 + C#1 a la vez (EXCLUSIVAMENTE las 2 primeras teclas del extremo izquierdo del teclado)
            # Para evitar que pulsar la 8ª y 9ª tecla (Do central y Do#) active Full Level por error:
            if self.looper.state not in ["RECORDING", "OVERDUBBING"] and len(active_notes) >= 2:
                lowest_note = active_notes[0]
                # Solo se activa si la nota más grave es EXACTAMENTE la tecla física C1 (la más grave del teclado)
                if self.lowest_base_c is not None and lowest_note == self.lowest_base_c:
                    if (lowest_note + 1) in self.held_keyboard_notes:
                        self.toggle_keys_full_level(lowest_note)
                        return

            # Check if any held note is an intentional modifier key (ONLY when not actively recording music)
            # REGLA DE ORO:
            # 1. El modificador C1/C#1 DEBE ser exclusivamente la tecla 1 o 2 del extremo izquierdo (self.lowest_base_c).
            # 2. La tecla modificadora DEBE haber estado sostenida deliberadamente (mínimo 0.22s) ANTES de pulsar la otra tecla.
            if self.looper.state not in ["RECORDING", "OVERDUBBING"] and len(active_notes) >= 2:
                lowest_note = active_notes[0]
                modifier_hold_time = now - self.held_keyboard_notes.get(lowest_note, now)

                # Solo actúa como modificador si es la tecla física C1 o C#1 del extremo izquierdo
                is_physical_modifier = (self.lowest_base_c is not None and lowest_note in [self.lowest_base_c, self.lowest_base_c + 1])
                if is_physical_modifier and modifier_hold_time >= 0.22 and note >= (lowest_note + 2):
                    base_c = self.lowest_base_c

                    # MODIFIER 1: Tecla C1 (Blanca, más grave) -> CAMBIO DE PIANO / MELÓDICO
                    if lowest_note == base_c:
                        fluid.send(f"noteoff 0 {note}\nnoteoff 0 {base_c}")
                        idx = (note - (base_c + 2)) % len(MELODIC_INSTRUMENTS)
                        self.current_melodic_idx = idx
                        prog_num, name = MELODIC_INSTRUMENTS[idx]
                        fluid.send(f"prog 0 {prog_num}")
                        print(f"\n[KEYBOARD SELECT] -> Tecla {idx + 1}: {name} (Prog {prog_num})")
                        play_preview(chan=0, note=72, vel=110, duration=0.35)
                        return

                    # MODIFIER 2: Tecla C#1 (Negra contigua) -> CAMBIO DE BATERÍAS (DRUM KITS)
                    if lowest_note == (base_c + 1):
                        fluid.send(f"noteoff 0 {note}\nnoteoff 0 {base_c + 1}")
                        idx = (note - (base_c + 2)) % len(DRUM_KITS)
                        self.current_drum_idx = idx
                        kit_num, name = DRUM_KITS[idx]
                        fluid.send(f"prog 9 {kit_num}")
                        print(f"\n[DRUM KIT SELECT] -> Tecla {idx + 1}: {name} (Kit {kit_num})")
                        play_preview(chan=9, note=36, vel=120, duration=0.35)
                        return

            # Registrar la nota para auto-detección de tempo del arpegiador
            self.looper.register_key_note(note)

            # Grabar notas de teclado en el Looper (incluso si está en ARMED para disparar la grabación):
            if self.looper.state in ["ARMED", "RECORDING", "OVERDUBBING"]:
                self.looper.record_event(0, note, velocity, True)

        # Si se tocan los pads (Canal 10 / index 9 en FluidSynth):
        elif channel == 9:
            # Detectar si estamos en Banco A (< 44) o Banco B (>= 44)
            if note >= 44:
                self.pad_bank = "B"
            else:
                self.pad_bank = "A"

            pad_num = (note - 36) % 8 if note < 44 else (note - 44) % 8

            # Modificadores de teclado para controlar ritmos con los pads:
            # D1  (segunda tecla blanca, semitono 2) -> LIVE LOOPER (8 pads dedicados)
            # D#1 (segunda tecla negra, semitono 3)  -> 7 RITMOS PREGRABADOS + STOP
            if self.held_keyboard_notes:
                is_d_held = any((h % 12 == 2) for h in self.held_keyboard_notes)
                is_ds_held = any((h % 12 == 3) for h in self.held_keyboard_notes)

                if is_d_held:
                    # Mute instantáneo del canal 9 para suprimir cualquier fuga del golpe de percusión
                    fluid.send("cc 9 7 0")
                    for h in list(self.held_keyboard_notes.keys()):
                        if h % 12 == 2:
                            fluid.send(f"noteoff 0 {h}")
                            self.looper.remove_recent_note(0, h, window=1.0)
                    fluid.send(f"noteoff 9 {note}")
                    self.trigger_looper_pad_press(pad_num)
                    # Restaurar volumen normal de percusión de fondo tras silenciar el golpe
                    threading.Timer(0.04, lambda: fluid.send(f"cc 9 7 {self.current_drum_volume}")).start()
                    return

                if is_ds_held:
                    fluid.send("cc 9 7 0")
                    for h in list(self.held_keyboard_notes.keys()):
                        if h % 12 == 3:
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

    def handle_note_off(self, note: int, channel: int):
        if channel == 0:
            self.held_keyboard_notes.pop(note, None)
            self.cancel_shutdown_timer()
            # Grabar liberación de tecla para mantener duración exacta de notas
            if self.looper.state in ["RECORDING", "OVERDUBBING"]:
                self.looper.record_event(0, note, 0, False)
        elif channel == 9:
            pad_num = (note - 36) % 8 if note < 44 else (note - 44) % 8
            # Si se suelta un pad mientras D1 está sostenido (o estaba activo el looper):
            if self.held_keyboard_notes and any((h % 12 == 2) for h in self.held_keyboard_notes):
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

            elif knob_idx == 3:  # K4: Drum & Looper Volume Balance (Volumen Mezcla Batería)
                self.current_drum_volume = value
                fluid.send(f"cc 9 7 {value}")
                print(f"[KNOB 4 - BATERÍA] Volumen Mezcla Batería/Loop: {int((value/127)*100)}%", flush=True)

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

            elif knob_idx == 6:  # K7: Chorus Speed / Leslie Rotary Rate (Velocidad de Modulación del Teclado)
                # De 0.2 Hz (vaivén lento y espacial tipo Rhodes/Pad) a 5.0 Hz (Leslie Rotary Speaker / Trémolo rápido)
                speed = 0.2 + (value / 127.0) * 4.8
                fluid.send(f"cho_set_speed {speed:.2f}")
                print(f"[KNOB 7 - TECLADO] Modulación / Leslie Rotary Speed: {speed:.2f} Hz", flush=True)

            elif knob_idx == 7:  # K8: Master Volume (Volumen General)
                norm = value / 127.0
                gain = (norm ** 1.7) * 1.05
                fluid.send(f"gain {gain:.2f}")
                print(f"[KNOB 8 - MASTER] Volumen General: {int(norm * 100)}% (Gain {gain:.2f})", flush=True)

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
                    fluid.send(f"cc 0 64 {127 if self.sustain_active else 0}")
                    status = "ACTIVADO (Notas sostenidas libres)" if self.sustain_active else "DESACTIVADO (Notas secas)"
                    print(f"\n[PAD CC A-1] SUSTAIN PEDAL -> {status}", flush=True)
                else:
                    if (now - self.last_sustain_press) > 0.4:
                        self.sustain_active = False
                        fluid.send("cc 0 64 0")
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
                    self.current_melodic_idx = (self.current_melodic_idx - 1) % len(MELODIC_INSTRUMENTS)
                    prog_num, name = MELODIC_INSTRUMENTS[self.current_melodic_idx]
                    fluid.send(f"prog 0 {prog_num}")
                    print(f"\n[PAD CC A-6] Instrumento Anterior -> ({self.current_melodic_idx + 1}/{len(MELODIC_INSTRUMENTS)}): {name} (Prog {prog_num})", flush=True)
                    play_preview(chan=0, note=72, vel=110, duration=0.35)
            elif pad_idx == 6:  # Pad 7: Instrumento Siguiente (Teclado)
                if value > 0:
                    self.current_melodic_idx = (self.current_melodic_idx + 1) % len(MELODIC_INSTRUMENTS)
                    prog_num, name = MELODIC_INSTRUMENTS[self.current_melodic_idx]
                    fluid.send(f"prog 0 {prog_num}")
                    print(f"\n[PAD CC A-7] Instrumento Siguiente -> ({self.current_melodic_idx + 1}/{len(MELODIC_INSTRUMENTS)}): {name} (Prog {prog_num})", flush=True)
                    play_preview(chan=0, note=72, vel=110, duration=0.35)
            elif pad_idx == 7:  # Pad 8: Pánico / All Notes Off
                if value > 0:
                    fluid.send("cc 0 123 0\ncc 9 123 0\ncc 0 120 0\ncc 9 120 0\ncc 0 64 0")
                    self.looper.stop_all()
                    self.sustain_active = False
                    print("\n[PAD CC A-8] ¡PÁNICO! Silenciadas todas las notas y detenido el Looper", flush=True)

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
                print(f"[+] Conectado a {port_name}. Listo para tocar y cambiar sonidos.", flush=True)

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
                                print(f"[PROGRAM CHANGE] Canal {msg.channel + 1} -> Programa {msg.program}", flush=True)
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
