"""
Music Theory - Tonarten, Akkorde und Notenverwaltung

Verantwortlich für:
- Tonleiter-Berechnung (Dur und Moll)
- Akkord-Berechnung (Dreiklänge)
- MIDI-Notennummern Verwaltung
- Noten-Namen (C, D, E, F, G, A, B)
"""

import logging
from typing import List, Tuple, Dict
from enum import Enum

logger = logging.getLogger(__name__)

# Noten-Basis (C4 = MIDI 60)
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
SEMITONES_PER_OCTAVE = 12


class ScaleType(Enum):
    """Skalentypen"""
    MAJOR = "major"  # Dur
    MINOR_NATURAL = "minor_natural"  # Natürlich Moll
    MINOR_HARMONIC = "minor_harmonic"  # Harmonisch Moll
    MINOR_MELODIC = "minor_melodic"  # Melodisch Moll


class MusicTheory:
    """Musik-Theorie Helfer"""

    # Dur-Tonleiter: Intervalle in Halbtönen von der Grundnote
    # W-W-H-W-W-W-H = 2-2-1-2-2-2-1
    MAJOR_INTERVALS = [0, 2, 4, 5, 7, 9, 11]

    # Natürlich Moll: 2-1-2-2-1-2-2
    MINOR_NATURAL_INTERVALS = [0, 2, 3, 5, 7, 8, 10]

    # Dreiklang-Pattern: Grundton + Terz + Quinte
    # Dur: 0 (Grundton) + 4 (Terz) + 7 (Quinte) = Dur-Akkord
    # Moll: 0 + 3 + 7 = Moll-Akkord
    TRIAD_INTERVALS = {
        "major": [0, 4, 7],  # Dur
        "minor": [0, 3, 7],  # Moll
        "diminished": [0, 3, 6],  # Vermindert
        "augmented": [0, 4, 8],  # Übermäßig
    }

    # Diatonische Dreiklänge in einer Dur-Tonleiter
    # I ii iii IV V vi vii°
    DIATONIC_MAJOR_CHORD_TYPES = [
        "major",  # I
        "minor",  # ii
        "minor",  # iii
        "major",  # IV
        "major",  # V
        "minor",  # vi
        "diminished",  # vii°
    ]

    def __init__(self):
        """Initialisiere MusicTheory"""
        self.root_note = 60  # C4 (MIDI)
        self.scale_type = ScaleType.MAJOR
        logger.info(f"MusicTheory initialisiert (Root: {self._midi_to_note_name(self.root_note)})")

    def set_root_note(self, midi_note: int) -> None:
        """
        Setze Grundnote der Tonart

        Args:
            midi_note: MIDI-Notennummer (0-127)
        """
        self.root_note = midi_note
        logger.info(f"Root-Note gesetzt: {self._midi_to_note_name(midi_note)}")

    def set_scale_type(self, scale_type: ScaleType) -> None:
        """
        Setze Skalentyp (Dur/Moll)

        Args:
            scale_type: Skalentyp (ScaleType.MAJOR oder ScaleType.MINOR_NATURAL)
        """
        self.scale_type = scale_type
        logger.info(f"Skalen-Typ gesetzt: {scale_type.value}")

    def get_scale(self, num_octaves: int = 1) -> List[int]:
        """
        Gebe Tonleiter als MIDI-Noten zurück

        Args:
            num_octaves: Anzahl Oktaven

        Returns:
            Liste von MIDI-Noten
        """
        if self.scale_type in [ScaleType.MAJOR]:
            intervals = self.MAJOR_INTERVALS
        else:
            intervals = self.MINOR_NATURAL_INTERVALS

        scale = []
        for octave in range(num_octaves):
            for interval in intervals:
                midi_note = self.root_note + interval + (octave * SEMITONES_PER_OCTAVE)
                if 0 <= midi_note <= 127:
                    scale.append(midi_note)

        return scale

    def get_diatonic_note(self, degree: int) -> int:
        """
        Gebe diatonische Note für einen Grad (1-7)

        Args:
            degree: Stufe der Tonleiter (1-7, wobei 1 = Grundnote)

        Returns:
            MIDI-Notennummer
        """
        if degree < 1 or degree > 7:
            logger.warning(f"Ungültiger Grad: {degree}, verwende 1")
            degree = 1

        if self.scale_type in [ScaleType.MAJOR]:
            intervals = self.MAJOR_INTERVALS
        else:
            intervals = self.MINOR_NATURAL_INTERVALS

        interval = intervals[degree - 1]
        return self.root_note + interval

    def get_diatonic_chord(self, degree: int, num_notes: int = 3) -> List[int]:
        """
        Gebe diatonischen Akkord für einen Grad (1-7)

        Für C-Dur:
        - Grad 1 (I): C-E-G (Dur)
        - Grad 2 (ii): D-F-A (Moll)
        - Grad 3 (iii): E-G-B (Moll)
        - usw.

        Args:
            degree: Stufe der Tonleiter (1-7)
            num_notes: Anzahl der Noten im Akkord (2 = Zweiklang, 3 = Dreiklang)

        Returns:
            Liste von MIDI-Noten
        """
        if degree < 1 or degree > 7:
            logger.warning(f"Ungültiger Grad: {degree}, verwende 1")
            degree = 1

        # Bestimme Akkordtyp (Dur/Moll/Vermindert)
        chord_type = self.DIATONIC_MAJOR_CHORD_TYPES[degree - 1]
        intervals = self.TRIAD_INTERVALS[chord_type]

        # Grundton der Akkords
        root_midi = self.get_diatonic_note(degree)

        # Baue Akkord
        chord = []
        for i in range(num_notes):
            if i < len(intervals):
                midi_note = root_midi + intervals[i]
                if 0 <= midi_note <= 127:
                    chord.append(midi_note)

        return chord

    def transpose(self, midi_note: int, semitones: int) -> int:
        """
        Transponiere Note um bestimmte Anzahl Halbtöne

        Args:
            midi_note: MIDI-Notennummer
            semitones: Anzahl Halbtöne (positiv = höher, negativ = tiefer)

        Returns:
            Neue MIDI-Notennummer
        """
        new_note = midi_note + semitones
        return np.clip(new_note, 0, 127)

    def _midi_to_note_name(self, midi_note: int) -> str:
        """
        Konvertiere MIDI-Note zu Namen

        Args:
            midi_note: MIDI-Notennummer (0-127)

        Returns:
            Note Name (z.B. "C4", "D#5")
        """
        octave = (midi_note // 12) - 1
        note_index = midi_note % 12
        return f"{NOTE_NAMES[note_index]}{octave}"

    def get_all_major_keys(self) -> Dict[str, int]:
        """
        Gebe alle 12 Dur-Tonarten mit ihren MIDI-Grundnoten

        Returns:
            Dictionary: {"C": 60, "C#": 61, ..., "B": 71}
        """
        keys = {}
        for i in range(12):
            midi_note = 60 + i  # Start von C4
            note_name = NOTE_NAMES[i]
            keys[note_name] = midi_note
        return keys


# Numpy Import (für transpose)
import numpy as np
