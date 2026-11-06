# Visual Gestures Synthesizer – Agent Instructions

## Projekt-Übersicht

Eine lokale **Air-Music-App mit Python, OpenCV und MediaPipe**. Die App erkennt Hände mittels Webcam und erzeugt durch Fingerbewegungen oder Handgesten Musik. Vollständig lokale Verarbeitung, keine externen Services.

**Repository**: Wird zu GitHub hochgeladen  
**Status**: Stufen 1–6 für dieses Wochenende prioritär

---

## Tech-Stack

- **Python** mit virtueller Umgebung
- **OpenCV**: Kamerazugriff und Bildverarbeitung
- **MediaPipe Tasks API**: HandLandmarker (aktuelle Version)
- **PySide6**: UI, Fenster, Kameradisplay, transparente Overlays
- **Audio-Bibliothek**: Lokale Synthese (später festlegen)
- **Sequenzielle Verarbeitung**: VIDEO-Modus mit monoton steigenden Zeitstempeln

---

## Oberflächen-Design

Nach der Gesture-Synth-Referenz mit eigener Gestaltung:

- **Hintergrund**: Großes, gespiegeltes Live-Kamerabild
- **Landmark-Overlay**: Sichtbare Hand-Landmarks und Verbindungen
- **Oben**: Spielmodus, Tonart, Skalentyp, Instrument
- **Links/Rechts**: Fingerbelegung der Hände
- **Unten**: Aktuelle Note/Akkord mit Stufenbezeichnung
- **Bedienelemente**: Start/Stopp, Lautstärke, halbtransparente Panels
- **Farbschema**: Dunkle Panels, warme Akzentfarben

---

## Architektur

```
Webcam (OpenCV)
    ↓
Hand Tracking (MediaPipe)
    ↓
Glättung & Gestenerkennung
    ↓
Spielmodus (Piano / Stufenakkorde / Gesten)
    ↓
Musiklogik (Tonart, Akkorde, MIDI-Nummern)
    ↓
Audio + UI
```

### Datenstrukturen

- **Tracking-Ergebnis**: Zeitstempel, Handzuordnung, Landmarks
- **Fingerzustand**: Position, Beugungsgrad, Auslösestatus
- **Spielereignis**: Ereignistyp, Finger/Hand, Zeitstempel
- **Aktive Noten**: Liste mit MIDI-Nummern und Startzeit
- **Einstellungen**: Tonart, Modus, Fingerbelegung, Filter-Konstanten

**Intern**: MIDI-Notennummern für Tonhöhen  
**Anzeige**: Internationale Notennamen (C, D, E, F, G, A, B)

---

## Implementierungs-Roadmap

### Stufe 1 – Projekt und Kamerafenster

**Ziel**: Startbares Fenster mit Live-Kamerabild

- Projektstruktur und virtuelle Umgebung
- Abhängigkeiten (OpenCV, MediaPipe, PySide6) und README
- Live-Kamerabild im Fenster, gespiegelt
- Start/Stopp, sauberes Beenden, Fehlerbehandlung (keine Kamera)

**Abnahme**: Kamera läuft, Ressourcen werden freigegeben

---

### Stufe 2 – Hände und Finger erkennen

**Ziel**: Zuverlässiges Hand-Tracking mit beiden Händen

- Hand-Landmarker-Modell integrieren
- Bis zu zwei Hände erkennen, links/rechts korrekt kennzeichnen
- Alle fünf Fingerspitzen bereitstellen
- Positionsschwankungen mit einstellbarem Filter glätten
- Handzuordnung explizit prüfen (nicht nur Reihenfolge!)
- Tracking-Verlust und Wiedererkennung behandeln

**Abnahme**: Beide Hände korrekt beschriftet, Tracking-Verlust führt zu neutralem Zustand

---

### Stufe 3 – Audio unabhängig von der Kamera

**Ziel**: Zuverlässige lokale Audiowiedergabe

- Einfachen Synthesizerklang erzeugen
- Einzelne Töne und Dreiklänge unterstützen
- Kurze Ein-/Ausblendungen gegen Knackgeräusche
- Lautstärke und „Alle Töne stoppen"
- Audiowiedergabe unabhängig von Bildverarbeitung
- Buttons zum Testen der Audio-Pipeline

**Abnahme**: Buttons spielen zuverlässig Noten und Akkorde, UI bleibt bedienbar

---

### Stufe 4 – Stufenakkorde (Priorität!)

**Ziel**: Spielbarer Modus mit Tonart-Dreiklängen

- Nutzer wählt Tonart (Start: C-Dur)
- Jeder zugeordnete Finger spielt einen diatonischen Dreiklang
- **Start-Belegung (C-Dur)**:
  - Linker Zeigefinger → I (C-Dur)
  - Linker Mittelfinger → IV (F-Dur)
  - Rechter Zeigefinger → V (G-Dur)
  - Rechter Mittelfinger → vi (A-Moll)

**Fingererkennung**:
- Bewusste Fingerbeugung relativ zur Hand (nicht nur absolute Bildschirmhöhe)
- Gelenkwinkel oder normalisierte Abstände nutzen
- Getrennte Schwellen für Auslösen und Zurücksetzen
- Pro Finger: Zustände „bereit" und „ausgelöst"
- Gehaltenes Signal = kein erneuter Anschlag
- Nach Tracking-Verlust zuerst neutrale Stellung erkennen
- Neuer Akkord ersetzt bisherigen mit kurzer Ausblendung

**Diagnose**: Erkannte Zustände zunächst anzeigen

**Abnahme**: Folge C–G–Am–F spielbar, keine Mehrfachauslösungen

---

### Stufe 5 – Tonarten und sieben Stufen

**Ziel**: Alle Tonarten mit korrekten Akkorden

- Alle zwölf Grundtöne mit Dur-Tonleitern
- Dreiklang-Muster: Dur – Moll – Moll – Dur – Dur – Moll – vermindert
- **Beispiel C-Dur**:
  - I: C-Dur (C–E–G)
  - ii: D-Moll (D–F–A)
  - iii: E-Moll (E–G–B)
  - IV: F-Dur (F–A–C)
  - V: G-Dur (G–B–D)
  - vi: A-Moll (A–C–E)
  - vii°: B-vermindert (B–D–F)

- Akkorde aus Tonleiter berechnen
- Sieben frei zuweisbare Finger
- Fingerbelegung nach Tonartwechsel aktualisieren
- Aktive Noten bei Modus/Tonartwechsel stoppen

**Abnahme**: In D-Dur ist ii korrekt E-Moll, V korrekt A-Dur

---

### Stufe 6 – Oberfläche nach Referenz

**Ziel**: Vollständige, flüssige UI

- Kamerabild ohne Verzerrung skalieren
- Landmark-Koordinaten korrekt auf Anzeige übertragen
- Panels bei Größenänderung sinnvoll positionieren
- Fingerbelegung und aktive Stufe anzeigen
- Aktuellen Akkord prominent darstellen
- Tracking-Status und fehlende Hände anzeigen
- Hilfepanels ein-/ausblendbar
- Diagnoseanzeige optional

**Performance**:
- Worker-Thread für Kamera und Tracking
- UI-Updates im UI-Thread
- Alte Kamerabilder nicht aufstauen

**Abnahme**: Steuerung, Tracking, Audio funktionieren gemeinsam flüssig

---

### Stufe 7 – Air Piano

**Ziel**: Klassischer Klaviermodus

- Acht virtuelle weiße Tasten (C bis C)
- Horizontal = Taste, vertikal = Anschlag
- Anschlaglinie und Rücksetzlinie (Mehrfachauslösung verhindern)
- Später: Mehrere Finger, gleichzeitige Töne

**Abnahme**: Einfache Melodie mit wiederholten Anschlägen spielbar

---

### Stufe 8 – Gesten-Synth

**Ziel**: Ganz-Hand-Posen für Musiksteuerung

- Linke Hand: Stufe aus Gestenbelegung
- Rechte Hand: Zusatzfunktion (z. B. Oktave)
- Wenige deutlich unterscheidbare Posen
- Pose muss für kurze Zeit stabil sein
- Neue Pose sperrt alte ab
- Akkord erklingt, solange Pose gehalten
- Später: Umkehrungen, Septakkorde

**Abnahme**: Gestenwechsel → kontrollierte Akkordwechsel

---

### Stufe 9 – Tests und Dokumentation

**Automatisierte Tests**:
- Akkordberechnung und Transposition
- Zustandswechsel der Anschlagerkennung
- Mehrfachauslösung verhindern
- Verhalten bei Tracking-Verlust

**Manuelle Prüfung**: Kamera, Handzuordnung, Audio, Spielgefühl

**README**:
- Installation und Start
- Modell-Download
- Bedienung und Fingerbelegung
- Kalibrierung
- Bekannte Einschränkungen
- Fehlerdiagnose

---

## Wichtige Anforderungen

✅ **Prüfe vor Installation**:
- Python-Kompatibilität
- MediaPipe, PySide6, Audiobibliothek
- Dokumentierte Schnittstellen
- Funktionierende Paketversionen

✅ **Arbeitsweise**:
- Jede Stufe funktionsfähig und testbar
- Nach jeder Stufe: Kurze Test-Anleitung dokumentieren
- Sequenzielle Verarbeitung mit monoton steigenden Zeitstempeln
- Keine externen Klavier-Samples im Prototyp

✅ **Handtracking-Qualität**:
- Linke und rechte Hand explizit unterscheiden
- Glätten ohne Lag
- Robustheit gegen Tracking-Verlust

---

## Priorität für dieses Wochenende

**Stufen 1–6 abschließen** mit zuverlässig spielbarem Stufenakkord-Modus.  
Air Piano und Gesten-Synth folgen anschließend.

---

## Agent-Guidance

- **Vor Code**: Kompatibilität und Versionen prüfen, dokumentieren
- **Pro Stufe**: Funktionierende Demo + kurze Test-Anleitung
- **Code-Struktur**: Clean separation (Tracking, Musik, Audio, UI)
- **Fehlerbehandlung**: Aussagekräftige Meldungen, sauberes Beenden
- **Performance**: Nicht blockieren, alte Bilder nicht aufstauen
