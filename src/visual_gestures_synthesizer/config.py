"""
Konfiguration und Konstanten für Visual Gestures Synthesizer

Enthält:
- UI-Einstellungen
- Audio-Parameter
- Hand-Tracking-Konstanten
- Spielmodi und Tonarten
"""

import os
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Config:
    """Zentrale Konfiguration für die App"""

    # Window
    WINDOW_WIDTH: int = 1280
    WINDOW_HEIGHT: int = 720
    WINDOW_TITLE: str = "Visual Gestures Synthesizer 🎵🤚"
    FPS: int = 30

    # Camera
    CAMERA_ID: int = 0  # Default Webcam
    CAMERA_MIRROR: bool = True  # Horizontal flip
    FRAME_SKIP: int = 1  # Process every N frames

    # Audio
    SAMPLE_RATE: int = 44100
    CHUNK_SIZE: int = 2048
    AUDIO_ENABLED: bool = True
    MASTER_VOLUME: float = 0.7

    # Hand Tracking (MediaPipe)
    MIN_CONFIDENCE: float = 0.5
    TRACKING_SMOOTHING: float = 0.7  # Low-pass filter alpha
    MAX_HANDS: int = 2

    # Finger Detection
    FINGER_BEND_THRESHOLD: float = 0.6  # Beugungsgrad zum Auslösen
    FINGER_HYSTERESIS: float = 0.1  # Unterschied Auslösen/Reset

    # Spielmodi
    DEFAULT_KEY: str = "C"  # Tonika
    DEFAULT_MODE: str = "scale_chords"  # scale_chords, piano, gesture
    SCALE_TYPE: str = "major"  # major, minor

    # Finger Mapping (für Scale Chords in C-Dur)
    # Roman numerals: I, ii, iii, IV, V, vi, vii°
    DEFAULT_FINGER_MAP: Dict[str, int] = None

    # Paths
    PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    MODELS_DIR: str = os.path.join(PROJECT_ROOT, "models")
    LOGS_DIR: str = os.path.join(PROJECT_ROOT, "logs")

    def __post_init__(self):
        """Setup nach Initialisierung"""
        if self.DEFAULT_FINGER_MAP is None:
            self.DEFAULT_FINGER_MAP = {
                "left_index": 0,     # I (Tonika)
                "left_middle": 3,    # IV (Subdominante)
                "right_index": 4,    # V (Dominante)
                "right_middle": 5,   # vi (Relative Moll)
                "left_ring": 2,      # iii
                "left_pinky": 6,     # vii°
                "right_ring": 1,     # ii
                "right_pinky": 0,    # I (Octave)
            }

        # Stelle sicher Verzeichnisse existieren
        os.makedirs(self.MODELS_DIR, exist_ok=True)
        os.makedirs(self.LOGS_DIR, exist_ok=True)

    def get_window_size(self) -> tuple:
        """Rückgabe der Fenstergröße"""
        return (self.WINDOW_WIDTH, self.WINDOW_HEIGHT)

    def get_audio_params(self) -> dict:
        """Audio-Parameter für PyAudio"""
        return {
            "sample_rate": self.SAMPLE_RATE,
            "chunk_size": self.CHUNK_SIZE,
            "channels": 1,
            "format": "float32",
        }


# Globale Config-Instanz
config = Config()
