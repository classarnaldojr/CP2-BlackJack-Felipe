"""
main.py — Orquestrador Principal
BlackJack Vision

Este módulo une todos os outros e implementa o loop principal do jogo.

Fluxo de execução:
1. Inicializa todos os módulos (Deck, Game, Betting, Renderer, Vision)
2. Entra no loop principal (30 fps target)
3. A cada frame:
   a. Lê frame da webcam + detecta gesto
   b. Processa entradas de teclado
   c. Despacha ações ao BlackjackGame conforme estado atual
   d. Renderiza o canvas completo
   e. Exibe na janela OpenCV
4. Ao encerrar, libera recursos

Controles:
    [Gestos]   → Ações do jogo (Hit, Stand, Double, Split)
    [N]        → Nova rodada
    [Q / ESC]  → Encerrar
    [Teclado]  → Digitar valor da aposta + Enter
"""

import cv2
import sys
import time
import traceback

from modules.deck     import Deck
from modules.game     import BlackjackGame, GameState, HandResult
from modules.betting  import BettingManager, MIN_BET
from modules.renderer import GameRenderer, WINDOW_NAME, WINDOW_W, WINDOW_H
from modules.vision   import GestureRecognizer, GestureAction


# ─────────────────────────────────────────────
# Inicialização
# ─────────────────────────────────────────────

def initialize_modules():
    """
    Instancia todos os módulos do jogo.
    Retorna uma tupla com cada módulo inicializado.
    """
    print("[Main] Inicializando BlackJack Vision...")

    game     = BlackjackGame()
    betting  = BettingManager()
    renderer = GameRenderer()

    try:
        vision = GestureRecognizer(camera_index=0)
        print("[Main] Câmera inicializada com sucesso.")
    except RuntimeError as e:
        print(f"[Main] AVISO: {e}")
        print("[Main] O jogo rodará sem detecção de gestos (modo teclado).")
        vision = None

    return game, betting, renderer, vision


# ─────────────────────────────────────────────
# Despacho de ações do jogo
# ─────────────────────────────────────────────

def dispatch_action(action: GestureAction, game: BlackjackGame, betting: BettingManager) -> str:
    """
    Executa uma ação do jogador no estado correto do jogo.

    Args:
        action  (GestureAction):   Ação detectada (gesto ou tecla)
        game    (BlackjackGame):   Instância do motor do jogo
        betting (BettingManager):  Gerenciador de apostas

    Returns:
        str: Mensagem de feedback para exibir na UI.
    """
    if game.state != GameState.PLAYER_TURN:
        return ""

    hand = game.active_hand
    if hand is None:
        return ""

    msg = ""

    if action == GestureAction.HIT:
        game.player_hit()
        msg = "HIT"

    elif action == GestureAction.STAND:
        game.player_stand()
        msg = "STAND"

    elif action == GestureAction.DOUBLE:
        if not hand.can_double():
            return "Double nao permitido agora."
        # Cobra o valor extra da aposta
        if not betting.charge_extra(hand.bet):
            return "Saldo insuficiente para Double."
        game.player_double()
        msg = "DOUBLE"

    elif action == GestureAction.SPLIT:
        if not hand.can_split():
            return "Split nao permitido: valores diferentes."
        # Cobra o valor da aposta para a segunda mão
        if not betting.charge_extra(hand.bet):
            return "Saldo insuficiente para Split."
        game.player_split()
        msg = "SPLIT jogando 2 maos"

    # Após o turno terminar, liquida as apostas
    if game.state == GameState.ROUND_OVER:
        total = betting.settle_all_hands(game.player_hands)
        msg = betting.message

    return msg


def start_new_round(game: BlackjackGame, betting: BettingManager, renderer: GameRenderer) -> str:
    """
    Inicia uma nova rodada com a aposta digitada pelo jogador.

    Returns:
        str: Mensagem de feedback.
    """
    raw_input = renderer.bet_input.strip()

    if not raw_input:
        return "Digite um valor de aposta e pressione Enter."

    try:
        bet_amount = int(raw_input)
    except ValueError:
        return "Valor invalido. Digite apenas numeros."

    valid, err_msg = betting.validate_bet(bet_amount)
    if not valid:
        return err_msg

    # Desconta a aposta e inicia a rodada
    betting.place_bet(bet_amount)
    renderer.clear_bet_input()
    game.reset()
    game.start_round(bet=bet_amount)

    # Se a rodada terminou imediatamente (blackjack natural), liquida
    if game.state == GameState.ROUND_OVER:
        betting.settle_all_hands(game.player_hands)
        return betting.message

    return f"Rodada iniciada! Aposta: {bet_amount} fichas."


# ─────────────────────────────────────────────
# Loop principal
# ─────────────────────────────────────────────

def main():
    game, betting, renderer, vision = initialize_modules()

    # Configura janela OpenCV
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, WINDOW_W, WINDOW_H)

    feedback_msg  = "Bem-vindo! Digite sua aposta para comecar."
    gesture_label = ""
    webcam_frame  = None

    # ── Turno do dealer: animação carta por carta ─────────────────────
    DEALER_CARD_DELAY = 1.0   # segundos entre cada carta do dealer
    dealer_card_timer = 0.0   # timestamp da última carta revelada

    # ── Rebuy ─────────────────────────────────────────────────────────
    rebuy_mode  = False
    rebuy_input = ""

    print("[Main] Loop principal iniciado. Pressione [Q] ou [ESC] para sair.")

    while True:
        # ── 1. Leitura da webcam e detecção de gesto ──────────────────
        confirmed_gesture = GestureAction.NONE

        if vision is not None:
            webcam_frame, confirmed_gesture = vision.read_frame()
            if confirmed_gesture != GestureAction.NONE:
                gesture_label = confirmed_gesture.name

        # Salva estado antes de qualquer ação (para detectar transições)
        state_before = game.state

        # ── 2. Processar ação de gesto ────────────────────────────────
        if confirmed_gesture != GestureAction.NONE:
            if game.state == GameState.PLAYER_TURN:
                msg = dispatch_action(confirmed_gesture, game, betting)
                if msg:
                    feedback_msg = msg

        # ── 3. Renderizar frame ───────────────────────────────────────
        canvas = renderer.render(
            dealer_hand       = game.dealer_hand,
            player_hands      = game.player_hands,
            active_hand_index = game.active_hand_index,
            balance           = betting.balance,
            current_bet       = betting.current_bet,
            state             = game.state,
            bet_message       = feedback_msg,
            webcam_frame      = webcam_frame,
            gesture_label     = gesture_label,
            rebuy_mode        = rebuy_mode,
            rebuy_input       = rebuy_input,
        )

        cv2.imshow(WINDOW_NAME, canvas)

        # ── 4. Processar teclas ───────────────────────────────────────
        key = cv2.waitKey(30) & 0xFF

        # Sair
        if key in (ord('q'), ord('Q'), 27):
            break

        # Nova rodada
        if key in (ord('n'), ord('N')):
            if game.state in (GameState.WAITING_BET, GameState.ROUND_OVER):
                game.state    = GameState.WAITING_BET
                feedback_msg  = "Digite sua aposta."
                gesture_label = ""

        # Enter — submete aposta ou confirma rebuy
        if key == 13:
            if rebuy_mode:
                try:
                    amount = int(rebuy_input.strip()) if rebuy_input.strip() else 0
                    if betting.add_funds(amount):
                        rebuy_mode  = False
                        rebuy_input = ""
                        feedback_msg = betting.message
                    else:
                        feedback_msg = betting.message
                except ValueError:
                    feedback_msg = "Valor invalido para rebuy."
            elif game.state == GameState.WAITING_BET:
                feedback_msg = start_new_round(game, betting, renderer)

        # Entrada de dígitos: rebuy ou aposta normal
        if rebuy_mode:
            if key == 8 and rebuy_input:
                rebuy_input = rebuy_input[:-1]
            elif 48 <= key <= 57 and len(rebuy_input) < 6:
                rebuy_input += chr(key)
        elif game.state == GameState.WAITING_BET:
            renderer.process_key(key)

        # ── Teclas de ação manual (fallback sem gestos) ───────────────
        if game.state == GameState.PLAYER_TURN:
            action_map = {
                ord('h'): GestureAction.HIT,
                ord('H'): GestureAction.HIT,
                ord('s'): GestureAction.STAND,
                ord('S'): GestureAction.STAND,
                ord('d'): GestureAction.DOUBLE,
                ord('D'): GestureAction.DOUBLE,
                ord('p'): GestureAction.SPLIT,
                ord('P'): GestureAction.SPLIT,
            }
            if key in action_map:
                msg = dispatch_action(action_map[key], game, betting)
                if msg:
                    feedback_msg = msg

        # ── Detectar início do turno do dealer ────────────────────────
        if game.state == GameState.DEALER_TURN and state_before != GameState.DEALER_TURN:
            dealer_card_timer = time.time()  # 1s de pausa antes da primeira carta extra

        # ── Turno do dealer: uma carta por segundo ────────────────────
        if game.state == GameState.DEALER_TURN:
            now = time.time()
            if now - dealer_card_timer >= DEALER_CARD_DELAY:
                dealer_card_timer = now
                still_needs_cards = game.dealer_deal_one()
                if not still_needs_cards:
                    # Dealer encerrou — liquida apostas
                    betting.settle_all_hands(game.player_hands)
                    feedback_msg = betting.message
                    if betting.is_broke():
                        feedback_msg += " Pressione [N] para rebuy."

        # ── Verificar saldo zerado → ativar rebuy ─────────────────────
        if betting.is_broke() and game.state == GameState.WAITING_BET and not rebuy_mode:
            rebuy_mode   = True
            rebuy_input  = ""
            feedback_msg = "Sem fichas! Digite o rebuy + [Enter]."

    # ── 5. Encerramento ───────────────────────────────────────────────
    print("[Main] Encerrando BlackJack Vision...")
    if vision is not None:
        vision.release()
    cv2.destroyAllWindows()
    print("[Main] Ate a proxima!")


# ─────────────────────────────────────────────
# Ponto de entrada
# ─────────────────────────────────────────────

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Main] Interrompido pelo usuário.")
        cv2.destroyAllWindows()
    except Exception as e:
        print(f"[Main] Erro inesperado: {e}")
        traceback.print_exc()
        cv2.destroyAllWindows()
        sys.exit(1)
