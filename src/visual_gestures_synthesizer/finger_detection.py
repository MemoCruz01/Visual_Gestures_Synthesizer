"""
Finger-Beugung Erkennung & State-Machine
- Pure Logic: Kreis-basierte Erkennung (robust gegen Handhaltungen)
- State-Management pro Finger (verhindert Mehrfachauslösung)
- Keine UI, kein Audio → 100% testbar
"""

import logging
from enum import Enum
from time import time
from math import acos, sqrt, pi
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Gelenkwinkel-Schwellwerte pro Finger (in Grad)
# Unter dem Threshold = GEBEUGT (aktiv)
# Über dem Threshold = GESTRECKT (inaktiv)
FINGER_THRESHOLDS = {
    'thumb': 50,    # Daumen hat andere Anatomie
    'index': 160,
    'middle': 90,
    'ring': 90,
    'pinky': 90,
}

# Debounce & Sperre-Zeiten
BEND_DEBOUNCE_TIME = 0.05   # 50ms - Schnell reagieren
RELEASE_LOCK_TIME = 0.1     # 100ms - Sperre nach Release


# ============================================================================
# INKREIS-BASIERTE FINGER-ERKENNUNG
# ============================================================================

def calculate_incircle_center(
    landmark1, landmark2, landmark3
) -> Tuple[float, float]:
    """
    Berechne das Inzentrum (center of the incircle) eines Dreiecks
    
    Das Inzentrum ist der Mittelpunkt des größten Kreises, der INNERHALB
    des Dreiecks liegt. Das ist die perfekte Referenz für die Hand!
    
    Formel: Inzentrum = (a*P1 + b*P2 + c*P3) / (a+b+c)
    wobei a, b, c die Seitenlängen sind (gegenüber P1, P2, P3)
    
    Args:
        landmark1, landmark2, landmark3: MediaPipe Landmark-Objekte mit x, y
    
    Returns:
        Tuple (center_x, center_y)
    """
    x1, y1 = landmark1.x, landmark1.y
    x2, y2 = landmark2.x, landmark2.y
    x3, y3 = landmark3.x, landmark3.y
    
    # Berechne Seitenlängen des Dreiecks
    a = distance_between_points(landmark2, landmark3)  # gegenüber P1
    b = distance_between_points(landmark1, landmark3)  # gegenüber P2
    c = distance_between_points(landmark1, landmark2)  # gegenüber P3
    
    # Sicherheit: Wenn Dreieck degeneriert ist, nutze Mittelwert
    perimeter = a + b + c
    if perimeter < 1e-10:
        return ((x1 + x2 + x3) / 3, (y1 + y2 + y3) / 3)
    
    # Gewichteter Durchschnitt → Inzentrum
    center_x = (a * x1 + b * x2 + c * x3) / perimeter
    center_y = (a * y1 + b * y2 + c * y3) / perimeter
    
    return (center_x, center_y)


def calculate_incircle_radius(
    landmark1, landmark2, landmark3
) -> float:
    """
    Berechne den Inradius (radius of the incircle)
    
    Formel: inradius = Fläche / Semi-Perimeter
    wobei Fläche via Heron's Formula berechnet wird
    
    Args:
        landmark1, landmark2, landmark3: MediaPipe Landmark-Objekte mit x, y
    
    Returns:
        Radius des Inkreises
    """
    # Berechne Seitenlängen
    a = distance_between_points(landmark2, landmark3)
    b = distance_between_points(landmark1, landmark3)
    c = distance_between_points(landmark1, landmark2)
    
    # Semi-Perimeter
    s = (a + b + c) / 2
    
    # Heron's Formula für Fläche
    # Area = sqrt(s * (s-a) * (s-b) * (s-c))
    discriminant = s * (s - a) * (s - b) * (s - c)
    
    if discriminant < 1e-10:  # Degeneriertes Dreieck
        return 0.001  # Minimal radius
    
    area = sqrt(discriminant)
    
    # Inradius = Fläche / Semi-Perimeter
    inradius = area / s if s > 0 else 0.001
    
    return max(inradius, 0.001)  # Mindestens 0.1% (verhindert zu kleinen Kreis)


def distance_between_points(point1, point2) -> float:
    """
    Berechne Distanz zwischen zwei Landmarks
    
    Args:
        point1, point2: Landmark-Objekte mit x, y (oder Tuples)
    
    Returns:
        Distanz
    """
    if hasattr(point1, 'x'):
        x1, y1 = point1.x, point1.y
    else:
        x1, y1 = point1
    
    if hasattr(point2, 'x'):
        x2, y2 = point2.x, point2.y
    else:
        x2, y2 = point2
    
    return sqrt((x2 - x1)**2 + (y2 - y1)**2)


def is_landmark_inside_circle(
    landmark,
    circle_center: Tuple[float, float],
    circle_radius: float
) -> bool:
    """
    Prüfe ob ein Landmark innerhalb eines Kreises liegt
    
    Args:
        landmark: Landmark-Objekt mit x, y
        circle_center: Tuple (center_x, center_y)
        circle_radius: Radius des Kreises
    
    Returns:
        True wenn Landmark innerhalb des Kreises, False sonst
    """
    dist = distance_between_points(landmark, circle_center)
    return dist < circle_radius


class FingerState(Enum):
    """Zustände pro Finger für State-Machine"""
    READY = "ready"           # Warte auf Beugung
    TRIGGERED = "triggered"   # Gerade ausgelöst (Akkord spielen!)
    HELD = "held"            # Gebeugt, aber schon ausgelöst
    RELEASING = "releasing"  # Entsperre, Sperre aktiv



class FingerTracker:
    """Verwaltet einen einzelnen Finger mit State-Machine"""
    
    def __init__(self, finger_name: str, bend_threshold: float = 90):
        """
        Args:
            finger_name: 'thumb', 'index', 'middle', 'ring', 'pinky'
            bend_threshold: Gelenkwinkel-Schwelle (Grad)
        """
        self.finger_name = finger_name
        self.bend_threshold = bend_threshold
        
        # State-Machine
        self.state = FingerState.READY
        self.bend_start_time = None
        self.release_time = None
        self.last_trigger_time = 0
        
    def update(self, is_bent: bool) -> bool:
        """
        Update Finger-Status basierend auf Beugung
        
        Args:
            is_bent: True wenn Finger gebeugt
        
        Returns:
            True wenn gerade ausgelöst (neuer Trigger)
        """
        current_time = time()
        triggered = False
        
        if is_bent:
            # Starte Beugung-Timer wenn nicht schon läuft
            if self.bend_start_time is None:
                self.bend_start_time = current_time
            
            bend_duration = current_time - self.bend_start_time
            
            # Transition: READY → TRIGGERED
            # (Finger muss mindestens BEND_DEBOUNCE_TIME gebeugt sein)
            if self.state == FingerState.READY and bend_duration > BEND_DEBOUNCE_TIME:
                self.state = FingerState.TRIGGERED
                self.last_trigger_time = current_time
                triggered = True
                logger.debug(f"✅ {self.finger_name} TRIGGERED")
            
            # Transition: TRIGGERED → HELD (nach erstem Trigger)
            elif self.state == FingerState.TRIGGERED:
                self.state = FingerState.HELD
                logger.debug(f"🔒 {self.finger_name} HELD (Lock aktiv)")
        
        else:  # Finger NICHT gebeugt
            self.bend_start_time = None
            
            # Transition: HELD/TRIGGERED → RELEASING
            if self.state in [FingerState.HELD, FingerState.TRIGGERED]:
                self.state = FingerState.RELEASING
                self.release_time = current_time
                logger.debug(f"🔓 {self.finger_name} RELEASING")
            
            # Transition: RELEASING → READY (nach Lock-Zeit)
            elif self.state == FingerState.RELEASING:
                if current_time - self.release_time > RELEASE_LOCK_TIME:
                    self.state = FingerState.READY
                    logger.debug(f"↩️ {self.finger_name} READY")
        
        return triggered
    
    def get_state_short(self) -> str:
        """Gibt kurzen State-Namen zurück für Display"""
        state_short = {
            FingerState.READY: "READY",
            FingerState.TRIGGERED: "TRIGGER",
            FingerState.HELD: "HELD",
            FingerState.RELEASING: "RELEASE",
        }
        return state_short[self.state]




# ============================================================================
# LEGACY: Alte Gelenkwinkel-basierte Funktionen (DEPRECATED)
# ============================================================================
# Diese Funktionen wurden durch die KREIS-basierte Erkennung ersetzt.
# Sie werden hier behalten für Referenz, aber nicht mehr aktiv genutzt.

def calculate_finger_angle(point1, point2, point3) -> float:
    """
    [DEPRECATED] Berechnet Gelenkwinkel zwischen 3 Landmarks (in Grad)
    
    Diese Methode war anfällig gegenüber verschiedenen Handhaltungen.
    Nutze stattdessen die KREIS-basierte Erkennung!
    
    Args:
        point1, point2, point3: MediaPipe Landmark-Objekte mit x, y
    
    Returns:
        Winkel in Grad (0° = gekrümmt, 180° = gestreckt)
    """
    # Vektoren
    v1 = (point2.x - point1.x, point2.y - point1.y)
    v2 = (point3.x - point2.x, point3.y - point2.y)
    
    # Skalarprodukt
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    
    # Normen (Längen)
    norm1 = sqrt(v1[0]**2 + v1[1]**2)
    norm2 = sqrt(v2[0]**2 + v2[1]**2)
    
    # Sicherheit: Division by Zero
    if norm1 == 0 or norm2 == 0:
        return 0
    
    # Cosinus des Winkels
    cos_angle = dot / (norm1 * norm2)
    
    # Clip auf [-1, 1] wegen Floating-Point-Fehlern
    cos_angle = max(-1, min(1, cos_angle))
    
    # Winkel in Radiant → Grad
    angle_rad = acos(cos_angle)
    angle_deg = angle_rad * 180 / pi
    
    return angle_deg


def get_finger_landmarks(hand_landmarks, finger_type: str):
    """
    [DEPRECATED] Extrahiert die 4 Landmarks eines Fingers
    
    Args:
        hand_landmarks: 21 Landmarks von MediaPipe
        finger_type: 'thumb', 'index', 'middle', 'ring', 'pinky'
    
    Returns:
        Liste mit 4 Landmarks (Base → Spitze)
    """
    finger_indices = {
        'thumb': [1, 2, 3, 4],
        'index': [5, 6, 7, 8],
        'middle': [9, 10, 11, 12],
        'ring': [13, 14, 15, 16],
        'pinky': [17, 18, 19, 20]
    }
    
    indices = finger_indices.get(finger_type, [])
    return [hand_landmarks[i] for i in indices]


def is_finger_bent(hand_landmarks, finger_type: str, threshold: float = None) -> bool:
    """
    [DEPRECATED] Prüft ob ein Finger gebeugt ist (Gelenkwinkel-basiert)
    
    Diese Methode ist veraltet! Nutze stattdessen die KREIS-basierte Erkennung
    in HandTracker._is_finger_bent_circle().
    
    Args:
        hand_landmarks: 21 Landmarks von MediaPipe
        finger_type: 'thumb', 'index', 'middle', 'ring', 'pinky'
        threshold: Gelenkwinkel-Schwelle (Standard aus FINGER_THRESHOLDS)
    
    Returns:
        True wenn Finger gebeugt (Winkel < Threshold)
    """
    if threshold is None:
        threshold = FINGER_THRESHOLDS.get(finger_type, 90)
    
    points = get_finger_landmarks(hand_landmarks, finger_type)
    
    if len(points) < 3:
        return False
    
    # Berechne Winkel bei MCP-Gelenk (Index 1)
    # point[0]=Base, point[1]=MCP, point[2]=PIP
    angle = calculate_finger_angle(points[0], points[1], points[2])
    
    # Unter Threshold = GEBEUGT (aktiv)
    return angle < threshold


class HandTracker:
    """Verwaltet alle Finger einer Hand mit State-Machines"""
    
    def __init__(self, hand_side: str = "left"):
        """
        Args:
            hand_side: 'left' oder 'right'
        """
        self.hand_side = hand_side
        
        # Importiere Config am Anfang
        from .config import config
        self.config = config
        
        # State-Machine für jeden Finger
        self.finger_trackers = {
            'thumb': FingerTracker('Daumen', FINGER_THRESHOLDS['thumb']),
            'index': FingerTracker('Index', FINGER_THRESHOLDS['index']),
            'middle': FingerTracker('Mittel', FINGER_THRESHOLDS['middle']),
            'ring': FingerTracker('Ring', FINGER_THRESHOLDS['ring']),
            'pinky': FingerTracker('Klein', FINGER_THRESHOLDS['pinky']),
        }
        
        # Ordnung für Anzeige (links oben → rechts unten)
        self.finger_order = ['thumb', 'index', 'middle', 'ring', 'pinky']
        
        # Debug: Kreis-Info (für UI-Visualisierung)
        self.incircle_center: Optional[Tuple[float, float]] = None
        self.incircle_radius: Optional[float] = None
    
    def process_hand(self, hand_landmarks):
        """
        Verarbeite Hand-Landmarks, berechne Finger-States mit KREIS-LOGIK
        
        Args:
            hand_landmarks: 21 Landmarks von MediaPipe (oder None)
        
        Returns:
            Dict mit Finger-Status:
            {
                'triggered_fingers': ['index'],  # Gerade ausgelöst
                'held_fingers': ['middle'],       # Gebeugt & gehalten
                'bent_fingers': ['index', 'middle'],  # Alle gebeugten
                'states': {
                    'thumb': 'READY',
                    'index': 'HELD',
                    ...
                },
                'hand_side': 'left',
                'circle_center': (0.5, 0.5),  # DEBUG: Kreis-Mittelpunkt
                'circle_radius': 0.1,           # DEBUG: Kreis-Radius
            }
        """
        result = {
            'triggered_fingers': [],
            'held_fingers': [],
            'bent_fingers': [],
            'states': {},
            'hand_side': self.hand_side,
            'incircle_center': None,
            'incircle_radius': None,
        }
        
        # Wenn keine Hand erkannt
        if hand_landmarks is None or len(hand_landmarks) == 0:
            return result
        
        # ===== INKREIS-BASIERTE ERKENNUNG =====
        # 1. Berechne Inkreis-Mittelpunkt aus 3 Landmarks
        try:
            center_landmark_ids = self.config.INCIRCLE_CENTER_LANDMARKS
            if len(hand_landmarks) > max(center_landmark_ids):
                landmarks_for_incircle = [hand_landmarks[i] for i in center_landmark_ids]
                self.incircle_center = calculate_incircle_center(*landmarks_for_incircle)
                result['incircle_center'] = self.incircle_center
                
                # 2. Berechne Inradius (mathematisch aus den 3 Landmarks)
                self.incircle_radius = calculate_incircle_radius(*landmarks_for_incircle)
                
                # 3. Skaliere Inradius nach Config-Parameter
                scaled_radius = self.incircle_radius * self.config.INCIRCLE_RADIUS_SCALE
                self.incircle_radius = scaled_radius
                result['incircle_radius'] = self.incircle_radius
        except Exception as e:
            logger.warning(f"Fehler bei Inkreis-Berechnung: {e}")
            return result
        
        # ===== FINGER-ERKENNUNG: Sind Finger innerhalb oder außerhalb des Kreises? =====
        # Verarbeite jeden Finger
        for finger_name in self.finger_order:
            tracker = self.finger_trackers[finger_name]
            
            # 1. Prüfe ob Finger gebeugt ist (KREIS-LOGIK)
            is_bent = self._is_finger_bent_circle(hand_landmarks, finger_name)
            
            # 2. Update State-Machine (gibt zurück ob gerade ausgelöst)
            triggered = tracker.update(is_bent)
            
            # 3. Sammel Ergebnisse
            if triggered:
                result['triggered_fingers'].append(finger_name)
            
            if tracker.state == FingerState.HELD:
                result['held_fingers'].append(finger_name)
            
            if is_bent:
                result['bent_fingers'].append(finger_name)
            
            # State für Debug-Display
            result['states'][finger_name] = tracker.get_state_short()
        
        return result
    
    def _is_finger_bent_circle(self, hand_landmarks, finger_name: str) -> bool:
        """
        Prüfe ob ein Finger gebeugt ist (INKREIS-basiert)
        
        Inkreis = größter Kreis INNERHALB der Hand
        - Finger ist GEBEUGT wenn die Spitze INNERHALB des Inkreises ist (nah am Mittelpunkt)
        - Finger ist GESTRECKT wenn die Spitze AUSSERHALB des Inkreises ist (weit weg)
        
        Args:
            hand_landmarks: 21 Landmarks von MediaPipe
            finger_name: 'thumb', 'index', 'middle', 'ring', 'pinky'
        
        Returns:
            True wenn Finger gebeugt (innerhalb Inkreis)
        """
        if self.incircle_center is None or self.incircle_radius is None:
            return False
        
        # Hole Landmark-ID der Finger-Spitze
        tip_landmark_id = self.config.FINGER_TIP_LANDMARKS.get(finger_name)
        if tip_landmark_id is None or tip_landmark_id >= len(hand_landmarks):
            return False
        
        tip_landmark = hand_landmarks[tip_landmark_id]
        
        # Prüfe ob Spitze innerhalb des Inkreises
        is_inside = is_landmark_inside_circle(tip_landmark, self.incircle_center, self.incircle_radius)
        
        # KORREKTE LOGIK: Gebeugt = INNERHALB Inkreis
        return is_inside
    
    
    def get_debug_text(self, hand_state: dict) -> str:
        """Formatiert Hand-State für Debug-Display"""
        states_text = "  ".join(
            f"{fn[:3].upper()}:{hand_state['states'].get(fn, '???')}"
            for fn in self.finger_order
        )
        return states_text
