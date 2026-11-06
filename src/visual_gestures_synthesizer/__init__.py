"""
Visual Gestures Synthesizer - Air Music App

Eine lokale Air-Music-App mit Python, OpenCV und MediaPipe.
Erkenne Handbewegungen und erzeuge Musik durch Fingerbewegungen.

Stages:
1. Camera & UI Window
2. Hand Tracking (MediaPipe)
3. Audio Pipeline
4. Scale Chords (Priority!)
5. All Keys & 7 Scale Degrees
6. UI Polish
7. Air Piano
8. Gesture Synth
9. Tests & Docs
"""

__version__ = "0.1.0"
__author__ = "Visual Gestures Team"

from .config import Config
from .camera import CameraHandler
from .ui import MainWindow

__all__ = ["Config", "CameraHandler", "MainWindow"]
