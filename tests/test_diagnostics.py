#!/usr/bin/env python
"""
Diagnose: Verifiziere MediaPipe Hand Landmarker Setup
"""

import sys
from pathlib import Path

# Test 1: Modell-Pfad
print("=" * 70)
print("1️⃣  MODELL-PFAD VERIFIKATION")
print("=" * 70)

# Berechne den Pfad wie in camera.py
camera_py = Path(__file__).parent.parent / "src" / "visual_gestures_synthesizer" / "camera.py"
model_dir = Path(__file__).parent.parent / "models"
model_path = model_dir / "hand_landmarker.task"

print(f"Project Root:    {Path(__file__).parent.parent}")
print(f"Modell-Dir:      {model_dir}")
print(f"Modell-Datei:    {model_path}")
print(f"Modell existiert: {model_path.exists()}")

if model_path.exists():
    size_mb = model_path.stat().st_size / (1024*1024)
    print(f"Modell-Größe:    {size_mb:.2f} MB ✅")
else:
    print("❌ FEHLER: Modell nicht gefunden!")
    sys.exit(1)

# Test 2: MediaPipe Installation
print("\n" + "=" * 70)
print("2️⃣  MEDIAPIPE INSTALLATION")
print("=" * 70)

try:
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core import base_options
    from mediapipe import Image, ImageFormat  # ← Korrekte API
    print("MediaPipe Vision:      ✅")
    print("MediaPipe Base Options: ✅")
except ImportError as e:
    print(f"❌ MediaPipe Fehler: {e}")
    sys.exit(1)

# Test 3: Lade das Modell
print("\n" + "=" * 70)
print("3️⃣  MODELL-LOAD TEST")
print("=" * 70)

try:
    print(f"Lade Modell von: {model_path}")
    
    base_options_obj = base_options.BaseOptions(
        model_asset_path=str(model_path)
    )
    
    options = vision.HandLandmarkerOptions(
        base_options=base_options_obj,
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2
    )
    
    landmarker = vision.HandLandmarker.create_from_options(options)
    print("Hand Landmarker geladen: ✅")
    print(f"Type: {type(landmarker)}")
    
except Exception as e:
    print(f"❌ Fehler beim Laden: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Test Image
print("\n" + "=" * 70)
print("4️⃣  TEST-DETECTION (mit Dummy-Bild)")
print("=" * 70)

try:
    import numpy as np
    
    # Schwarzes Dummy-Bild (640x480 RGB)
    test_image = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Konvertiere zu MediaPipe Image
    mp_image = Image(image_format=ImageFormat.SRGB, data=test_image)
    
    # Versuche zu detecten
    result = landmarker.detect_for_video(mp_image, timestamp_ms=0)
    
    if result.hand_landmarks:
        print(f"Detected Hands: {len(result.hand_landmarks)}")
    else:
        print("Keine Hände im Test-Bild erkannt (erwartet, da Dummy-Bild)")
    
    print("Hand Detection funktioniert: ✅")
    
except Exception as e:
    print(f"❌ Detection Fehler: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: UI-Landmarks Drawing
print("\n" + "=" * 70)
print("5️⃣  UI-LANDMARKS DRAWING FUNKTION")
print("=" * 70)

try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from visual_gestures_synthesizer.ui import draw_landmarks_on_frame
    
    print("draw_landmarks_on_frame importiert: ✅")
    
    # Test mit Dummy-Frame
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result_frame = draw_landmarks_on_frame(dummy_frame, None)
    
    print(f"Frame mit None-Landmarks: {result_frame.shape} ✅")
    
except Exception as e:
    print(f"❌ UI-Fehler: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Zusammenfassung
print("\n" + "=" * 70)
print("✅ ALLE TESTS BESTANDEN - BEREIT FÜR LIVE-TEST!")
print("=" * 70)
print()
print("Nächste Schritte:")
print("1. Starte die App: python -m visual_gestures_synthesizer.main")
print("2. Klicke 'Start' Button")
print("3. Halte deine Hände vor die Webcam")
print("4. Du solltest die Landmarks in Blau/Grün sehen")
