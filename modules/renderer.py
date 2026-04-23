"""
renderer.py — Módulo de Interface e Renderização
BlackJack Vision

Responsabilidades:
- Carregar imagens de cartas da pasta Assets/Card/
- Renderizar o estado completo do jogo em uma janela OpenCV
- Exibir cartas do Dealer e do Jogador (incluindo múltiplas mãos)
- Mostrar saldo, aposta, estado e resultado na tela
- Integrar o frame da webcam no layout
- Exibir campo de entrada de aposta e mensagens de feedback
"""

import cv2
import numpy as np
import os
from typing import Optional
from modules.deck import Card
from modules.game import Hand, HandResult, GameState


# ─────────────────────────────────────────────
# Configurações visuais
# ─────────────────────────────────────────────

WINDOW_NAME  = "BlackJack Vision"
WINDOW_W     = 1280
WINDOW_H     = 720

# Dimensões de cada carta renderizada na mesa
CARD_W = 90
CARD_H = 130

# Cor de fundo da mesa (verde clássico de cassino)
TABLE_COLOR  = (34, 100, 34)
TEXT_COLOR   = (255, 255, 255)
ACCENT_COLOR = (0, 215, 255)    # Dourado para destaques
RED_COLOR    = (60, 60, 220)
GREEN_COLOR  = (60, 200, 60)

# Posições Y na mesa (eixo vertical)
DEALER_Y = 80
PLAYER_Y = 380

# Caminho base das cartas
ASSETS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Assets", "Card")
CARD_BACK_FILE = "back.png"     # Nome do arquivo de verso da carta


class GameRenderer:
    """
    Renderiza o jogo de Blackjack usando OpenCV como motor gráfico.

    O layout é dividido em duas regiões:
    - Painel esquerdo (900px): Mesa de jogo com cartas
    - Painel direito (380px): Feed da webcam + informações

    Cartas são carregadas sob demanda e armazenadas em cache para
    evitar leitura desnecessária de disco a cada frame.
    """

    def __init__(self, assets_path: str = ASSETS_PATH):
        self.assets_path = assets_path
        self._card_cache: dict[str, np.ndarray] = {}  # Cache de imagens de cartas
        self._back_img: Optional[np.ndarray] = None   # Cache do verso

        # Campo de texto da aposta (digitação pelo teclado)
        self.bet_input: str = ""
        self.input_active: bool = False

        # Frame atual da webcam
        self.webcam_frame: Optional[np.ndarray] = None

        self._load_back_image()

    # ── Carregamento de imagens ───────────────────────────────────────

    def _load_back_image(self) -> None:
        """Carrega e faz cache da imagem do verso da carta."""
        path = os.path.join(self.assets_path, CARD_BACK_FILE)
        img  = cv2.imread(path)
        if img is not None:
            self._back_img = cv2.resize(img, (CARD_W, CARD_H))
        else:
            # Fallback: retângulo cinza com "?" se o arquivo não for encontrado
            self._back_img = self._make_placeholder_card("?", (80, 80, 80))
            print(f"[Renderer] AVISO: verso da carta não encontrado em {path}")

    def load_card_image(self, card: Card) -> np.ndarray:
        """
        Carrega a imagem de uma carta específica, usando cache.

        Usa card.get_filename() como fonte de verdade para o nome do arquivo,
        garantindo o padrão <Valor><Naipe>.png (ex: ASpades.png, 10Hearts.png).

        Args:
            card (Card): Carta a ser carregada.

        Returns:
            np.ndarray: Imagem da carta redimensionada para CARD_W × CARD_H.
        """
        if not card.face_up:
            return self._back_img

        filename = card.get_filename()

        # Cache hit
        if filename in self._card_cache:
            return self._card_cache[filename]

        # Carrega do disco
        path = os.path.join(self.assets_path, filename)
        img  = cv2.imread(path)

        if img is None:
            print(f"[Renderer] AVISO: imagem não encontrada: {path}")
            img = self._make_placeholder_card(
                f"{card.value}\n{card.suit[0]}", (255, 255, 255)
            )
        else:
            img = cv2.resize(img, (CARD_W, CARD_H))

        self._card_cache[filename] = img
        return img

    def _make_placeholder_card(self, label: str, bg_color: tuple) -> np.ndarray:
        """
        Cria uma carta placeholder quando o arquivo de imagem não é encontrado.
        Útil durante o desenvolvimento antes de ter todas as artes.
        """
        img = np.full((CARD_H, CARD_W, 3), bg_color, dtype=np.uint8)
        cv2.rectangle(img, (2, 2), (CARD_W - 3, CARD_H - 3), (0, 0, 0), 2)
        cv2.putText(
            img, label, (10, CARD_H // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2
        )
        return img

    # ── Renderização principal ────────────────────────────────────────

    def render(
        self,
        dealer_hand: Hand,
        player_hands: list,
        active_hand_index: int,
        balance: int,
        current_bet: int,
        state: GameState,
        bet_message: str = "",
        webcam_frame=None,
        gesture_label: str = "",
        rebuy_mode: bool = False,
        rebuy_input: str = "",
    ) -> np.ndarray:
        """
        Gera o frame completo da interface do jogo.

        Args:
            dealer_hand (Hand):         Mão do Dealer
            player_hands (list[Hand]):  Lista de mãos do Jogador
            active_hand_index (int):    Índice da mão ativa
            balance (int):              Saldo atual do jogador
            current_bet (int):          Aposta da rodada atual
            state (GameState):          Estado da rodada
            bet_message (str):          Mensagem de feedback da aposta
            webcam_frame:               Frame BGR da webcam
            gesture_label (str):        Nome do último gesto confirmado

        Returns:
            np.ndarray: Frame BGR completo para exibição.
        """
        # Canvas principal
        canvas = np.full((WINDOW_H, WINDOW_W, 3), TABLE_COLOR, dtype=np.uint8)

        # ── Divisória visual entre mesa e painel lateral
        cv2.line(canvas, (900, 0), (900, WINDOW_H), (20, 60, 20), 3)

        # ── Mesa de jogo (lado esquerdo)
        self._render_table(
            canvas, dealer_hand, player_hands,
            active_hand_index, state
        )

        # ── Painel lateral (lado direito)
        self._render_side_panel(
            canvas, balance, current_bet, state,
            bet_message, webcam_frame, gesture_label,
            rebuy_mode, rebuy_input,
        )

        return canvas

    # ── Renderização da mesa ──────────────────────────────────────────

    def _render_table(
        self,
        canvas: np.ndarray,
        dealer_hand: Hand,
        player_hands: list,
        active_hand_index: int,
        state: GameState,
    ) -> None:
        """Renderiza as cartas e valores na área da mesa."""

        # ── Dealer ──────────────────────────────────────────────────
        self._draw_label(canvas, "DEALER", 30, DEALER_Y - 10)
        if dealer_hand.cards:
            dealer_val = (
                dealer_hand.calculate_value_full()
                if state in (GameState.DEALER_TURN, GameState.ROUND_OVER)
                else dealer_hand.calculate_value()
            )
            self._draw_label(canvas, f"Total: {dealer_val}", 120, DEALER_Y - 10,
                             color=(200, 200, 200))
            self._draw_hand(canvas, dealer_hand, x_start=30, y=DEALER_Y)

        # ── Jogador ──────────────────────────────────────────────────
        self._draw_label(canvas, "JOGADOR", 30, PLAYER_Y - 30)

        if player_hands:
            # Distribui as mãos horizontalmente
            hand_spacing = min(240, 840 // len(player_hands))
            for i, hand in enumerate(player_hands):
                x_start = 30 + i * hand_spacing
                is_active = (i == active_hand_index) and (state == GameState.PLAYER_TURN)

                # Destaca a mão ativa
                if is_active:
                    cv2.rectangle(
                        canvas,
                        (x_start - 8, PLAYER_Y - 8),
                        (x_start + CARD_W * 5 + 8, PLAYER_Y + CARD_H + 30),
                        ACCENT_COLOR, 2
                    )

                self._draw_hand(canvas, hand, x_start=x_start, y=PLAYER_Y)

                # Valor e resultado da mão
                hand_val  = hand.calculate_value()
                hand_info = f"{hand_val}"
                if hand.is_soft():
                    hand_info += " (soft)"

                val_color = TEXT_COLOR
                if hand.result != HandResult.PENDING:
                    hand_info += f"  {self._result_label(hand.result)}"
                    val_color = self._result_color(hand.result)

                self._draw_label(
                    canvas, hand_info,
                    x_start, PLAYER_Y + CARD_H + 12,
                    color=val_color, scale=0.55
                )

                # Aposta desta mão
                self._draw_label(
                    canvas, f"Aposta: {hand.bet}",
                    x_start, PLAYER_Y + CARD_H + 32,
                    color=(200, 200, 100), scale=0.45
                )

        # ── Resultado global (ROUND_OVER) ────────────────────────────
        if state == GameState.ROUND_OVER:
            self._draw_round_over_banner(canvas, player_hands)

    def _draw_hand(self, canvas: np.ndarray, hand: Hand, x_start: int, y: int) -> None:
        """Renderiza as cartas de uma mão na posição (x_start, y)."""
        gap = 8  # Sobreposição entre cartas
        for j, card in enumerate(hand.cards):
            img = self.load_card_image(card)
            x   = x_start + j * (CARD_W - gap * 4 + 4)
            self._blit(canvas, img, x, y)

    def _draw_round_over_banner(self, canvas: np.ndarray, hands: list) -> None:
        """Exibe um banner central com o resultado final da rodada."""
        overlay = canvas.copy()
        cv2.rectangle(overlay, (150, 270), (750, 370), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, canvas, 0.3, 0, canvas)

        # Verifica resultados para mensagem central
        results = [h.result for h in hands]
        if HandResult.PLAYER_BLACKJACK in results:
            msg, color = "BLACKJACK!", ACCENT_COLOR
        elif all(r == HandResult.PLAYER_BUST for r in results):
            msg, color = "BUST  Voce perdeu!", RED_COLOR
        elif all(r == HandResult.DEALER_WIN for r in results):
            msg, color = "Dealer venceu.", RED_COLOR
        elif all(r == HandResult.PUSH for r in results):
            msg, color = "EMPATE  Aposta devolvida.", TEXT_COLOR
        elif all(r == HandResult.DEALER_BUST for r in results):
            msg, color = "Dealer busted! Voce venceu!", GREEN_COLOR
        elif HandResult.PLAYER_WIN in results or HandResult.DEALER_BUST in results:
            msg, color = "Voce venceu!", GREEN_COLOR
        else:
            msg, color = "Rodada encerrada.", TEXT_COLOR

        cv2.putText(canvas, msg, (170, 325),
                    cv2.FONT_HERSHEY_DUPLEX, 1.1, color, 2)
        cv2.putText(canvas, "Pressione [N] para nova rodada",
                    (170, 355), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)

    # ── Painel lateral ────────────────────────────────────────────────

    def _render_side_panel(
        self,
        canvas: np.ndarray,
        balance: int,
        current_bet: int,
        state: GameState,
        bet_message: str,
        webcam_frame,
        gesture_label: str,
        rebuy_mode: bool = False,
        rebuy_input: str = "",
    ) -> None:
        """Renderiza o painel direito: webcam + HUD de informações."""

        panel_x = 905  # Margem esquerda do painel

        # ── Feed da webcam ───────────────────────────────────────────
        if webcam_frame is not None:
            cam_h, cam_w = webcam_frame.shape[:2]
            target_w = WINDOW_W - panel_x - 5
            target_h = int(target_w * cam_h / cam_w)
            cam_resized = cv2.resize(webcam_frame, (target_w, target_h))
            self._blit(canvas, cam_resized, panel_x, 5)
            cam_bottom = 5 + target_h + 10
        else:
            # Placeholder quando câmera não está disponível
            cam_rect = np.full((200, WINDOW_W - panel_x - 5, 3), (30, 30, 30), dtype=np.uint8)
            cv2.putText(cam_rect, "Camera nao disponivel",
                        (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)
            self._blit(canvas, cam_rect, panel_x, 5)
            cam_bottom = 215

        # ── Informações do jogo ──────────────────────────────────────
        info_y = cam_bottom

        # Saldo
        cv2.putText(canvas, f"Saldo: {balance} fichas",
                    (panel_x, info_y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.65, ACCENT_COLOR, 2)
        info_y += 30

        # Aposta atual
        cv2.putText(canvas, f"Aposta: {current_bet}",
                    (panel_x, info_y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, TEXT_COLOR, 1)
        info_y += 25

        # Estado da rodada
        state_labels = {
            GameState.WAITING_BET: "Faca sua aposta",
            GameState.DEALING:     "Distribuindo...",
            GameState.PLAYER_TURN: "Sua vez!",
            GameState.DEALER_TURN: "Dealer jogando...",
            GameState.ROUND_OVER:  "Rodada encerrada",
        }
        cv2.putText(canvas, state_labels.get(state, ""),
                    (panel_x, info_y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (150, 220, 255), 1)
        info_y += 35

        # Último gesto detectado
        if gesture_label:
            cv2.putText(canvas, f"Gesto: {gesture_label}",
                        (panel_x, info_y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, GREEN_COLOR, 1)
            info_y += 25

        # ── Campo de aposta / Rebuy ──────────────────────────────────
        if state == GameState.WAITING_BET:
            info_y += 10
            if rebuy_mode:
                cv2.putText(canvas, "--- SEM FICHAS ---",
                            (panel_x, info_y), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, RED_COLOR, 2)
                info_y += 25
                cv2.putText(canvas, "Rebuy  quanto deseja adicionar?",
                            (panel_x, info_y), cv2.FONT_HERSHEY_SIMPLEX,
                            0.43, (200, 200, 200), 1)
                info_y += 22
                cv2.putText(canvas, "Digite + [Enter]:",
                            (panel_x, info_y), cv2.FONT_HERSHEY_SIMPLEX,
                            0.43, (200, 200, 200), 1)
                info_y += 25
                cv2.rectangle(canvas, (panel_x, info_y - 20),
                              (WINDOW_W - 10, info_y + 8), RED_COLOR, 2)
                cv2.putText(canvas, rebuy_input + "|",
                            (panel_x + 5, info_y), cv2.FONT_HERSHEY_SIMPLEX,
                            0.65, TEXT_COLOR, 1)
                info_y += 30
            else:
                cv2.putText(canvas, "Digite a aposta + [Enter]:",
                            (panel_x, info_y), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (200, 200, 200), 1)
                info_y += 25
                box_color = ACCENT_COLOR if self.input_active else (150, 150, 150)
                cv2.rectangle(canvas, (panel_x, info_y - 20),
                              (WINDOW_W - 10, info_y + 8), box_color, 2)
                cv2.putText(canvas, self.bet_input + "|",
                            (panel_x + 5, info_y), cv2.FONT_HERSHEY_SIMPLEX,
                            0.65, TEXT_COLOR, 1)
                info_y += 30

        # ── Mensagem de feedback ─────────────────────────────────────
        if bet_message:
            # Quebra mensagem longa em duas linhas
            words = bet_message.split()
            line1, line2 = "", ""
            for w in words:
                if len(line1) < 22:
                    line1 += w + " "
                else:
                    line2 += w + " "
            cv2.putText(canvas, line1.strip(),
                        (panel_x, info_y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.48, (220, 220, 100), 1)
            if line2.strip():
                cv2.putText(canvas, line2.strip(),
                            (panel_x, info_y + 20), cv2.FONT_HERSHEY_SIMPLEX,
                            0.48, (220, 220, 100), 1)
            info_y += 45

        # ── Guia de controles ────────────────────────────────────────
        guide_y = WINDOW_H - 130
        cv2.putText(canvas, "CONTROLES:",
                    (panel_x, guide_y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.48, (150, 220, 255), 1)
        controls = [
            "Mao aberta   Hit",
            "Punho        Stand",
            "1 dedo       Double",
            "Dois dedos   Split",
            "[N] Nova rodada  [Q] Sair",
        ]
        for i, ctrl in enumerate(controls):
            cv2.putText(canvas, ctrl,
                        (panel_x, guide_y + 20 + i * 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)

    # ── Auxiliares visuais ────────────────────────────────────────────

    def _blit(self, canvas: np.ndarray, img: np.ndarray, x: int, y: int) -> None:
        """Cola uma imagem no canvas na posição (x, y), com clipagem de bordas."""
        h, w = img.shape[:2]
        ch, cw = canvas.shape[:2]
        x1, y1 = max(x, 0), max(y, 0)
        x2, y2 = min(x + w, cw), min(y + h, ch)
        ix1, iy1 = x1 - x, y1 - y
        ix2, iy2 = ix1 + (x2 - x1), iy1 + (y2 - y1)
        if x2 > x1 and y2 > y1:
            canvas[y1:y2, x1:x2] = img[iy1:iy2, ix1:ix2]

    def _draw_label(
        self,
        canvas: np.ndarray,
        text: str,
        x: int,
        y: int,
        color: tuple = TEXT_COLOR,
        scale: float = 0.6,
        thickness: int = 1,
    ) -> None:
        """Desenha texto no canvas."""
        cv2.putText(canvas, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, color, thickness)

    def _result_label(self, result: HandResult) -> str:
        labels = {
            HandResult.PLAYER_BLACKJACK: "BLACKJACK!",
            HandResult.PLAYER_WIN:       "GANHOU",
            HandResult.DEALER_WIN:       "perdeu",
            HandResult.PUSH:             "EMPATE",
            HandResult.PLAYER_BUST:      "BUST",
            HandResult.DEALER_BUST:      "Dealer busted!",
        }
        return labels.get(result, "")

    def _result_color(self, result: HandResult) -> tuple:
        wins  = {HandResult.PLAYER_BLACKJACK, HandResult.PLAYER_WIN, HandResult.DEALER_BUST}
        loses = {HandResult.PLAYER_BUST, HandResult.DEALER_WIN}
        if result in wins:
            return GREEN_COLOR
        if result in loses:
            return RED_COLOR
        return TEXT_COLOR  # PUSH

    def process_key(self, key: int) -> str:
        """
        Processa teclas digitadas para o campo de aposta.

        Args:
            key (int): Código de tecla retornado por cv2.waitKey()

        Returns:
            str: "submit" se Enter foi pressionado, "" caso contrário.
        """
        if key == 13:  # Enter
            return "submit"
        if key == 8 and self.bet_input:  # Backspace
            self.bet_input = self.bet_input[:-1]
        elif 48 <= key <= 57:  # Dígitos 0-9
            if len(self.bet_input) < 6:
                self.bet_input += chr(key)
        return ""

    def clear_bet_input(self) -> None:
        """Limpa o campo de aposta após confirmação."""
        self.bet_input = ""
