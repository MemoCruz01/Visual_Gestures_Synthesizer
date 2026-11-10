"""
Audio Synthesizer & Player - Lokale Audio-Synthese und PyAudio Ausgabe

Verantwortlich für:
- Sinus-Wellen-Synthese (Einzeltöne und Akkorde)
- PyAudio Stream Verwaltung
- Thread-sichere Audio-Queue
- Fade-In/Out (gegen Knackgeräusche)
- Lautstärke-Kontrolle
"""

import numpy as np
import pyaudio
import threading
import queue
import logging
import time
from typing import List, Optional
from dataclasses import dataclass
from .config import config

logger = logging.getLogger(__name__)

# Audio Settings
SAMPLE_RATE = 44100  # 44.1 kHz
CHANNELS = 2  # Stereo
SAMPLE_WIDTH = 2  # 16-bit = 2 bytes
CHUNK_SIZE = 4410  # ~100ms bei 44.1kHz


@dataclass
class AudioCommand:
    """Command für Audio-Queue"""
    command_type: str  # "play_tone", "play_chord", "stop", "set_volume"
    midi_notes: Optional[List[int]] = None  # Für play_tone/play_chord
    duration: Optional[float] = None  # Für Akkorde (in Sekunden)
    volume: Optional[float] = None  # Für set_volume


class Synthesizer:
    """Sinus-Wellen Synthesizer für Musiknoten"""

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        """
        Args:
            sample_rate: Sample-Rate in Hz (default 44.1kHz)
        """
        self.sample_rate = sample_rate
        self.a4_frequency = 440.0  # Standard: A4 = 440 Hz

    def midi_to_frequency(self, midi_note: int) -> float:
        """
        Konvertiere MIDI-Note zu Frequenz (Hz)

        MIDI Standard: Note 69 = A4 = 440 Hz
        Formel: f = 440 * 2^((midi_note - 69) / 12)

        Args:
            midi_note: MIDI-Notennummer (0-127, wobei 60 = C4)

        Returns:
            Frequenz in Hz
        """
        return self.a4_frequency * (2.0 ** ((midi_note - 69) / 12.0))

    def generate_sine_wave(
        self,
        frequency: float,
        duration: float,
        sample_rate: int = None,
        volume: float = 1.0,
    ) -> np.ndarray:
        """
        Generiere Sinus-Welle für eine bestimmte Frequenz und Dauer

        Args:
            frequency: Frequenz in Hz
            duration: Dauer in Sekunden
            sample_rate: Samples pro Sekunde (default: self.sample_rate)
            volume: Lautstärke (0.0-1.0)

        Returns:
            numpy array mit Audio-Samples (16-bit int)
        """
        if sample_rate is None:
            sample_rate = self.sample_rate

        num_samples = int(sample_rate * duration)
        t = np.linspace(0, duration, num_samples, False)

        # Generiere Sinus-Welle
        wave = np.sin(2 * np.pi * frequency * t) * volume

        # Fade-In/Out (10ms each) gegen Knackgeräusche
        fade_samples = int(sample_rate * 0.01)
        if fade_samples < num_samples:
            # Fade-In
            wave[:fade_samples] *= np.linspace(0, 1, fade_samples)
            # Fade-Out
            wave[-fade_samples:] *= np.linspace(1, 0, fade_samples)

        # Konvertiere zu 16-bit PCM
        wave = np.clip(wave * 32767, -32768, 32767).astype(np.int16)
        return wave

    def generate_tone(
        self,
        midi_note: int,
        duration: float,
        sample_rate: int = None,
        volume: float = 1.0,
    ) -> np.ndarray:
        """
        Generiere einen Einzelton (MIDI-Note)

        Args:
            midi_note: MIDI-Notennummer (0-127)
            duration: Dauer in Sekunden
            sample_rate: Samples pro Sekunde
            volume: Lautstärke (0.0-1.0)

        Returns:
            numpy array mit Audio-Samples (16-bit int)
        """
        frequency = self.midi_to_frequency(midi_note)
        return self.generate_sine_wave(frequency, duration, sample_rate, volume)

    def generate_chord(
        self,
        midi_notes: List[int],
        duration: float,
        sample_rate: int = None,
        volume: float = 1.0,
    ) -> np.ndarray:
        """
        Generiere einen Akkord (mehrere MIDI-Noten gemischt)

        Args:
            midi_notes: Liste von MIDI-Notennummern
            duration: Dauer in Sekunden
            sample_rate: Samples pro Sekunde
            volume: Lautstärke (0.0-1.0, wird auf Anzahl Noten normalisiert)

        Returns:
            numpy array mit Audio-Samples (16-bit int)
        """
        if sample_rate is None:
            sample_rate = self.sample_rate

        if not midi_notes:
            return np.zeros(int(sample_rate * duration), dtype=np.int16)

        num_samples = int(sample_rate * duration)
        combined_wave = np.zeros(num_samples)

        # Normalisiere Lautstärke auf Anzahl Noten
        note_volume = volume / len(midi_notes)

        # Addiere Sinus-Wellen für jeden Note
        for midi_note in midi_notes:
            frequency = self.midi_to_frequency(midi_note)
            t = np.linspace(0, duration, num_samples, False)
            wave = np.sin(2 * np.pi * frequency * t) * note_volume
            combined_wave += wave

        # Fade-In/Out
        fade_samples = int(sample_rate * 0.01)
        if fade_samples < num_samples:
            combined_wave[:fade_samples] *= np.linspace(0, 1, fade_samples)
            combined_wave[-fade_samples:] *= np.linspace(1, 0, fade_samples)

        # Konvertiere zu 16-bit PCM
        combined_wave = np.clip(combined_wave * 32767, -32768, 32767).astype(
            np.int16
        )
        return combined_wave


class AudioPlayer:
    """PyAudio Player mit Queue-basierter Steuerung"""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        chunk_size: int = CHUNK_SIZE,
    ):
        """
        Args:
            sample_rate: Sample-Rate in Hz
            channels: Anzahl Kanäle (2 = Stereo)
            chunk_size: Größe der Audio-Chunks
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size

        self.synthesizer = Synthesizer(sample_rate)
        self.is_running = False
        self.thread = None

        # Command Queue
        self.command_queue = queue.Queue()

        # Audio State
        self.current_audio_buffer = None
        self.current_position = 0
        self.master_volume = config.MASTER_VOLUME  # Initialisiere mit Config-Wert
        self.playing = False

        # PyAudio Stream
        self.pa = None
        self.stream = None

        logger.info(
            f"AudioPlayer initialisiert ({sample_rate}Hz, {channels} channels, "
            f"Master Volume: {self.master_volume:.2f})"
        )

    def initialize(self) -> bool:
        """Initialisiere PyAudio Stream"""
        try:
            self.pa = pyaudio.PyAudio()

            self.stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=self.chunk_size,
            )

            logger.info("PyAudio Stream geöffnet")
            return True

        except Exception as e:
            logger.error(f"Fehler beim Öffnen des Audio-Streams: {e}")
            return False

    def start(self) -> None:
        """Starten Sie Audio-Player in separatem Thread"""
        if self.is_running:
            logger.warning("AudioPlayer läuft bereits")
            return

        if not self.stream:
            if not self.initialize():
                logger.error("Audio-Stream konnte nicht initialisiert werden")
                return

        self.is_running = True
        self.thread = threading.Thread(target=self._audio_loop, daemon=True)
        self.thread.start()
        logger.info("AudioPlayer gestartet")

    def stop(self) -> None:
        """Stoppe Audio-Player"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        self.playing = False
        logger.info("AudioPlayer gestoppt")

    def play_tone(self, midi_note: int, duration: float = 0.5) -> None:
        """
        Spiele einen Einzelton

        Args:
            midi_note: MIDI-Notennummer (0-127)
            duration: Dauer in Sekunden
        """
        cmd = AudioCommand(
            command_type="play_tone",
            midi_notes=[midi_note],
            duration=duration,
        )
        self.command_queue.put(cmd)

    def play_chord(self, midi_notes: List[int], duration: float = 2.0) -> None:
        """
        Spiele einen Akkord

        Args:
            midi_notes: Liste von MIDI-Noten
            duration: Dauer in Sekunden
        """
        cmd = AudioCommand(
            command_type="play_chord",
            midi_notes=midi_notes,
            duration=duration,
        )
        self.command_queue.put(cmd)

    def play_chord_continuous(self, midi_notes: List[int]) -> None:
        """
        Spiele einen Akkord kontinuierlich bis stop_all() aufgerufen wird
        
        Ideal für Interactive Mode: Akkord spielt solange rechter Zeigefinger gestreckt ist
        
        Args:
            midi_notes: Liste von MIDI-Noten
        """
        # Spiele mit sehr langer Duration (60 Sekunden)
        # wird gestoppt durch stop_all() wenn Zeigefinger gebeugt wird
        cmd = AudioCommand(
            command_type="play_chord",
            midi_notes=midi_notes,
            duration=60.0,  # 60 Sekunden - wird von stop_all() unterbrochen
        )
        self.command_queue.put(cmd)

    def stop_all(self) -> None:
        """Stoppe alle spielenden Noten sofort"""
        cmd = AudioCommand(command_type="stop")
        self.command_queue.put(cmd)

    def set_volume(self, volume: float) -> None:
        """
        Setze Master-Lautstärke

        Args:
            volume: Lautstärke (0.0-1.0)
        """
        volume = np.clip(volume, 0.0, 1.0)
        cmd = AudioCommand(command_type="set_volume", volume=volume)
        self.command_queue.put(cmd)

    def _audio_loop(self) -> None:
        """Main Audio-Loop (läuft in separatem Thread)"""
        try:
            while self.is_running:
                # Verarbeite Commands
                try:
                    cmd = self.command_queue.get_nowait()
                    self._handle_command(cmd)
                except queue.Empty:
                    pass

                # Schreibe Audio-Daten
                if self.playing and self.current_audio_buffer is not None:
                    chunk = self._get_next_chunk()
                    if chunk is not None:
                        self.stream.write(chunk.tobytes())
                else:
                    # Spielen Stille wenn nicht aktiv
                    silence = np.zeros(self.chunk_size * self.channels, dtype=np.int16)
                    self.stream.write(silence.tobytes())

                time.sleep(0.001)  # Kleine Verzögerung

        except Exception as e:
            logger.error(f"Fehler in Audio-Loop: {e}")

    def _handle_command(self, cmd: AudioCommand) -> None:
        """Verarbeite Audio-Commands"""
        try:
            if cmd.command_type == "play_tone" and cmd.midi_notes:
                # Generiere Sinus-Welle
                self.current_audio_buffer = self.synthesizer.generate_tone(
                    cmd.midi_notes[0],
                    cmd.duration or 0.5,
                    volume=self.master_volume,
                )
                self.current_position = 0
                self.playing = True
                logger.debug(
                    f"Spiele Ton: MIDI {cmd.midi_notes[0]}, Duration {cmd.duration}s"
                )

            elif cmd.command_type == "play_chord" and cmd.midi_notes:
                # Generiere Akkord
                self.current_audio_buffer = self.synthesizer.generate_chord(
                    cmd.midi_notes,
                    cmd.duration or 2.0,
                    volume=self.master_volume,
                )
                self.current_position = 0
                self.playing = True
                logger.debug(
                    f"Spiele Akkord: {cmd.midi_notes}, Duration {cmd.duration}s"
                )

            elif cmd.command_type == "stop":
                self.playing = False
                self.current_audio_buffer = None
                self.current_position = 0
                logger.debug("Audio gestoppt")

            elif cmd.command_type == "set_volume":
                if cmd.volume is not None:
                    self.master_volume = cmd.volume
                    logger.debug(f"Lautstärke: {cmd.volume:.2f}")

        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten von Command: {e}")

    def _get_next_chunk(self) -> Optional[np.ndarray]:
        """Gebe nächsten Audio-Chunk zurück"""
        if self.current_audio_buffer is None:
            return None

        end_pos = self.current_position + self.chunk_size * self.channels
        chunk = self.current_audio_buffer[
            self.current_position : end_pos
        ].copy()

        # Ergänze mit Stille wenn nötig
        if len(chunk) < self.chunk_size * self.channels:
            silence = np.zeros(
                self.chunk_size * self.channels - len(chunk), dtype=np.int16
            )
            chunk = np.concatenate([chunk, silence])
            self.playing = False  # Ende erreicht
            self.current_audio_buffer = None

        self.current_position = end_pos
        return chunk

    def _cleanup(self) -> None:
        """Cleanup Audio-Ressourcen"""
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
                logger.info("Audio-Stream geschlossen")

            if self.pa:
                self.pa.terminate()
                self.pa = None
                logger.info("PyAudio beendet")

        except Exception as e:
            logger.error(f"Fehler beim Cleanup: {e}")

    def __del__(self):
        """Destruktor - Cleanup beim Beenden"""
        if self.is_running:
            self.stop()
        self._cleanup()


# Globale Audio-Player Instanz (wird in UI verwendet)
_audio_player: Optional[AudioPlayer] = None


def get_audio_player() -> AudioPlayer:
    """Gebe globale AudioPlayer Instanz zurück (Singleton)"""
    global _audio_player
    if _audio_player is None:
        _audio_player = AudioPlayer()
    return _audio_player


def init_audio() -> bool:
    """Initialisiere globale AudioPlayer Instanz"""
    player = get_audio_player()
    if not player.stream:
        return player.initialize()
    return True
