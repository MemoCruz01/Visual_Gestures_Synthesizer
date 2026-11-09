"""
Application Controller - Zentrale Geschäftslogik

Verantwortlich für:
- Spielmodi (CHORDS, INTERACTIVE, AIR_PIANO, GESTURES)
- Tonart-Verwaltung
- Finger-zu-Akkord-Mapping
- Orchestrierung von Finger-States → Audio-Output
"""

import logging
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .finger_detection import FingerState
from .music_theory import MusicTheory
from .audio import get_audio_player
from .config import config

logger = logging.getLogger(__name__)


# ============================================================================
# Spielmodi
# ============================================================================

class GameMode(Enum):
    """Verfügbare Spielmodi"""
    CHORDS = "chords"              # Finger = Akkord-Stufe (diatonisch)
    INTERACTIVE = "interactive"    # Linke Hand = Akkord, Rechte Hand = Effekte
    AIR_PIANO = "air_piano"       # Horizontale Position = Taste, Anschlag
    GESTURES = "gestures"         # Ganz-Hand-Posen für Akkorde


# ============================================================================
# Tonarten
# ============================================================================

ALL_ROOT_NOTES = [
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"
]


# ============================================================================
# Finger-zu-Akkord-Mapping (Start: C-Dur)
# ============================================================================

DEFAULT_FINGER_MAPPING = {
    "left": {
        "thumb": -1,      # Nicht für Akkorde verwendet
        "index": 0,       # I (Tonika)
        "middle": 3,      # IV (Subdominante)
        "ring": 4,        # V (Dominante) - alternativ
        "pinky": 5,       # vi (Moll-Relative)
    },
    "right": {
        "thumb": -1,
        "index": 4,       # V (Dominante)
        "middle": 5,      # vi (Moll-Relative)
        "ring": 2,        # iii (Moll-Mediante)
        "pinky": 1,       # ii (Subdominante-Parallel)
    }
}


# ============================================================================
# GameState - Zentrale Verwaltung aller Spielzustände
# ============================================================================

class GameState:
    """
    Verwaltet den gesamten Spielzustand und Logik.
    Wird von UI und Camera angesprochen.
    """

    def __init__(self):
        """Initialisiere GameState mit Defaults"""
        self.mode: GameMode = GameMode.INTERACTIVE  # DEFAULT: Interactive Mode
        self.root_note: str = "C"
        self.scale_type: str = "major"  # "major" oder "minor"
        
        # MusicTheory erwartet MIDI-Noten, nicht Note-Namen
        self.music_theory = MusicTheory()
        self._set_music_theory_root_note(self.root_note)
        
        self.audio_player = get_audio_player()
        
        # Kopiere Standard-Mapping
        self.finger_mapping: Dict = self._get_default_mapping()
        
        # Aktive Noten pro Hand
        self.active_chords: Dict[str, List[int]] = {
            "left": [],
            "right": []
        }
        
        # Interactive Mode: Tracking der erkannten Positionen
        self.interactive_last_position: Dict[str, Optional[int]] = {
            "left": None,
            "right": None
        }
        self.interactive_position_stable_time: Dict[str, float] = {
            "left": 0.0,
            "right": 0.0
        }
        
        # Debugging
        self.last_triggered: Dict[str, str] = {}  # {"left": "index", ...}
        
        logger.info(f"GameState initialisiert: {self.mode.value}, {self.root_note}")

    def set_mode(self, mode: GameMode) -> None:
        """
        Wechsle Spielmodus
        
        Args:
            mode: Neuer GameMode
        """
        if self.mode == mode:
            return
        
        logger.info(f"Modus gewechselt: {self.mode.value} → {mode.value}")
        self.mode = mode
        self.stop_all_notes()

    def set_root_note(self, note: str) -> None:
        """
        Wechsle Tonart/Grundton
        
        Args:
            note: Grundton (z.B. "C", "G", "D#")
        """
        if note not in ALL_ROOT_NOTES:
            logger.warning(f"Ungültiger Ton: {note}")
            return
        
        if self.root_note == note:
            return
        
        logger.info(f"Tonart gewechselt: {self.root_note} → {note}")
        self.root_note = note
        self._set_music_theory_root_note(note)
        self.stop_all_notes()

    def _set_music_theory_root_note(self, note_name: str) -> None:
        """
        Hilfsfunktion: Konvertiere Note-Name zu MIDI und setze in MusicTheory
        
        Args:
            note_name: Note-Name (z.B. "C", "G", "D#")
        """
        # Konvertiere Note-Name zu MIDI (C4 = 60)
        midi_note = self._note_name_to_midi(note_name)
        self.music_theory.set_root_note(midi_note)

    def process_hand_state(self, hand_side: str, hand_state: dict) -> None:
        """
        Verarbeite Finger-States und generiere Audio-Output
        
        Args:
            hand_side: "left" oder "right"
            hand_state: Dict mit:
                - 'triggered_fingers': List[str] (gerade aktivierte Finger)
                - 'held_fingers': List[str] (gehaltene Finger)
                - 'states': Dict[str, str] (Finger → FingerState: "READY", "TRIGGERED", "HELD", "RELEASING")
        """
        if hand_side not in ["left", "right"]:
            return
        
        triggered = hand_state.get("triggered_fingers", [])
        held = hand_state.get("held_fingers", [])
        finger_states = hand_state.get("states", {})
        
        # Debug-Info speichern
        if triggered:
            self.last_triggered[hand_side] = triggered[0]
        
        # Dispatch zu Modus-spezifischer Logik
        if self.mode == GameMode.CHORDS:
            self._process_chords_mode(hand_side, triggered, held)
        elif self.mode == GameMode.INTERACTIVE:
            self._process_interactive_mode(hand_side, finger_states)
        elif self.mode == GameMode.AIR_PIANO:
            self._process_air_piano_mode(hand_side, triggered, held)
        elif self.mode == GameMode.GESTURES:
            self._process_gestures_mode(hand_side, triggered, held)

    def _process_chords_mode(
        self,
        hand_side: str,
        triggered: List[str],
        held: List[str]
    ) -> None:
        """
        CHORDS Mode: Jeder Finger spielt diatonischen Akkord
        
        Nur bei TRIGGERED: Akkord spielen
        Bei HELD: Akkord halten (nicht wiederholen)
        """
        if not triggered:
            return
        
        # Nur den ersten triggerten Finger verarbeiten
        finger = triggered[0]
        
        # Nachschlag: Finger → Stufe
        degree = self.finger_mapping[hand_side].get(finger, -1)
        
        if degree < 0 or degree >= 7:
            logger.debug(f"Finger {finger} nicht gemappt oder ungültige Stufe {degree}")
            return
        
        # Nachschlag: Stufe (0-6) → Akkord
        # get_diatonic_chord erwartet Grad 1-7, also +1
        midi_chord = self.music_theory.get_diatonic_chord(degree + 1, num_notes=3)
        
        logger.debug(f"CHORDS: {hand_side}.{finger} → Stufe {degree} (Grad {degree+1}) → MIDI {midi_chord}")
        
        # Stoppe alte Akkorde dieser Hand und starte Neuen
        self.active_chords[hand_side] = midi_chord
        self.audio_player.stop_all()
        self.audio_player.play_chord(midi_chord)

    def _process_interactive_mode(
        self,
        hand_side: str,
        finger_states: Dict[str, str]
    ) -> None:
        """
        INTERACTIVE Mode: Linke Hand steuert 7 Positionen → 7 Akkord-Grade
        
        Die 7 Positionen sind eindeutig durch Finger-Kombinationen definiert:
        1. Nur Index gestreckt → Grad I
        2. Index + Middle gestreckt → Grad II
        3. Index + Middle + Ring gestreckt → Grad III
        4. Index + Middle + Ring + Pinky gestreckt → Grad IV
        5. Alle 5 Finger gestreckt → Grad V
        6. Index + Pinky gestreckt → Grad VI
        7. Index + Pinky + Thumb gestreckt → Grad VII
        
        Args:
            hand_side: "left" oder "right"
            finger_states: Dict[str, str] (Finger → State: "READY", "TRIGGERED", "HELD", "RELEASING")
        """
        # Nur linke Hand verarbeiten
        if hand_side != "left":
            return
        
        # Erkenne aktuelle Position
        detected_position = self._detect_interactive_position(finger_states)
        
        if detected_position is None:
            # Keine gültige Position erkannt
            if self.interactive_last_position[hand_side] is not None:
                # Position verloren → Stoppe Akkord
                logger.debug(f"INTERACTIVE: Position verloren (war {self.interactive_last_position[hand_side]})")
                self.active_chords[hand_side] = []
                self.audio_player.stop_all()
            self.interactive_last_position[hand_side] = None
            return
        
        # Position stabil? Nur bei Wechsel spielen
        if detected_position != self.interactive_last_position[hand_side]:
            logger.info(f"INTERACTIVE: Position {detected_position} erkannt → Grad {detected_position}")
            
            # Position → Grad (1-7)
            degree = detected_position - 1  # Position 1 → Degree 0 (API nutzt 1-7)
            
            # Grad → Akkord (diatonisch)
            midi_chord = self.music_theory.get_diatonic_chord(detected_position, num_notes=3)
            
            # Stoppe alten Akkord und starte Neuen
            self.audio_player.stop_all()
            self.active_chords[hand_side] = midi_chord
            self.audio_player.play_chord(midi_chord)
            
            # Update: Neue Position aktiv
            self.interactive_last_position[hand_side] = detected_position

    @staticmethod
    def _detect_interactive_position(finger_states: Dict[str, str]) -> Optional[int]:
        """
        Erkenne die 7 Positionen basierend auf Finger-States
        
        Gestreckt = "READY" oder "RELEASING" (Finger ist NOT bent)
        Gebeugt = "TRIGGERED" oder "HELD" (Finger is bent)
        
        Args:
            finger_states: Dict[str, str] (thumb, index, middle, ring, pinky → State)
        
        Returns:
            Position (1-7) oder None wenn ungültig
        """
        # Finger → Is Straight? (READY/RELEASING = straight, TRIGGERED/HELD = bent)
        def is_straight(state: str) -> bool:
            return state in ["READY", "RELEASING"]
        
        idx = is_straight(finger_states.get("index", "READY"))
        mid = is_straight(finger_states.get("middle", "READY"))
        rng = is_straight(finger_states.get("ring", "READY"))
        pky = is_straight(finger_states.get("pinky", "READY"))
        thm = is_straight(finger_states.get("thumb", "READY"))
        
        # Position-Logik (teste spezifische von allgemein)
        
        # Position 5: Alle 5 Finger gestreckt
        if idx and mid and rng and pky and thm:
            return 5
        
        # Position 7: Index + Pinky + Thumb gestreckt (keine anderen)
        if idx and pky and thm and not mid and not rng:
            return 7
        
        # Position 6: Index + Pinky gestreckt (Thumb egal)
        if idx and pky and not mid and not rng:
            return 6
        
        # Position 4: Index + Middle + Ring + Pinky gestreckt (Thumb bent)
        if idx and mid and rng and pky and not thm:
            return 4
        
        # Position 3: Index + Middle + Ring gestreckt, Pinky gebeugt
        if idx and mid and rng and not pky:
            return 3
        
        # Position 2: Index + Middle gestreckt, Rest gebeugt
        if idx and mid and not rng and not pky:
            return 2
        
        # Position 1: Nur Index gestreckt
        if idx and not mid and not rng and not pky:
            return 1
        
        # Keine gültige Position
        return None
    
    

    def _process_air_piano_mode(
        self,
        hand_side: str,
        triggered: List[str],
        held: List[str]
    ) -> None:
        """
        AIR_PIANO Mode: Wird später implementiert
        Horizontale Position = Klaviertaste
        Vertikale Position = Anschlagdruck
        """
        logger.debug(f"AIR_PIANO mode (TODO): {hand_side} triggered={triggered}")

    def _process_gestures_mode(
        self,
        hand_side: str,
        triggered: List[str],
        held: List[str]
    ) -> None:
        """
        GESTURES Mode: Wird später implementiert
        Ganz-Hand-Posen für schnelle Akkordwechsel
        """
        logger.debug(f"GESTURES mode (TODO): {hand_side} triggered={triggered}")

    def stop_all_notes(self) -> None:
        """Stoppe alle aktiven Noten/Akkorde"""
        self.audio_player.stop_all()
        self.active_chords["left"] = []
        self.active_chords["right"] = []
        logger.debug("Alle Noten gestoppt")

    def _get_default_mapping(self) -> Dict:
        """Gebe Standard-Fingerbelegung zurück"""
        return DEFAULT_FINGER_MAPPING.copy()

    @staticmethod
    def _note_name_to_midi(note_name: str) -> int:
        """
        Konvertiere Note-Name zu MIDI-Nummer
        
        Args:
            note_name: Note-Name (z.B. "C", "D#", "Bb")
        
        Returns:
            MIDI-Notennummer (0-127), C4 = 60
        """
        note_map = {
            "C": 0, "C#": 1, "Db": 1,
            "D": 2, "D#": 3, "Eb": 3,
            "E": 4, "Fb": 4,
            "F": 5, "F#": 6, "Gb": 6,
            "G": 7, "G#": 8, "Ab": 8,
            "A": 9, "A#": 10, "Bb": 10,
            "B": 11, "Cb": 11,
        }
        
        note_base = note_map.get(note_name, 0)
        # Standard: C4 = 60, also C = Oktave 4
        octave = 4
        return (octave + 1) * 12 + note_base

    def get_status(self) -> Dict:
        """Gebe Status-Info für Debug-Display zurück"""
        return {
            "mode": self.mode.value,
            "root_note": self.root_note,
            "last_triggered": self.last_triggered,
            "active_chords": self.active_chords,
            "interactive_position": self.interactive_last_position.get("left"),
        }


# ============================================================================
# Globale Instanz (Singleton-Pattern)
# ============================================================================

_game_state: Optional[GameState] = None


def get_game_state() -> GameState:
    """Erhalte die globale GameState-Instanz"""
    global _game_state
    if _game_state is None:
        _game_state = GameState()
    return _game_state


def init_game_state() -> GameState:
    """Initialisiere GameState (wird von main.py aufgerufen)"""
    global _game_state
    _game_state = GameState()
    return _game_state
