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
)
from PySide6.QtGui import QImage, QPixmap, QFont
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtWidgets import QApplication

from .config import config
from .camera import CameraHandler, MockCamera, MEDIAPIPE_AVAILABLE
from .audio import get_audio_player, init_audio
from .music_theory import MusicTheory

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
            
            # Zeichne Verbindungen
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
                        cv2.line(frame, (x1, y1), (x2, y2), connection_color, 2)
            
            # Zeichne Landmarks (Kreise)
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

        # Timer für Frame-Updates
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_frame)
        self.timer.setInterval(1000 // config.FPS)  # 30fps

        self._init_ui()
        self._init_camera()
        self._init_audio()

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
        """Update Frame-Anzeige mit Hand-Landmarks"""
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
