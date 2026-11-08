"""
Camera Handler - OpenCV Wrapper für Webcam-Zugriff

Verantwortlich für:
- Webcam-Initialisierung
- Frame-Erfassung
- Bildbearbeitung (spiegeln, skalieren)
- Hand-Tracking mit MediaPipe
- Fehlerbehandlung
"""

import cv2
import threading
import queue
import logging
from typing import Optional, Tuple, List
import numpy as np
import os
import urllib.request
from pathlib import Path

from .config import config

# MediaPipe Imports
try:
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core import base_options  # ← Korrekt für 1.2.2
    from mediapipe import Image, ImageFormat  # ← Image API
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================================
# MediaPipe Hand Landmarker Model Management
# ============================================================================

MODEL_DIR = Path(__file__).parent.parent.parent / "models"
MODEL_PATH = MODEL_DIR / "hand_landmarker.task"


def _download_hand_model():
    """
    Lade Hand Landmarker Modell herunter (nur beim ersten Start)
    
    Strategie:
    1. Prüfe ob Modell existiert
    2. Versuche von mehreren Quellen zu downloaden
    3. Falls alles fehlschlägt: MediaPipe wird das Modell lazy-load
    """
    if MODEL_PATH.exists():
        logger.info(f"✅ Hand Landmarker Modell existiert: {MODEL_PATH}")
        return
    
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    
    if not MEDIAPIPE_AVAILABLE:
        logger.warning("MediaPipe nicht installiert")
        return
    
    logger.info("📥 Lade Hand Landmarker Modell herunter...")
    
    # Versuch 1: Kopiere von MediaPipe's internem Modell-Cache
    try:
        import mediapipe
        mediapipe_path = Path(mediapipe.__file__).parent
        possible_model_paths = [
            mediapipe_path / "tasks" / "python" / "genai" / "hand_landmarker.task",
            mediapipe_path / "tasks" / "hand_landmarker.task",
            mediapipe_path / "hand_landmarker.task",
        ]
        
        for src_path in possible_model_paths:
            if src_path.exists():
                import shutil
                shutil.copy2(src_path, MODEL_PATH)
                logger.info(f"✅ Modell kopiert von: {src_path}")
                return
    except Exception as e:
        logger.debug(f"Konnte nicht von MediaPipe-Pfad kopieren: {e}")
    
    # Versuch 2: Download mit Timeout
    try:
        import urllib.request
        import socket
        
        urls = [
            "https://storage.googleapis.com/mediapipe-models/hand_landmarker.task",
            "https://dl.google.com/mediapipe-tasks/python/hand_landmarker/latest/hand_landmarker.task",
        ]
        
        # Set timeout
        socket.setdefaulttimeout(10)
        
        for url in urls:
            try:
                logger.info(f"   Versuche: {url}")
                urllib.request.urlretrieve(url, MODEL_PATH, timeout=10)
                logger.info(f"✅ Modell heruntergeladen von: {url}")
                return
            except Exception as e:
                logger.debug(f"   Fehler: {e}")
                continue
    except Exception as e:
        logger.debug(f"Download fehlgeschlagen: {e}")
    
    # Fallback: Warnung, MediaPipe wird das Modell beim Load versuchen
    logger.warning("⚠️  Modell-Download fehlgeschlagen, MediaPipe wird Lazy-Loading versuchen")


def _load_hand_landmarker() -> Optional[vision.HandLandmarker]:
    """
    Lade Hand Landmarker mit VIDEO-Mode
    
    Falls das Modell nicht lokal existiert, versucht MediaPipe es automatisch herunterzuladen
    
    Returns:
        HandLandmarker Instanz oder None bei Fehler
    """
    if not MEDIAPIPE_AVAILABLE:
        logger.warning("MediaPipe nicht verfügbar")
        return None
    
    try:
        # Versuche zuerst zu downloaden/finden
        _download_hand_model()
        
        # Wenn Modell jetzt existiert, lade es
        if MODEL_PATH.exists():
            logger.info(f"Lade Modell von: {MODEL_PATH}")
            base_options_obj = base_options.BaseOptions(
                model_asset_path=str(MODEL_PATH)
            )
        else:
            # Fallback: Nutze Default-Modell aus MediaPipe Package
            logger.warning("⚠️  Lokales Modell nicht gefunden, nutze MediaPipe Default")
            base_options_obj = base_options.BaseOptions(
                model_asset_path="hand_landmarker.task"  # MediaPipe sucht dieses intern
            )
        
        options = vision.HandLandmarkerOptions(
            base_options=base_options_obj,
            running_mode=vision.RunningMode.VIDEO,  # ← Wichtig für Zeitstempel!
            num_hands=2  # Beide Hände
        )
        
        landmarker = vision.HandLandmarker.create_from_options(options)
        logger.info("✅ Hand Landmarker geladen")
        return landmarker
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden des Hand Landmarker: {e}")
        logger.error("   Hand-Tracking wird NICHT funktionieren")
        return None



class CameraHandler:
    """Wrapper für OpenCV Kamerazugriff + MediaPipe Hand Tracking"""

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
        self.current_hands = None  # ← Hand-Tracking Ergebnisse
        self.frame_count = 0
        self.start_time_ms = None  # ← Für VIDEO-mode Zeitstempel
        
        # Hand Landmarker
        self.landmarker = None
        if MEDIAPIPE_AVAILABLE:
            self.landmarker = _load_hand_landmarker()

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

        # Wenn Kamera nicht initialisiert (z.B. nach stop()), neu initialisieren
        if self.cap is None or not self.cap.isOpened():
            logger.info("Kamera nicht initialisiert, initialisiere neu...")
            if not self.initialize():
                logger.error("Kamera konnte nicht re-initialisiert werden")
                return

        self.is_running = True
        self.start_time_ms = None  # Reset Zeitstempel
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        logger.info("Kamera-Thread gestartet")

    def stop(self) -> None:
        """Stoppen Sie Kamera-Capture (Kamera bleibt offen für schnellen Neustart)"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        # NOT calling _cleanup() here - Kamera bleibt offen für schnellen Neustart!
        logger.info("Kamera gestoppt")

    def _capture_loop(self) -> None:
        """Capture-Loop in separatem Thread mit Hand-Tracking"""
        import time
        
        while self.is_running:
            ret, frame = self.cap.read()

            if not ret:
                logger.warning("Fehler beim Lesen des Frames")
                continue

            # Verarbeite Frame
            if self.mirror:
                frame = cv2.flip(frame, 1)  # Horizontal flip

            # Hand-Tracking (VIDEO-Mode mit monoton steigenden Zeitstempeln)
            hands = None
            if self.landmarker is not None:
                try:
                    # Berechne Zeitstempel (monoton steigend in ms)
                    if self.start_time_ms is None:
                        self.start_time_ms = int(time.time() * 1000)
                    
                    timestamp_ms = int(time.time() * 1000) - self.start_time_ms
                    
                    # Convert BGR to RGB für MediaPipe
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # Detect hands (VIDEO-mode)
                    mp_image = Image(image_format=ImageFormat.SRGB, data=rgb_frame)
                    hands = self.landmarker.detect_for_video(mp_image, timestamp_ms)
                    
                except Exception as e:
                    logger.warning(f"Hand-Tracking Fehler: {e}")
                    hands = None

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
            self.current_hands = hands  # ← Speichere Hand-Tracking Ergebnisse
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

    def get_frame_with_hands(self) -> Tuple[Optional[np.ndarray], Optional[vision.HandLandmarkerResult]]:
        """
        Hole aktuelles Frame + Hand-Tracking Ergebnisse
        
        Returns:
            Tuple (frame, hands) wobei hands die MediaPipe HandLandmarkerResult ist
        """
        return self.current_frame, self.current_hands

    def get_frame_count(self) -> int:
        """Rückgabe Anzahl verarbeiteter Frames"""
        return self.frame_count

    def _cleanup(self) -> None:
        """Cleanup Kamera-Ressourcen"""
        if self.cap:
            self.cap.release()
            self.cap = None
            logger.info("Kamera-Ressourcen freigegeben")

    def __del__(self):
        """Destruktor - Cleanup beim Beenden"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        self._cleanup()


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

    def get_frame_with_hands(self) -> Tuple[np.ndarray, None]:
        """Mock: Keine Hand-Tracking Ergebnisse"""
        return self.get_frame(), None
