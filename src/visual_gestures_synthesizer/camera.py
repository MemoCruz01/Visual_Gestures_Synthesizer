"""
Camera Handler - OpenCV Wrapper für Webcam-Zugriff

Verantwortlich für:
- Webcam-Initialisierung
- Frame-Erfassung
- Bildbearbeitung (spiegeln, skalieren)
- Fehlerbehandlung
"""

import cv2
import threading
import queue
import logging
from typing import Optional, Tuple
import numpy as np

from .config import config

logger = logging.getLogger(__name__)


class CameraHandler:
    """Wrapper für OpenCV Kamerazugriff"""

    def __init__(self, camera_id: int = 0, mirror: bool = True):
        """
        Args:
            camera_id: Kamera-ID (0 = default Webcam)
            mirror: Horizontal spiegeln
        """
        self.camera_id = camera_id
        self.mirror = mirror
        self.cap = None
        self.is_running = False
        self.frame_queue = queue.Queue(maxsize=2)
        self.thread = None
        self.current_frame = None
        self.frame_count = 0

    def initialize(self) -> bool:
        """
        Initialisiere Kamerazugriff

        Returns:
            True bei Erfolg, False wenn keine Kamera verfügbar
        """
        try:
            self.cap = cv2.VideoCapture(self.camera_id)

            if not self.cap.isOpened():
                logger.error(f"Kamera {self.camera_id} konnte nicht geöffnet werden")
                return False

            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.WINDOW_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.WINDOW_HEIGHT)
            self.cap.set(cv2.CAP_PROP_FPS, config.FPS)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimaler Buffer

            logger.info(
                f"Kamera {self.camera_id} erfolgreich initialisiert "
                f"({config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT} @ {config.FPS}fps)"
            )
            return True

        except Exception as e:
            logger.error(f"Fehler beim Initialisieren der Kamera: {e}")
            return False

    def start(self) -> None:
        """Starten Sie Kamera-Capture in separatem Thread"""
        if self.is_running:
            logger.warning("Kamera läuft bereits")
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        logger.info("Kamera-Thread gestartet")

    def stop(self) -> None:
        """Stoppen Sie Kamera-Capture"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        self._cleanup()
        logger.info("Kamera gestoppt")

    def _capture_loop(self) -> None:
        """Capture-Loop in separatem Thread"""
        while self.is_running:
            ret, frame = self.cap.read()

            if not ret:
                logger.warning("Fehler beim Lesen des Frames")
                continue

            # Verarbeite Frame
            if self.mirror:
                frame = cv2.flip(frame, 1)  # Horizontal flip

            # Versuchen Queue zu aktualisieren (alte Frames droppen)
            try:
                self.frame_queue.put_nowait(frame)
            except queue.Full:
                try:
                    self.frame_queue.get_nowait()
                    self.frame_queue.put_nowait(frame)
                except queue.Empty:
                    pass

            self.current_frame = frame
            self.frame_count += 1

    def get_frame(self) -> Optional[np.ndarray]:
        """
        Hole aktuelles Frame

        Returns:
            numpy array BGR or None bei Fehler
        """
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return self.current_frame

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Hole letztes verarbeitetes Frame (blocking)"""
        return self.current_frame

    def get_frame_count(self) -> int:
        """Rückgabe Anzahl verarbeiteter Frames"""
        return self.frame_count

    def _cleanup(self) -> None:
        """Cleanup Kamera-Ressourcen"""
        if self.cap:
            self.cap.release()
            logger.info("Kamera-Ressourcen freigegeben")

    def __del__(self):
        """Destruktor"""
        self.stop()


class MockCamera:
    """Mock-Kamera für Tests ohne echte Webcam"""

    def __init__(self):
        self.is_running = False
        self.frame_count = 0

    def initialize(self) -> bool:
        logger.info("MockCamera: Initialisiert")
        return True

    def start(self) -> None:
        self.is_running = True
        logger.info("MockCamera: Gestartet")

    def stop(self) -> None:
        self.is_running = False
        logger.info("MockCamera: Gestoppt")

    def get_frame(self) -> np.ndarray:
        self.frame_count += 1
        # Schwarzes Frame mit Text
        frame = np.zeros((config.WINDOW_HEIGHT, config.WINDOW_WIDTH, 3), dtype=np.uint8)
        cv2.putText(
            frame,
            "Mock Camera (No Webcam Available)",
            (100, config.WINDOW_HEIGHT // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 255),
            2,
        )
        return frame

    def get_latest_frame(self) -> np.ndarray:
        return self.get_frame()

    def get_frame_count(self) -> int:
        return self.frame_count
