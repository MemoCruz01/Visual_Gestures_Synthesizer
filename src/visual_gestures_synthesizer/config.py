"""
Konfiguration und Konstanten für Visual Gestures Synthesizer

Enthält:
- UI-Einstellungen
- Audio-Parameter
- Hand-Tracking-Konstanten
- Spielmodi und Tonarten
"""

import os
from dataclasses import dataclass, field
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
    CAMERA_AUTO_START: bool = True  # Kamera automatisch beim Start anschalten

    # Audio
    SAMPLE_RATE: int = 44100
    CHUNK_SIZE: int = 2048
    AUDIO_ENABLED: bool = True
    MASTER_VOLUME: float = 0.2  # 20% - Lautstärke einstellen hier (0.0-1.0)

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

    # =========================================================================
    # KALIBRIERUNG: Umkreis-Erkennung für Finger Bent/Straight
    # =========================================================================
    # Diese Parameter steuern die Erkennung, ob ein Finger gestreckt oder gebeugt ist
    # Ändere diese Werte um die Erkennung anzupassen!
    
    # === INKREIS-MITTELPUNKT: Welche 3 Landmarks definieren das Inzentrum? ===
    # Der Inkreis ist der größte Kreis der INNERHALB der Hand liegt
    # Landmarks: 0=WRIST, 2=THUMB_MCP, 5=INDEX_MCP, 9=MIDDLE_MCP, 13=RING_MCP, 17=PINKY_MCP
    INCIRCLE_CENTER_LANDMARKS: List[int] = field(default_factory=lambda: [2, 5, 17])  # THUMB_MCP, INDEX_MCP, PINKY_MCP  
    
    # === INKREIS-SKALIERUNG: Wie wird der Radius skaliert? ===
    # Der berechnete Inradius wird mit diesem Faktor multipliziert
    # 1.0 = exakter Inradius (KALIBRIERUNGS-BASELINE)
    # > 1.0 = größer (toleranter, mehr INSIDE)
    # < 1.0 = kleiner (strenger, mehr OUTSIDE)
    INCIRCLE_RADIUS_SCALE: float = 1.0  # BASELINE - Langsam anpassen wenn nötig
    
    # === FINGER-SPITZEN: Welche Landmarks sind die Finger-Spitzen? ===
    # Wenn diese Landmarks außerhalb des Kreises sind → Finger gestreckt
    # Wenn innerhalb → Finger gebeugt
    FINGER_TIP_LANDMARKS: Dict[str, int] = field(default_factory=lambda: {
        'thumb': 4,      # THUMB_TIP
        'index': 8,      # INDEX_FINGER_TIP
        'middle': 12,    # MIDDLE_FINGER_TIP
        'ring': 16,      # RING_FINGER_TIP
        'pinky': 20,     # PINKY_TIP
    })
    
    # === DEBUG-VISUALISIERUNG: Zeige den Kreis auf der UI? ===
    SHOW_INCIRCLE_DEBUG: bool = True  # Kreis zeichnen bei DEBUG
    
    # === RADIUS: Distanz vom Mittelpunkt zu welchem Punkt? ===
    # Radius = Distanz vom Mittelpunkt zum Midpoint zwischen diesen 2 Landmarks
    # Landmarkpaare: [2,3]=THUMB, [6,7]=INDEX, [10,11]=MIDDLE, [14,15]=RING, [18,19]=PINKY
    RADIUS_REFERENCE_LANDMARKS: List[int] = field(default_factory=lambda: [2, 3])  # THUMB_MCP und THUMB_IP (Daumen)
    
    # === RADIUS-SKALIERUNG ===
    # Multiplikator für den berechneten Radius
    # < 1.0  = kleinerer Kreis (strikter, mehr Finger als gestreckt erkannt)
    # = 1.0  = normaler Radius (standard)
    # > 1.0  = größerer Kreis (lockerer, mehr Finger als gebeugt erkannt)
    RADIUS_MULTIPLIER: float = 1.0  # Probier: 0.85, 0.9, 1.0, 1.1, 1.2
    
    # === BENT/STRAIGHT VERGLEICH ===
    # Wenn tip_dist <= (radius * BENT_THRESHOLD_MULTIPLIER) → GEBEUGT
    # Wenn tip_dist > (radius * BENT_THRESHOLD_MULTIPLIER) → GESTRECKT
    BENT_THRESHOLD_MULTIPLIER: float = 1.0  # Probier: 0.8, 0.9, 1.0, 1.1
    
    # === STATE-MACHINE DEBOUNCING ===
    # Verhindert Flattern (mehrfaches Triggern)
    BEND_DEBOUNCE_TIME: float = 0.05  # Sekunden (50ms) - Zeit bis TRIGGERED
    RELEASE_LOCK_TIME: float = 0.1    # Sekunden (100ms) - Sperre nach Release
    
    # =========================================================================
    # DEBUG: Visualisierung
    # =========================================================================
    SHOW_DETECTION_CIRCLE: bool = True  # Zeige Umkreis auf Frame
    SHOW_INTERACTIVE_DEBUG: bool = True  # Zeige Debug-Info für Positionen
    SHOW_FINGER_STATES: bool = True     # Zeige Finger-States (READY/TRIGGERED/HELD)

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
