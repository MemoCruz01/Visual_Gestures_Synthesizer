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
            "right": None,
            "right_last_degree": None  # Speichert den zuletzt gespielten Grad
        }
        self.interactive_position_stable_time: Dict[str, float] = {
            "left": 0.0,
            "right": 0.0
        }
        
        # Interactive Mode: State des rechten Zeigeringers
        # Wird verwendet um zu erkennen WANN der Finger gestreckt/gebeugt WIRD (Übergänge)
        self.interactive_right_index_was_straight: bool = False
        
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
        INTERACTIVE Mode: Getrennte Kontrolle für beide Hände
        
        LINKE HAND: Bestimmt den Akkord (7 Positionen = 7 Akkord-Grade)
        - Position 1: Nur Index → Grad I
        - Position 2: Index + Middle → Grad II
        - Position 3: Index + Middle + Ring → Grad III
        - Position 4: 4 Finger (ohne Pinky) → Grad IV
        - Position 5: Alle 5 Finger → Grad V (z.B. G-Dur in C-Dur)
        - Position 6: Index + Pinky → Grad VI
        - Position 7: Index + Pinky + Thumb → Grad VII
        
        RECHTE HAND: Steuert wann der Akkord gespielt wird
        - Zeigefinger GESTRECKT → Akkord an (basierend auf linker Hand Grad)
        - Zeigefinger GEBEUGT → Akkord aus
        
        Args:
            hand_side: "left" oder "right"
            finger_states: Dict[str, str] (Finger → State: "READY", "TRIGGERED", "HELD", "RELEASING")
        """
        if hand_side == "left":
            # ===================================================================
            # LINKE HAND: Erkenne Position und speichere Akkord-Grad
            # ===================================================================
            position = self._detect_interactive_position(finger_states)
            
            if position is not None:
                # Position erkannt und ist neu/unterschiedlich → speichere
                if self.interactive_last_position["left"] != position:
                    self.interactive_last_position["left"] = position
                    logger.info(
                        f"INTERACTIVE: Linke Hand Position {position} erkannt "
                        f"→ Grad {position} (Akkord-Auswahl)"
                    )
                    
                    # Wenn gerade ein Akkord gespielt wird, stoppe ihn kurz
                    # damit der neue Akkord deutlich wahrgenommen wird
                    if self.active_chords.get("right"):
                        self.audio_player.stop_all()
                        # Wenn rechter Zeigefinger noch gestreckt ist,
                        # spiele den neuen Akkord sofort
                        # (wird in der nächsten _process_interactive_mode(right) Aufrufe erledigt)
        
        elif hand_side == "right":
            # ===================================================================
            # RECHTE HAND: MASTER VOLUME SCHALTER für Akkord
            # Der Akkord spielt solange der Zeigefinger gestreckt ist!
            # ===================================================================
            index_state = finger_states.get("index", "READY")
            is_index_straight = index_state in ["READY", "RELEASING"]
            
            # Verwende den Grad der linken Hand (Default: Grad I wenn nichts definiert)
            degree = self.interactive_last_position.get("left") or 1
            
            # Erkenne Übergänge: gestreckt → gebeugt oder gebeugt → gestreckt
            if is_index_straight and not self.interactive_right_index_was_straight:
                # ÜBERGANG: Finger wurde GERADE GESTRECKT
                # → Starte Akkord (kontinuierlich bis Beugung)
                logger.info(
                    f"INTERACTIVE: Rechter Zeigefinger GESTRECKT (START) "
                    f"→ Spiele Grad {degree} Akkord kontinuierlich"
                )
                
                midi_chord = self.music_theory.get_diatonic_chord(degree, num_notes=3)
                self.active_chords["right"] = midi_chord
                self.audio_player.play_chord_continuous(midi_chord)
                
            elif not is_index_straight and self.interactive_right_index_was_straight:
                # ÜBERGANG: Finger wurde GERADE GEBEUGT
                # → Stoppe Akkord sofort (Master Volume OFF)
                logger.info(
                    f"INTERACTIVE: Rechter Zeigefinger GEBEUGT (STOP) → Akkord stoppen"
                )
                self.active_chords["right"] = []
                self.audio_player.stop_all()
            
            elif is_index_straight and self.interactive_right_index_was_straight:
                # Finger bleibt GESTRECKT: Prüfe ob linke Hand Position geändert hat
                current_left_degree = self.interactive_last_position.get("left") or 1
                last_played_degree = self.interactive_last_position.get("right_last_degree")
                
                if current_left_degree != last_played_degree:
                    # Akkord-Grad hat sich geändert während Finger gestreckt war
                    # → Spiele neuen Akkord kontinuierlich
                    logger.info(
                        f"INTERACTIVE: Position-Wechsel zu Grad {current_left_degree} "
                        f"→ Neuer Akkord kontinuierlich"
                    )
                    midi_chord = self.music_theory.get_diatonic_chord(
                        current_left_degree, num_notes=3
                    )
                    self.active_chords["right"] = midi_chord
                    self.audio_player.play_chord_continuous(midi_chord)
                    self.interactive_last_position["right_last_degree"] = current_left_degree
            
            # Speichere aktuellen Zustand für nächste Iteration
            self.interactive_right_index_was_straight = is_index_straight
    
    # =========================================================================
    # ZUKÜNFTIG: 7-Positionen Logik (Für erweiterte Interactive Mode Versionen)
    # =========================================================================
    # @staticmethod
    # def _detect_interactive_position_advanced(finger_states: Dict[str, str]) -> Optional[int]:
    #     """
    #     ZUKÜNFTIG: Erkenne 7 Positionen für erweiterte Interactive Mode
    #     
    #     Position 1: Nur Index gestreckt → Grad I
    #     Position 2: Index + Middle gestreckt → Grad II
    #     Position 3: Index + Middle + Ring gestreckt → Grad III
    #     Position 4: Index + Middle + Ring + Pinky gestreckt → Grad IV
    #     Position 5: Alle 5 Finger gestreckt → Grad V
    #     Position 6: Index + Pinky gestreckt → Grad VI
    #     Position 7: Index + Pinky + Thumb gestreckt → Grad VII
    #     """
    #     pass
    
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
