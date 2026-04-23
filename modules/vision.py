"""
vision.py — Módulo de Visão Computacional
BlackJack Vision

Responsabilidades:
- Capturar frames da webcam via OpenCV
- Processar landmarks da mão com MediaPipe Hands
- Classificar gestos em ações do jogo (Hit, Stand, Double, Split)
- Implementar debounce temporal para evitar ações repetidas acidentalmente
- Expor o frame anotado para renderização na interface principal

Gestos implementados:
    Mão aberta (4-5 dedos)   → Hit
    Punho fechado (0 dedos)  → Stand
    1 dedo (indicador)       → Double
    Dois dedos (V)           → Split
"""

import cv2
import mediapipe as mp
import time
from enum import Enum, auto
from typing import Optional


# ─────────────────────────────────────────────
# Ações reconhecidas por gesto
# ─────────────────────────────────────────────

class GestureAction(Enum):
    NONE   = auto()
    HIT    = auto()
    STAND  = auto()
    DOUBLE = auto()
    SPLIT  = auto()


# ─────────────────────────────────────────────
# Índices dos landmarks do MediaPipe
# ─────────────────────────────────────────────
# Referência: https://developers.google.com/mediapipe/solutions/vision/hand_landmarker
#
#  4  = THUMB_TIP       8  = INDEX_FINGER_TIP
#  3  = THUMB_IP        7  = INDEX_FINGER_DIP
#  2  = THUMB_MCP       6  = INDEX_FINGER_PIP
#  1  = THUMB_CMC       5  = INDEX_FINGER_MCP
#  0  = WRIST
#
# Padrão para dedos: TIP > PIP significa dedo levantado
# Para o polegar: TIP.x < IP.x (mão direita) ou TIP.x > IP.x (mão esquerda)

FINGER_TIPS = [8, 12, 16, 20]   # Indicador, médio, anelar, mínimo
FINGER_PIPS = [6, 10, 14, 18]   # Articulações médias correspondentes

THUMB_TIP = 4
THUMB_IP  = 3
THUMB_MCP = 2
WRIST     = 0


class GestureRecognizer:
    """
    Captura vídeo da webcam e classifica gestos da mão em tempo real.

    Usa MediaPipe Hands para detectar 21 landmarks por mão e uma
    lógica de comparação de posições para identificar o gesto.

    O debounce evita que um único gesto dispare a ação várias vezes
    enquanto a mão permanece na posição.
    """

    DEBOUNCE_SECONDS = 1.5   # Tempo mínimo entre dois gestos aceitos

    def __init__(self, camera_index: int = 0):
        """
        Args:
            camera_index (int): Índice da câmera (0 = câmera padrão).
        """
        # MediaPipe setup
        self.mp_hands    = mp.solutions.hands
        self.mp_draw     = mp.solutions.drawing_utils
        self.mp_styles   = mp.solutions.drawing_styles

        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.6,
        )

        # OpenCV — captura de vídeo
        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            raise RuntimeError(
                f"[Vision] Não foi possível abrir a câmera {camera_index}. "
                "Verifique se a webcam está conectada."
            )

        # Estado interno
        self.last_gesture:      GestureAction = GestureAction.NONE
        self.last_gesture_time: float         = 0.0
        self.current_frame                    = None
        self.gesture_label:     str           = ""
        self.confidence_count:  int           = 0   # Frames consecutivos com o mesmo gesto
        self.CONFIDENCE_THRESHOLD = 5               # Frames necessários para confirmar

    # ── Leitura de frame ──────────────────────────────────────────────

    def read_frame(self):
        """
        Lê um frame da webcam, processa landmarks e detecta o gesto.

        Returns:
            tuple: (frame_anotado, GestureAction confirmada ou NONE)
        """
        ret, frame = self.cap.read()
        if not ret:
            return None, GestureAction.NONE

        # Espelha horizontalmente para UX mais natural (como um espelho)
        frame = cv2.flip(frame, 1)

        # Converte BGR → RGB para o MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results   = self.hands.process(rgb_frame)

        detected_gesture = GestureAction.NONE

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Desenha os landmarks na imagem
                self.mp_draw.draw_landmarks(
                    frame,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_styles.get_default_hand_landmarks_style(),
                    self.mp_styles.get_default_hand_connections_style(),
                )
                # Classifica o gesto
                detected_gesture = self._classify_gesture(
                    hand_landmarks.landmark, frame.shape
                )

        # Sistema de confirmação por múltiplos frames consecutivos
        confirmed_gesture = self._confirm_gesture(detected_gesture)

        # Anotações visuais no frame
        self._draw_overlay(frame, detected_gesture, confirmed_gesture)
        self.current_frame = frame

        return frame, confirmed_gesture

    # ── Classificação de gestos ───────────────────────────────────────

    def _classify_gesture(self, landmarks, frame_shape) -> GestureAction:
        """
        Classifica o gesto a partir dos landmarks detectados.

        Estratégia:
        1. Conta quantos dedos (não-polegar) estão levantados
        2. Verifica gestos específicos para cada ação

        Args:
            landmarks: Lista de 21 landmarks normalizados (x, y, z)
            frame_shape: Dimensões do frame (altura, largura, canais)

        Returns:
            GestureAction correspondente ao gesto detectado.
        """
        fingers_up = self._count_fingers_up(landmarks)

        # ── Lógica de classificação ───────────────────────────────────
        #
        # Stand  → Punho fechado: nenhum dedo levantado
        # Double → Só o indicador levantado (apontar com 1 dedo)
        # Split  → Exatamente indicador + médio levantados (gesto V)
        # Hit    → Mão aberta: 4 ou mais dedos levantados

        if fingers_up == 0:
            return GestureAction.STAND

        if fingers_up == 1 and self._is_one_finger_point(landmarks):
            return GestureAction.DOUBLE

        if fingers_up == 2 and self._is_peace_sign(landmarks):
            return GestureAction.SPLIT

        if fingers_up >= 4:
            return GestureAction.HIT

        return GestureAction.NONE

    def _count_fingers_up(self, landmarks) -> int:
        """
        Conta quantos dedos (exceto polegar) estão levantados.

        Um dedo está levantado quando seu TIP está acima de seu PIP
        (coordenada Y menor, pois Y=0 está no topo da imagem).
        """
        count = 0
        for tip, pip in zip(FINGER_TIPS, FINGER_PIPS):
            if landmarks[tip].y < landmarks[pip].y:
                count += 1
        return count

    def _is_one_finger_point(self, landmarks) -> bool:
        """
        Detecta gesto de apontar com 1 dedo (só o indicador levantado).
        Usado para Double — muito mais distinto do punho (Stand) do que o polegar.
        """
        index_up    = landmarks[8].y  < landmarks[6].y
        middle_down = landmarks[12].y > landmarks[10].y
        ring_down   = landmarks[16].y > landmarks[14].y
        pinky_down  = landmarks[20].y > landmarks[18].y
        return index_up and middle_down and ring_down and pinky_down

    def _is_peace_sign(self, landmarks) -> bool:
        """
        Verifica gesto V (paz): indicador + médio levantados,
        anelar + mínimo fechados.
        """
        index_up  = landmarks[8].y  < landmarks[6].y   # Indicador
        middle_up = landmarks[12].y < landmarks[10].y  # Médio
        ring_down = landmarks[16].y > landmarks[14].y  # Anelar fechado
        pinky_down= landmarks[20].y > landmarks[18].y  # Mínimo fechado
        return index_up and middle_up and ring_down and pinky_down

    # ── Debounce / confirmação ────────────────────────────────────────

    def _confirm_gesture(self, gesture: GestureAction) -> GestureAction:
        """
        Confirma um gesto apenas se ele aparecer por N frames consecutivos
        E se tiver passado o tempo de debounce desde o último gesto aceito.

        Isso evita:
        - Falsos positivos de frames únicos
        - Ações repetidas enquanto a mão permanece parada
        """
        if gesture == GestureAction.NONE:
            self.confidence_count = 0
            return GestureAction.NONE

        if gesture == self.last_gesture:
            self.confidence_count += 1
        else:
            self.confidence_count = 1
            self.last_gesture = gesture

        # Ainda não atingiu o threshold de confiança
        if self.confidence_count < self.CONFIDENCE_THRESHOLD:
            return GestureAction.NONE

        # Verifica debounce temporal
        now = time.time()
        if now - self.last_gesture_time < self.DEBOUNCE_SECONDS:
            return GestureAction.NONE

        # Gesto confirmado!
        self.last_gesture_time = now
        self.confidence_count = 0
        return gesture

    # ── Overlay visual ────────────────────────────────────────────────

    def _draw_overlay(self, frame, raw: GestureAction, confirmed: GestureAction):
        """
        Desenha informações de debug e feedback de gesto no frame.
        """
        h, w = frame.shape[:2]

        # Fundo semi-transparente para o painel de gestos
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h - 120), (320, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        # Gesto detectado (raw)
        raw_label = raw.name if raw != GestureAction.NONE else "---"
        cv2.putText(
            frame, f"Gesto: {raw_label}",
            (10, h - 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1
        )

        # Gesto confirmado (dispara ação)
        if confirmed != GestureAction.NONE:
            cv2.putText(
                frame, f">> ACAO: {confirmed.name} <<",
                (10, h - 55), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
            )

        # Guia de gestos
        guide = "HIT(4+)  STAND(0)  DOUBLE(1)  SPLIT(2)"
        cv2.putText(
            frame, guide,
            (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 220, 255), 1
        )

    # ── Ciclo de vida ─────────────────────────────────────────────────

    def release(self):
        """Libera recursos da câmera e do MediaPipe."""
        self.cap.release()
        self.hands.close()
        print("[Vision] Câmera liberada.")

    def __repr__(self) -> str:
        return f"<GestureRecognizer último={self.last_gesture.name}>"
