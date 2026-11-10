"""
Kalibrierungs-Dialog für Parameter-Anpassung
- Slider für INCIRCLE_RADIUS_SCALE und andere Tracking-Parameter
- Live-Vorschau auf Hand-Detection
- Nur für autorisierte Nutzer (zukünftig mit Permission-System)
"""

import logging
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QPushButton,
    QGroupBox,
    QSpinBox,
    QDoubleSpinBox,
)
from PySide6.QtCore import Qt
from .config import config

logger = logging.getLogger(__name__)


class CalibrationDialog(QDialog):
    """Dialog zur Kalibrierung von Hand-Tracking Parametern"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Kalibrierungs-Menu")
        self.setGeometry(200, 200, 600, 500)
        self.config = config
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialisiere Kalibrierungs-Dialog UI"""
        layout = QVBoxLayout()

        # ========================================================================
        # GRUPPE 1: INKREIS-RADIUS (Priorität!)
        # ========================================================================
        group_radius = QGroupBox("🎯 Inkreis-Radius Kalibrierung")
        group_layout = QVBoxLayout()

        # INCIRCLE_RADIUS_SCALE
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("INCIRCLE_RADIUS_SCALE:"))
        
        self.radius_scale_spinbox = QDoubleSpinBox()
        self.radius_scale_spinbox.setMinimum(0.5)
        self.radius_scale_spinbox.setMaximum(3.0)
        self.radius_scale_spinbox.setSingleStep(0.05)
        self.radius_scale_spinbox.setValue(config.INCIRCLE_RADIUS_SCALE)
        self.radius_scale_spinbox.setDecimals(2)
        self.radius_scale_spinbox.valueChanged.connect(self._on_radius_scale_changed)
        h_layout.addWidget(self.radius_scale_spinbox)
        
        self.radius_scale_label = QLabel(f"(aktuell: {config.INCIRCLE_RADIUS_SCALE})")
        h_layout.addWidget(self.radius_scale_label)
        h_layout.addStretch()
        
        group_layout.addLayout(h_layout)
        
        # Slider für schnellere Anpassung
        self.radius_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.radius_scale_slider.setMinimum(50)  # 0.5
        self.radius_scale_slider.setMaximum(200)  # 2.0
        self.radius_scale_slider.setValue(int(config.INCIRCLE_RADIUS_SCALE * 100))
        self.radius_scale_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.radius_scale_slider.setTickInterval(10)
        self.radius_scale_slider.sliderMoved.connect(self._on_radius_scale_slider_changed)
        group_layout.addWidget(QLabel("Schnell-Anpassung:"))
        group_layout.addWidget(self.radius_scale_slider)
        
        # Info-Text
        info_text = QLabel(
            "💡 Tipps:\n"
            "• < 1.0 = kleinerer Kreis → strikter (mehr Finger als gestreckt erkannt)\n"
            "• = 1.0 = Standard (Balance)\n"
            "• > 1.0 = größerer Kreis → lockerer (mehr Finger als gebeugt erkannt)\n"
            "• Probieren Sie: 0.85, 0.9, 1.0, 1.1, 1.2, 1.3"
        )
        info_text.setStyleSheet("color: #666; font-size: 9pt;")
        info_text.setWordWrap(True)
        group_layout.addWidget(info_text)
        
        group_radius.setLayout(group_layout)
        layout.addWidget(group_radius)

        # ========================================================================
        # GRUPPE 2: BENT-THRESHOLD (Optional, später nutzbar)
        # ========================================================================
        group_threshold = QGroupBox("🎪 Bent-Threshold Multiplier")
        group_layout_2 = QVBoxLayout()
        
        h_layout_2 = QHBoxLayout()
        h_layout_2.addWidget(QLabel("BENT_THRESHOLD_MULTIPLIER:"))
        
        self.bent_threshold_spinbox = QDoubleSpinBox()
        self.bent_threshold_spinbox.setMinimum(0.7)
        self.bent_threshold_spinbox.setMaximum(1.3)
        self.bent_threshold_spinbox.setSingleStep(0.05)
        self.bent_threshold_spinbox.setValue(config.BENT_THRESHOLD_MULTIPLIER)
        self.bent_threshold_spinbox.setDecimals(2)
        self.bent_threshold_spinbox.valueChanged.connect(self._on_bent_threshold_changed)
        h_layout_2.addWidget(self.bent_threshold_spinbox)
        
        self.bent_threshold_label = QLabel(f"(aktuell: {config.BENT_THRESHOLD_MULTIPLIER})")
        h_layout_2.addWidget(self.bent_threshold_label)
        h_layout_2.addStretch()
        
        group_layout_2.addLayout(h_layout_2)
        group_threshold.setLayout(group_layout_2)
        layout.addWidget(group_threshold)

        # ========================================================================
        # GRUPPE 3: DEBUG-OPTIONEN
        # ========================================================================
        group_debug = QGroupBox("🔍 Debug-Visualisierung")
        group_layout_3 = QVBoxLayout()
        
        # Toggle SHOW_INCIRCLE_DEBUG
        self.debug_incircle_btn = QPushButton(
            f"Inkreis anzeigen: {'✅ ON' if config.SHOW_INCIRCLE_DEBUG else '❌ OFF'}"
        )
        self.debug_incircle_btn.clicked.connect(self._toggle_incircle_debug)
        group_layout_3.addWidget(self.debug_incircle_btn)
        
        # Toggle SHOW_FINGER_STATES
        self.debug_finger_states_btn = QPushButton(
            f"Finger-States anzeigen: {'✅ ON' if config.SHOW_FINGER_STATES else '❌ OFF'}"
        )
        self.debug_finger_states_btn.clicked.connect(self._toggle_finger_states_debug)
        group_layout_3.addWidget(self.debug_finger_states_btn)
        
        group_debug.setLayout(group_layout_3)
        layout.addWidget(group_debug)

        # ========================================================================
        # BUTTONS
        # ========================================================================
        btn_layout = QHBoxLayout()
        
        # Undo Button
        btn_undo = QPushButton("↶ Zurücksetzen")
        btn_undo.clicked.connect(self._on_reset)
        btn_layout.addWidget(btn_undo)
        
        btn_layout.addStretch()
        
        # Close Button
        btn_close = QPushButton("✅ Fertig")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def _on_radius_scale_changed(self, value: float) -> None:
        """SpinBox für INCIRCLE_RADIUS_SCALE geändert"""
        self.config.INCIRCLE_RADIUS_SCALE = value
        self.radius_scale_label.setText(f"(aktuell: {value:.2f})")
        self.radius_scale_slider.blockSignals(True)
        self.radius_scale_slider.setValue(int(value * 100))
        self.radius_scale_slider.blockSignals(False)
        logger.info(f"INCIRCLE_RADIUS_SCALE = {value:.2f}")

    def _on_radius_scale_slider_changed(self, value: int) -> None:
        """Slider für INCIRCLE_RADIUS_SCALE bewegt"""
        float_value = value / 100.0
        self.radius_scale_spinbox.blockSignals(True)
        self.radius_scale_spinbox.setValue(float_value)
        self.radius_scale_spinbox.blockSignals(False)

    def _on_bent_threshold_changed(self, value: float) -> None:
        """SpinBox für BENT_THRESHOLD_MULTIPLIER geändert"""
        self.config.BENT_THRESHOLD_MULTIPLIER = value
        self.bent_threshold_label.setText(f"(aktuell: {value:.2f})")
        logger.info(f"BENT_THRESHOLD_MULTIPLIER = {value:.2f}")

    def _toggle_incircle_debug(self) -> None:
        """Togglen SHOW_INCIRCLE_DEBUG"""
        self.config.SHOW_INCIRCLE_DEBUG = not self.config.SHOW_INCIRCLE_DEBUG
        status = "✅ ON" if self.config.SHOW_INCIRCLE_DEBUG else "❌ OFF"
        self.debug_incircle_btn.setText(f"Inkreis anzeigen: {status}")
        logger.info(f"SHOW_INCIRCLE_DEBUG = {self.config.SHOW_INCIRCLE_DEBUG}")

    def _toggle_finger_states_debug(self) -> None:
        """Togglen SHOW_FINGER_STATES"""
        self.config.SHOW_FINGER_STATES = not self.config.SHOW_FINGER_STATES
        status = "✅ ON" if self.config.SHOW_FINGER_STATES else "❌ OFF"
        self.debug_finger_states_btn.setText(f"Finger-States anzeigen: {status}")
        logger.info(f"SHOW_FINGER_STATES = {self.config.SHOW_FINGER_STATES}")

    def _on_reset(self) -> None:
        """Werte auf Standard zurücksetzen"""
        self.config.INCIRCLE_RADIUS_SCALE = 1.0
        self.config.BENT_THRESHOLD_MULTIPLIER = 1.0
        self.config.SHOW_INCIRCLE_DEBUG = True
        self.config.SHOW_FINGER_STATES = True
        
        self.radius_scale_spinbox.setValue(1.0)
        self.radius_scale_slider.setValue(100)
        self.bent_threshold_spinbox.setValue(1.0)
        self.debug_incircle_btn.setText("Inkreis anzeigen: ✅ ON")
        self.debug_finger_states_btn.setText("Finger-States anzeigen: ✅ ON")
        
        logger.info("Alle Parameter auf Standard zurückgesetzt")
