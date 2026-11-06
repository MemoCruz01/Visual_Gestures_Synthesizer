# Quick Start – Visual Gestures Synthesizer

Schneller Einstieg in die App. Für detaillierte Installation siehe [README.md](README.md).

---

## ⚡ Schnellste Variante (nach Setup)

```powershell
visual-gestures-synthesizer
```

Das ist alles! 🚀

---

## 🔧 Setup (nur einmalig)

### 1. Virtual Environment aktivieren

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
.\venv\Scripts\activate.bat
```

**Linux / macOS:**
```bash
source venv/bin/activate
```

### 2. Paket installieren (editable mode)

```powershell
pip install -e .
```

Das ist es! Ab jetzt kannst du die App mit `visual-gestures-synthesizer` starten.

---

## 🎬 App starten

### Variante A: Einfach (empfohlen)
```powershell
visual-gestures-synthesizer
```

### Variante B: Mit Python Modul
```powershell
python -m visual_gestures_synthesizer.main
```

### Variante C: Mit venv-Python direkt
```powershell
.\venv\Scripts\python.exe -m visual_gestures_synthesizer.main
```

---

## 📝 Logging

Die App schreibt Logs zu:
- **Console**: Echtzeit-Output
- **Datei**: `app.log` im Projektverzeichnis

---

## 🎮 Bedienung

| Button | Funktion |
|--------|----------|
| **▶ Start** | Kamera starten |
| **⏹ Stopp** | Kamera stoppen |
| **Volume Slider** | Lautstärke anpassen (später für Audio) |
| **ESC / X** | Fenster schließen |

---

## 🐛 Probleme?

### "Command not found: visual-gestures-synthesizer"
→ Venv muss aktiviert sein und `pip install -e .` muss gelaufen sein

### "No module named 'visual_gestures_synthesizer'"
→ Aktiviere das venv: `.\venv\Scripts\Activate.ps1`

### "Kamera startet nicht"
→ Die App nutzt dann MockCamera (schwarzes Fenster mit Text) – das ist OK für Tests

---

## 📚 Weitere Optionen

- **VS Code Tasks**: `Ctrl+Shift+P` → "Tasks: Run Task" → "Run App"
- **PowerShell Script**: `.\run-app.ps1`
- **Bash Script**: `./run-app.sh`

Viel Spaß! 🎵🤚
