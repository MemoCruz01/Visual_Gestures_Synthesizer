"""
UI Window - PySide6 GUI für Visual Gestures Synthesizer

Verantwortlich für:
- Fenster und Layout
- Live-Kamerabild-Anzeige
- Buttons und Kontrollelemente
- Status-Anzeigen
- Event-Handling
"""

import sys
import logging
from typing import Optional
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
from .camera import CameraHandler, MockCamera

logger = logging.getLogger(__name__)


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
        """Update Frame-Anzeige"""
        try:
            frame = self.camera.get_frame()
            if frame is not None:
                self.camera_label.set_image_from_cv(frame)
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des Frames: {e}")

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
