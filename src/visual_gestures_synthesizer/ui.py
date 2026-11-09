"""
UI Window - PySide6 GUI für Visual Gestures Synthesizer

Verantwortlich für:
- Fenster und Layout
- Live-Kamerabild-Anzeige
- Buttons und Kontrollelemente
- Status-Anzeigen
- Event-Handling
- Hand-Landmark Visualization
"""

import sys
import logging
from typing import Optional, List
import cv2
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSlider,
    QComboBox,
)
from PySide6.QtGui import QImage, QPixmap, QFont
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtWidgets import QApplication

from .config import config
from .camera import CameraHandler, MockCamera, MEDIAPIPE_AVAILABLE
from .audio import get_audio_player, init_audio
from .music_theory import MusicTheory
from .app_controller import get_game_state, init_game_state, GameMode, ALL_ROOT_NOTES

# Optional MediaPipe import für Type Hints
if MEDIAPIPE_AVAILABLE:
    from mediapipe.tasks.python import vision
else:
    vision = None

logger = logging.getLogger(__name__)


# ============================================================================
# Hand Landmark Visualization
# ============================================================================

def draw_landmarks_on_frame(frame: np.ndarray, hands_result) -> np.ndarray:
    """
    Zeichne Hand-Landmarks auf Frame
    
    Args:
        frame: OpenCV BGR image
        hands_result: MediaPipe HandLandmarkerResult oder None
    
    Returns:
        Frame mit gezeichneten Landmarks
    """
    if hands_result is None or not hasattr(hands_result, 'hand_landmarks'):
        return frame
    
    if not hands_result.hand_landmarks or len(hands_result.hand_landmarks) == 0:
        # Keine Hände erkannt - Meldung auf Frame
        cv2.putText(
            frame,
            "Keine Haende erkannt - Halte deine Haende vor die Kamera",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 165, 255),  # Orange
            2
        )
        return frame
    
    try:
        h, w = frame.shape[:2]
        
        # Hand-Landmarker: 21 Punkte pro Hand
        # 0: Handfläche, 1-4: Daumen, 5-8: Index, 9-12: Mittel, 13-16: Ring, 17-20: Klein
        HAND_CONNECTIONS = [
            # Handfläche
            (0, 1), (0, 5), (0, 17),
            # Daumen
            (1, 2), (2, 3), (3, 4),
            # Index
            (5, 6), (6, 7), (7, 8),
            # Mittel
            (9, 10), (10, 11), (11, 12),
            # Ring
            (13, 14), (14, 15), (15, 16),
            # Klein
            (17, 18), (18, 19), (19, 20),
            # Verbindungen zwischen Fingern
            (5, 9), (9, 13), (13, 17),
        ]
        
        num_hands = len(hands_result.hand_landmarks)
        
        # Debug-Info auf Frame
        cv2.putText(
            frame,
            f"Haende erkannt: {num_hands}",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 0),  # Grün
            2
        )
        
        for hand_idx, hand_landmarks in enumerate(hands_result.hand_landmarks):
            # Versuche Handedness zu bestimmen
            is_left = False
            landmark_color = (0, 255, 0)  # Standard: Grün (Rechts)
            connection_color = (0, 128, 0)
            hand_label = "Rechte Hand"
            
            # Versuche handedness zu lesen (verschiedene Formate)
            try:
                if hasattr(hands_result, 'handedness') and hands_result.handedness:
                    handedness_list = hands_result.handedness[hand_idx]
                    
                    # Prüfe ob es eine Liste oder ein Objekt ist
                    if isinstance(handedness_list, list) and len(handedness_list) > 0:
                        handedness_obj = handedness_list[0]
                        if hasattr(handedness_obj, 'category_name'):
                            is_left = handedness_obj.category_name == "Left"
                    elif hasattr(handedness_list, 'category_name'):
                        is_left = handedness_list.category_name == "Left"
                    elif hasattr(handedness_list, 'display_name'):
                        is_left = handedness_list.display_name == "Left"
            except Exception as e:
                logger.debug(f"Handedness Fehler (kein großes Problem): {e}")
            
            # Setze Farben basierend auf Hand
            if is_left:
                landmark_color = (255, 0, 0)  # Blau (Links)
                connection_color = (128, 0, 0)
                hand_label = "Linke Hand"
            
            # Zeichne Hand-Label
            cv2.putText(
                frame,
                f"{hand_label} #{hand_idx + 1}",
                (50, 80 + hand_idx * 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                landmark_color,
                2
            )
            
            # Zeichne Verbindungen in WEISS (Skelett-Struktur) ZUERST
            for start, end in HAND_CONNECTIONS:
                if start < len(hand_landmarks) and end < len(hand_landmarks):
                    start_pos = hand_landmarks[start]
                    end_pos = hand_landmarks[end]
                    
                    x1 = int(start_pos.x * w)
                    y1 = int(start_pos.y * h)
                    x2 = int(end_pos.x * w)
                    y2 = int(end_pos.y * h)
                    
                    # Prüfe ob beide Punkte im Frame sind
                    if 0 <= x1 < w and 0 <= y1 < h and 0 <= x2 < w and 0 <= y2 < h:
                        # Weiße Linien für Skelett-Struktur (werden von Punkten überlagert)
                        cv2.line(frame, (x1, y1), (x2, y2), (255, 255, 255), 1)
            
            # Zeichne Landmarks (Kreise) - NACH Linien für sichtbaren Überlagerer-Effekt
            for landmark_idx, landmark in enumerate(hand_landmarks):
                x = int(landmark.x * w)
                y = int(landmark.y * h)
                
                if 0 <= x < w and 0 <= y < h:
                    # Fingerspitzen größer
                    radius = 7 if landmark_idx in [4, 8, 12, 16, 20] else 4
                    cv2.circle(frame, (x, y), radius, landmark_color, -1)
                    
                    # Weiße Kontur (sichtbarer)
                    cv2.circle(frame, (x, y), radius + 2, (255, 255, 255), 2)
    
    except Exception as e:
        logger.warning(f"Fehler beim Zeichnen von Landmarks: {e}")
    
    return frame


def draw_incircle_debug(
    frame: np.ndarray,
    hand_states: dict,
    w: int = None,
    h: int = None
) -> np.ndarray:
    """
    Zeichne den Inkreis-Debug-Kreis auf dem Frame
    
    Der Inkreis ist der größte Kreis der INNERHALB der Hand liegt:
    - Finger INNERHALB = gestreckt
    - Finger AUSSERHALB = gebeugt
    
    Args:
        frame: OpenCV BGR image
        hand_states: Hand-States mit incircle_center und incircle_radius
        w, h: Frame-Breite und -Höhe (auto-detect wenn None)
    
    Returns:
        Frame mit gezeichnetem Kreis
    """
    if w is None or h is None:
        h, w = frame.shape[:2]
    
    try:
        for hand_side, hand_state in hand_states.items():
            incircle_center = hand_state.get('incircle_center')
            incircle_radius = hand_state.get('incircle_radius')
            
            if incircle_center is None or incircle_radius is None:
                continue
            
            # Konvertiere normalisierte Koordinaten (0-1) zu Pixel
            cx = int(incircle_center[0] * w)
            cy = int(incircle_center[1] * h)
            radius_px = int(incircle_radius * w)  # Nutze w als Referenz
            
            # Farbe je nach Hand
            circle_color = (255, 0, 0) if hand_side == "left" else (0, 255, 0)  # Blau oder Grün
            
            # Zeichne Inkreis-Outline (solid line)
            cv2.circle(frame, (cx, cy), radius_px, circle_color, 2)
            
            # Zeichne Mittelpunkt (Inzentrum)
            cv2.circle(frame, (cx, cy), 5, circle_color, -1)
            
            # Debug-Text
            text = f"{hand_side} incircle: r={radius_px}px"
            cv2.putText(
                frame, text, (cx - 50, cy - radius_px - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, circle_color, 1
            )
    
    except Exception as e:
        logger.warning(f"Fehler beim Zeichnen des Inkreises: {e}")
    
    return frame


def draw_incircle_finger_status(
    frame: np.ndarray,
    hand_states: dict
) -> np.ndarray:
    """
    Zeichne detaillierte Inkreis-Status für jeden Finger
    
    Zeigt für jeden Finger:
    - INSIDE (BENT) = Gebeugt (Spitze drinnen im Inkreis) - Rot
    - OUTSIDE (STRAIGHT) = Gestreckt (Spitze draußen vom Inkreis) - Grün
    
    Args:
        frame: OpenCV BGR image
        hand_states: Hand-States mit bent_fingers Info
    
    Returns:
        Frame mit Finger-Status
    """
    if not hand_states:
        return frame
    
    try:
        h, w = frame.shape[:2]
        
        # Alle Finger in Reihenfolge
        finger_names = ['thumb', 'index', 'middle', 'ring', 'pinky']
        
        y_offset = 20
        for hand_side, hand_state in hand_states.items():
            bent_fingers = hand_state.get('bent_fingers', [])
            
            # Panel-Hintergrund
            panel_width = 250
            panel_height = 140
            x_pos = w - panel_width - 20
            y_pos = h - panel_height - 20
            
            cv2.rectangle(frame, (x_pos, y_pos), (x_pos + panel_width, y_pos + panel_height), (20, 20, 20), -1)
            cv2.rectangle(frame, (x_pos, y_pos), (x_pos + panel_width, y_pos + panel_height), (100, 100, 100), 2)
            
            # Titel
            title_text = f"INCIRCLE STATUS ({hand_side})"
            cv2.putText(
                frame, title_text, (x_pos + 10, y_pos + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1
            )
            
            # Finger-Status
            for i, finger_name in enumerate(finger_names):
                # Bestimme Status
                is_bent = finger_name in bent_fingers
                status_text = "INSIDE (BENT)" if is_bent else "OUTSIDE (STRAIGHT)"
                status_color = (0, 0, 255) if is_bent else (0, 255, 0)  # Rot oder Grün
                
                # Finger-Name + Status
                label = f"{finger_name.upper()[:3]}: {status_text}"
                cv2.putText(
                    frame, label, (x_pos + 10, y_pos + 50 + i * 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, status_color, 1
                )
    
    except Exception as e:
        logger.warning(f"Fehler beim Zeichnen des Finger-Status: {e}")
    
    return frame


def draw_interactive_debug(
    frame: np.ndarray,
    hand_states: dict,
    detected_position: int = None,
    active_chords: dict = None,
    root_note: str = "C"
) -> np.ndarray:
    """
    Zeichne Debug-Info für Interactive Mode
    - Erkannte Position (1-7)
    - Aktive Akkorde
    - Finger-Status
    
    Args:
        frame: OpenCV BGR image
        hand_states: Hand-States von camera
        detected_position: Erkannte Position (1-7) oder None
        active_chords: Dict mit aktiven Akkorden
        root_note: Aktuelle Tonart
    
    Returns:
        Frame mit Debug-Info
    """
    if not hand_states:
        return frame
    
    try:
        h, w = frame.shape[:2]
        
        # Background panel für Lesbarkeit
        cv2.rectangle(frame, (10, 10), (400, 280), (0, 0, 0), -1)
        cv2.rectangle(frame, (10, 10), (400, 280), (200, 200, 200), 2)
        
        y_pos = 40
        line_height = 30
        
        # Titel
        cv2.putText(
            frame,
            f"INTERACTIVE MODE DEBUG - {root_note}",
            (20, y_pos),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2
        )
        
        y_pos += line_height
        
        # Erkannte Position
        if detected_position is not None:
            color = (0, 255, 0) if detected_position > 0 else (0, 0, 255)
            cv2.putText(
                frame,
                f"Position erkannt: {detected_position} / 7",
                (20, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                color,
                2
            )
        else:
            cv2.putText(
                frame,
                "Position: KEINE",
                (20, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (0, 0, 255),
                2
            )
        
        y_pos += line_height
        
        # Finger-Status (aus linker Hand)
        if 'left' in hand_states:
            states = hand_states['left'].get('states', {})
            
            # Zeige welche Finger gestreckt sind
            straight_fingers = []
            for finger, state in states.items():
                # Gestreckt = READY oder RELEASING
                if state in ["READY", "RELEASING"]:
                    straight_fingers.append(finger[:3].upper())
            
            status_text = "Gestreckt: " + ", ".join(straight_fingers) if straight_fingers else "Gestreckt: KEINE"
            cv2.putText(
                frame,
                status_text,
                (20, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (100, 200, 255),
                1
            )
        
        y_pos += line_height
        
        # Aktive Akkorde
        if active_chords and active_chords.get("left"):
            midi_notes = active_chords["left"]
            chord_text = f"Akkord (MIDI): {midi_notes}"
            cv2.putText(
                frame,
                chord_text,
                (20, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 100),
                1
            )
        else:
            cv2.putText(
                frame,
                "Akkord: -",
                (20, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (100, 100, 100),
                1
            )
        
        y_pos += line_height
        
        # Position-Legende
        cv2.putText(
            frame,
            "Pos 1:IND  2:IND+MID  3:IND+MID+RIN",
            (20, y_pos),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (150, 150, 150),
            1
        )
        y_pos += 20
        cv2.putText(
            frame,
            "4:IND+MID+RIN+PIN  5:ALL  6:IND+PIN  7:IND+PIN+THU",
            (20, y_pos),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (150, 150, 150),
            1
        )
        
    except Exception as e:
        logger.warning(f"Fehler beim Zeichnen Interactive Debug: {e}")
    
    return frame


def draw_finger_states_on_frame(frame: np.ndarray, hand_states: dict) -> np.ndarray:
    """
    Zeichne Finger-Beugung States auf Frame in 2 Spalten
    Links: Linke Hand | Rechts: Rechte Hand
    
    Args:
        frame: OpenCV BGR image
        hand_states: Dict mit Hand-States von camera.current_hand_states
        
    Returns:
        Frame mit gezeichneten Finger-States
    """
    if not hand_states:
        return frame
    
    try:
        h, w = frame.shape[:2]
        y_start = 120
        left_col_x = 20
        right_col_x = w // 2 + 20
        line_height = 25
        
        # Finger-Abkürzungen
        finger_abbrev = {
            'thumb': 'THU',
            'index': 'IND',
            'middle': 'MID',
            'ring': 'RIN',
            'pinky': 'PIN'
        }
        
        # Zeichne LINKE HAND (linke Spalte)
        if 'left' in hand_states:
            hand_state = hand_states['left']
            hand_color = (255, 0, 0)  # Blau
            
            cv2.putText(
                frame,
                "LINKE HAND",
                (left_col_x, y_start),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                hand_color,
                2
            )
            
            states_text = hand_state.get('states', {})
            triggered = hand_state.get('triggered_fingers', [])
            
            for i, (finger_name, abbrev) in enumerate(finger_abbrev.items()):
                if finger_name in states_text:
                    state = states_text[finger_name]
                    
                    # Farbe: Orange wenn triggered/held
                    if finger_name in triggered or state in ['TRIGGERED', 'HELD']:
                        finger_color = (0, 165, 255)  # Orange
                    else:
                        finger_color = (200, 200, 200)  # Grau
                    
                    text = f"{abbrev}: {state}"
                    y_pos = y_start + (i + 1) * line_height
                    cv2.putText(
                        frame,
                        text,
                        (left_col_x, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.65,
                        finger_color,
                        1
                    )
        
        # Zeichne RECHTE HAND (rechte Spalte)
        if 'right' in hand_states:
            hand_state = hand_states['right']
            hand_color = (0, 255, 0)  # Grün
            
            cv2.putText(
                frame,
                "RECHTE HAND",
                (right_col_x, y_start),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                hand_color,
                2
            )
            
            states_text = hand_state.get('states', {})
            triggered = hand_state.get('triggered_fingers', [])
            
            for i, (finger_name, abbrev) in enumerate(finger_abbrev.items()):
                if finger_name in states_text:
                    state = states_text[finger_name]
                    
                    # Farbe: Orange wenn triggered/held
                    if finger_name in triggered or state in ['TRIGGERED', 'HELD']:
                        finger_color = (0, 165, 255)  # Orange
                    else:
                        finger_color = (200, 200, 200)  # Grau
                    
                    text = f"{abbrev}: {state}"
                    y_pos = y_start + (i + 1) * line_height
                    cv2.putText(
                        frame,
                        text,
                        (right_col_x, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.65,
                        finger_color,
                        1
                    )
        
    except Exception as e:
        logger.warning(f"Fehler beim Zeichnen von Finger-States: {e}")
    
    return frame


class CameraLabel(QLabel):
    """Custom QLabel für OpenCV Frame-Display"""

    def set_image_from_cv(self, cv_image: np.ndarray) -> None:
        """
        Zeige OpenCV Image in QLabel

        Args:
            cv_image: BGR numpy array
        """
        # Convert BGR to RGB
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)

        # Convert to QImage
        h, w, c = rgb_image.shape
        bytes_per_line = c * w
        qt_image = QImage(
            rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888
        )

        # Set as pixmap
        pixmap = QPixmap.fromImage(qt_image)
        self.setPixmap(pixmap.scaledToWidth(self.width() - 10, Qt.TransformationMode.SmoothTransformation))


class MainWindow(QMainWindow):
    """Hauptfenster der Anwendung"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.WINDOW_TITLE)
        self.setGeometry(100, 100, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)

        # Config
        self.config = config

        # Game State (zentrale Logik)
        self.game_state = init_game_state()

        # Camera Handler
        self.camera = None
        self.use_mock_camera = False

        # Audio Player
        self.audio_player = get_audio_player()
        self.music_theory = MusicTheory()

        # UI Elements
        self.camera_label = None
        self.status_label = None
        self.start_button = None
        self.stop_button = None
        self.volume_slider = None
        self.mode_combo = None
        self.root_note_combo = None

        # Timer für Frame-Updates
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_frame)
        self.timer.setInterval(1000 // config.FPS)  # 30fps

        self._init_ui()
        self._init_camera()
        self._init_audio()

        # Auto-Start Kamera wenn konfiguriert
        if config.CAMERA_AUTO_START:
            QTimer.singleShot(500, self._on_start_clicked)  # 500ms verzögert

    def _init_ui(self) -> None:
        """Initialisiere UI-Elemente"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main Layout
        main_layout = QVBoxLayout()

        # Camera Display
        self.camera_label = CameraLabel()
        self.camera_label.setMinimumSize(config.WINDOW_WIDTH - 20, config.WINDOW_HEIGHT - 200)
        self.camera_label.setStyleSheet("background-color: black; color: white;")
        self.camera_label.setText("Kamera wird initialisiert...")
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.camera_label)

        # Settings Layout (Modus, Tonart - oben rechts)
        settings_layout = QHBoxLayout()
        settings_layout.addStretch()  # Spacing nach links
        
        # Mode Dropdown
        settings_layout.addWidget(QLabel("Modus:"))
        self.mode_combo = QComboBox()
        for mode in GameMode:
            self.mode_combo.addItem(mode.value)
        self.mode_combo.setCurrentText(GameMode.INTERACTIVE.value)  # DEFAULT: Interactive
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        settings_layout.addWidget(self.mode_combo)
        
        # Root Note Dropdown
        settings_layout.addWidget(QLabel("Tonart:"))
        self.root_note_combo = QComboBox()
        for note in ALL_ROOT_NOTES:
            self.root_note_combo.addItem(note)
        self.root_note_combo.setCurrentText("C")
        self.root_note_combo.currentTextChanged.connect(self._on_root_note_changed)
        settings_layout.addWidget(self.root_note_combo)
        
        main_layout.addLayout(settings_layout)

        # Control Layout
        control_layout = QHBoxLayout()

        # Start Button
        self.start_button = QPushButton("▶ Start")
        self.start_button.clicked.connect(self._on_start_clicked)
        self.start_button.setMinimumHeight(40)
        control_layout.addWidget(self.start_button)

        # Stop Button
        self.stop_button = QPushButton("⏹ Stopp")
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)

        # Volume Slider
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(int(config.MASTER_VOLUME * 100))
        self.volume_slider.setMinimumWidth(100)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        control_layout.addWidget(QLabel("Lautstärke:"))
        control_layout.addWidget(self.volume_slider)

        # Status Label
        self.status_label = QLabel("Bereit")
        font = QFont()
        font.setPointSize(10)
        self.status_label.setFont(font)
        self.status_label.setStyleSheet("color: green;")
        control_layout.addWidget(self.status_label)

        main_layout.addLayout(control_layout)

        # Audio Test Layout
        audio_test_layout = QHBoxLayout()
        audio_test_layout.addWidget(QLabel("Audio Test:"))

        # Test Buttons for Notes
        test_notes = [
            ("C4 (60)", 60),
            ("E4 (64)", 64),
            ("G4 (67)", 67),
        ]
        for label, midi_note in test_notes:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, n=midi_note: self._on_test_tone(n))
            btn.setMinimumHeight(30)
            audio_test_layout.addWidget(btn)

        # Test Buttons for Chords
        audio_test_layout.addWidget(QLabel("Akkorde:"))
        test_chords = [
            ("C-Dur", [60, 64, 67]),  # C-E-G
            ("F-Dur", [65, 69, 72]),  # F-A-C
            ("G-Dur", [67, 71, 74]),  # G-B-D
            ("A-Moll", [69, 72, 76]),  # A-C-E
        ]
        for label, chord in test_chords:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, c=chord: self._on_test_chord(c))
            btn.setMinimumHeight(30)
            audio_test_layout.addWidget(btn)

        # Stop Audio Button
        btn_stop_audio = QPushButton("⏸ Stop Audio")
        btn_stop_audio.clicked.connect(lambda: self.audio_player.stop_all())
        btn_stop_audio.setMinimumHeight(30)
        audio_test_layout.addWidget(btn_stop_audio)

        main_layout.addLayout(audio_test_layout)
        central_widget.setLayout(main_layout)

    def _init_camera(self) -> None:
        """Initialisiere Kamera"""
        self.camera = CameraHandler(config.CAMERA_ID, config.CAMERA_MIRROR)

        if not self.camera.initialize():
            logger.warning("Echte Kamera nicht verfügbar, nutze MockCamera")
            self.use_mock_camera = True
            self.camera = MockCamera()
            self.camera.initialize()
            self._set_status("⚠️ MockCamera (keine Webcam verfügbar)", "orange")
        else:
            self._set_status("✅ Kamera bereit", "green")

    def _on_start_clicked(self) -> None:
        """Start Button clicked"""
        try:
            self.camera.start()
            self.timer.start()
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self._set_status("▶ Kamera läuft...", "green")
            logger.info("Kamera gestartet")
        except Exception as e:
            logger.error(f"Fehler beim Starten der Kamera: {e}")
            self._set_status(f"❌ Fehler: {e}", "red")

    def _on_stop_clicked(self) -> None:
        """Stop Button clicked"""
        try:
            self.timer.stop()
            self.camera.stop()
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self._set_status("⏹ Gestoppt", "orange")
            logger.info("Kamera gestoppt")
        except Exception as e:
            logger.error(f"Fehler beim Stoppen der Kamera: {e}")
            self._set_status(f"❌ Fehler: {e}", "red")

    def _update_frame(self) -> None:
        """Update Frame-Anzeige mit Hand-Landmarks und Finger-States"""
        try:
            # Hole Frame + Hand-Tracking Ergebnisse
            if hasattr(self.camera, 'get_frame_with_hands'):
                frame, hands = self.camera.get_frame_with_hands()
            else:
                # Fallback für MockCamera oder alte Kamera-Versionen
                frame = self.camera.get_frame()
                hands = None
            
            if frame is not None:
                # Zeichne Landmarks auf Frame
                if hands is not None:
                    frame = draw_landmarks_on_frame(frame, hands)
                
                # Zeichne Finger-States (von camera.current_hand_states)
                if hasattr(self.camera, 'current_hand_states'):
                    frame = draw_finger_states_on_frame(frame, self.camera.current_hand_states)
                    
                    # DEBUG: Zeichne Inkreis-Kreis für Finger-Erkennung
                    if self.config.SHOW_INCIRCLE_DEBUG:
                        frame = draw_incircle_debug(frame, self.camera.current_hand_states)
                        frame = draw_incircle_finger_status(frame, self.camera.current_hand_states)
                    
                    # DEBUG: Interactive Mode Info anzeigen
                    if self.game_state.mode == GameMode.INTERACTIVE:
                        status = self.game_state.get_status()
                        frame = draw_interactive_debug(
                            frame,
                            self.camera.current_hand_states,
                            detected_position=status.get("interactive_position"),
                            active_chords=status.get("active_chords"),
                            root_note=self.game_state.root_note
                        )
                    
                    # ===== ZENTRALE LOGIK: Hand-States an GameState übergeben =====
                    for hand_side, hand_state in self.camera.current_hand_states.items():
                        self.game_state.process_hand_state(hand_side, hand_state)
                
                self.camera_label.set_image_from_cv(frame)
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des Frames: {e}")

    def _init_audio(self) -> None:
        """Initialisiere Audio-Player"""
        try:
            if not init_audio():
                logger.warning("Audio-Player konnte nicht initialisiert werden")
                self._set_status("⚠️ Audio nicht verfügbar", "orange")
            else:
                self.audio_player.start()
                self._set_status("✅ Audio bereit", "green")
        except Exception as e:
            logger.error(f"Fehler beim Initialisieren von Audio: {e}")
            self._set_status(f"❌ Audio-Fehler: {e}", "red")

    def _on_volume_changed(self, value: int) -> None:
        """Volume Slider changed"""
        volume = value / 100.0
        self.audio_player.set_volume(volume)
        logger.debug(f"Lautstärke: {volume:.2f}")

    def _on_test_tone(self, midi_note: int) -> None:
        """Test Button: Spiele einzelnen Ton"""
        try:
            self.audio_player.play_tone(midi_note, duration=0.5)
            note_name = self._midi_to_note_name(midi_note)
            logger.info(f"Test Ton: {note_name}")
        except Exception as e:
            logger.error(f"Fehler beim Abspielen des Tons: {e}")

    def _on_test_chord(self, midi_notes: List[int]) -> None:
        """Test Button: Spiele Akkord"""
        try:
            self.audio_player.play_chord(midi_notes, duration=2.0)
            note_names = [self._midi_to_note_name(n) for n in midi_notes]
            logger.info(f"Test Akkord: {note_names}")
        except Exception as e:
            logger.error(f"Fehler beim Abspielen des Akkords: {e}")

    def _on_mode_changed(self, mode_value: str) -> None:
        """Modus-Dropdown gewechselt"""
        try:
            mode = GameMode(mode_value)
            self.game_state.set_mode(mode)
            self._set_status(f"📋 Modus: {mode_value}", "green")
            logger.info(f"Modus gewechselt: {mode_value}")
        except Exception as e:
            logger.error(f"Fehler beim Wechsel des Modus: {e}")

    def _on_root_note_changed(self, note: str) -> None:
        """Tonart-Dropdown gewechselt"""
        try:
            self.game_state.set_root_note(note)
            self._set_status(f"🎵 Tonart: {note}", "green")
            logger.info(f"Tonart gewechselt: {note}")
        except Exception as e:
            logger.error(f"Fehler beim Wechsel der Tonart: {e}")

    @staticmethod
    def _midi_to_note_name(midi_note: int) -> str:
        """Konvertiere MIDI zu Note Name"""
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = (midi_note // 12) - 1
        note_index = midi_note % 12
        return f"{note_names[note_index]}{octave}"

    def _set_status(self, message: str, color: str = "white") -> None:
        """Update Status-Label"""
        self.status_label.setText(message)
        color_map = {"green": "color: green;", "red": "color: red;", "orange": "color: orange;"}
        self.status_label.setStyleSheet(color_map.get(color, "color: white;"))

    def closeEvent(self, event) -> None:
        """Handle Fenster-Schließen"""
        logger.info("Fenster wird geschlossen, räume auf...")
        self.timer.stop()
        if self.camera:
            self.camera.stop()
        if self.audio_player:
            self.audio_player.stop()
        event.accept()

    def keyPressEvent(self, event) -> None:
        """Handle Tastatureingaben"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)


def run_ui() -> int:
    """Starten Sie die PySide6 Anwendung"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(run_ui())
