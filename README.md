# Visual Gestures Synthesizer 🎵🤚

Eine lokale **Air-Music-App** mit **Python, OpenCV und MediaPipe**. Erkenne Handbewegungen mit der Webcam und erzeuge Musik durch Fingerbewegungen oder Handgesten.

## Features

- 🎹 **Mehrere Spielmodi**: Stufenakkorde, Air Piano, Gesten-Synth
- 🤖 **Hand-Tracking**: MediaPipe HandLandmarker für präzise Erkennung
- 🎨 **Live-Visualisierung**: Kamerabild mit Landmarks und Overlays
- 🔊 **Lokale Audio-Synthese**: Keine externen Samples erforderlich
- ⚙️ **Konfigurierbar**: Tonarten, Fingerbelegung, Gesten anpassbar
- 🚀 **Vollständig lokal**: Keine externen Services nötig

## Installation

### Voraussetzungen

- Python 3.9+
- Webcam
- Windows, macOS oder Linux

### Schritt 1: Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# oder
venv\Scripts\activate  # Windows
```

### Schritt 2: Abhängigkeiten

```bash
pip install -r requirements.txt
```

### Schritt 3: Starten

```bash
python main.py
```

## Bedienung

### Stufenakkorde-Modus (Priorität)

- **Linker Zeigefinger**: I (Tonika)
- **Linker Mittelfinger**: IV (Subdominante)
- **Rechter Zeigefinger**: V (Dominante)
- **Rechter Mittelfinger**: vi (Relative Moll)

Tonart über das Bedienfeld oben wählen.

### Air Piano

Horizontale Fingerposition wählt die Taste, vertikale Bewegung triggert den Anschlag.

### Gesten-Synth

Handhaltungen wählen Akkorde aus.

## Projektstruktur

```
Visual_Gestures_Synthesizer/
├── main.py                 # Einstiegspunkt
├── src/
│   ├── camera.py          # OpenCV Integration
│   ├── hand_tracking.py   # MediaPipe HandLandmarker
│   ├── music_logic.py     # Tonart, Akkorde, MIDI
│   ├── audio.py           # Audio-Synthese
│   └── ui.py              # PySide6 Interface
├── tests/                  # Unit Tests
├── docs/
│   └── dev-status.md      # Development Notes (lokal)
├── .github/
│   └── copilot-instructions.md  # Agent Instructions
├── requirements.txt        # Dependencies
└── README.md              # Diese Datei
```

## Entwicklungs-Roadmap

1. ✅ Projekt & Kamerafenster
2. ⏳ Hand-Tracking (beide Hände)
3. ⏳ Audio-Synthese
4. ⏳ Stufenakkorde
5. ⏳ Tonarten & 7 Stufen
6. ⏳ Komplette UI
7. ⏳ Air Piano
8. ⏳ Gesten-Synth
9. ⏳ Tests & Dokumentation

## Schnellstart für Entwickler

```bash
# Repository klonen
git clone https://github.com/MemoCruz01/Visual_Gestures_Synthesizer.git
cd Visual_Gestures_Synthesizer

# Umgebung aufsetzen
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Starten
python main.py

# Tests
pytest tests/
```

## Bekannte Einschränkungen

- Nur lokale Audiowiedergabe (kein MIDI-Export)
- Optimiert für 2 Hände
- Erfordert gute Lichtverhältnisse für zuverlässiges Tracking

## Lizenz

MIT License – siehe LICENSE Datei

## Kontakt

**Autor**: MemoCruz01  
**GitHub**: https://github.com/MemoCruz01

---

**Status**: Aktive Entwicklung 🚀
