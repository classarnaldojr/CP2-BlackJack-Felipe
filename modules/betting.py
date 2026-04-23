"""
betting.py — Módulo de Saldo e Apostas
BlackJack Vision

Responsabilidades:
- Controlar o saldo do jogador (começa com 500 fichas)
- Validar apostas (mínimo, máximo, saldo disponível)
- Calcular e aplicar pagamentos de acordo com o resultado da mão
- Suportar pagamento de Blackjack natural (3:2)
"""

from modules.game import Hand, HandResult


# ─────────────────────────────────────────────
# Constantes de aposta
# ─────────────────────────────────────────────

STARTING_BALANCE  = 500    # Fichas iniciais do jogador
MIN_BET           = 25     # Aposta mínima por rodada
MAX_BET           = 10000    # Aposta máxima por rodada
BLACKJACK_RATIO   = 1.5    # Blackjack natural paga 3:2


class BettingManager:
    """
    Gerencia o saldo e as apostas do jogador.

    O saldo nunca fica negativo: o sistema bloqueia apostas inválidas
    antes de descontar qualquer valor.
    """

    def __init__(self, starting_balance: int = STARTING_BALANCE):
        self.balance: int = starting_balance
        self.current_bet: int = 0
        self.message: str = ""  # Feedback textual para a UI

    # ── Validação e cobrança ──────────────────────────────────────────

    def validate_bet(self, amount: int) -> tuple[bool, str]:
        """
        Verifica se um valor de aposta é válido.

        Returns:
            (True, "")              se válida
            (False, motivo)         se inválida
        """
        if amount < MIN_BET:
            return False, f"Aposta minima: {MIN_BET} fichas."
        if amount > MAX_BET:
            return False, f"Aposta maxima: {MAX_BET} fichas."
        if amount > self.balance:
            return False, f"Saldo insuficiente. Voce tem {self.balance} fichas."
        return True, ""

    def place_bet(self, amount: int) -> bool:
        """
        Desconta a aposta do saldo e registra o valor atual.

        Args:
            amount (int): Valor a ser apostado.

        Returns:
            bool: True se a aposta foi aceita, False caso contrário.
        """
        valid, msg = self.validate_bet(amount)
        if not valid:
            self.message = msg
            return False

        self.balance -= amount
        self.current_bet = amount
        self.message = f"Aposta de {amount} fichas realizada."
        return True

    def charge_extra(self, amount: int) -> bool:
        """
        Cobra uma quantia adicional (usada no Double e no Split).

        Args:
            amount (int): Valor extra a descontar do saldo.

        Returns:
            bool: True se foi possível cobrar, False se saldo insuficiente.
        """
        if amount > self.balance:
            self.message = "Saldo insuficiente para esta acao."
            return False
        self.balance -= amount
        return True

    # ── Pagamentos ────────────────────────────────────────────────────

    def settle_hand(self, hand: Hand) -> int:
        """
        Calcula e aplica o pagamento de uma mão ao saldo do jogador.

        Tabela de pagamentos:
        ┌──────────────────┬──────────────────────────────────┐
        │ Resultado        │ Retorno ao saldo                 │
        ├──────────────────┼──────────────────────────────────┤
        │ PLAYER_BLACKJACK │ aposta + aposta × 1.5            │
        │ PLAYER_WIN       │ aposta × 2 (aposta + ganho)      │
        │ DEALER_BUST      │ aposta × 2                       │
        │ PUSH             │ aposta (devolução)                │
        │ PLAYER_BUST      │ 0 (já perdeu ao apostar)         │
        │ DEALER_WIN       │ 0                                 │
        └──────────────────┴──────────────────────────────────┘

        Args:
            hand (Hand): Mão com resultado já definido e aposta registrada.

        Returns:
            int: Valor efetivamente adicionado ao saldo.
        """
        result = hand.result
        bet = hand.bet
        payout = 0

        if result == HandResult.PLAYER_BLACKJACK:
            # 3:2 → devolve a aposta + 1.5× a aposta
            payout = bet + int(bet * BLACKJACK_RATIO)
            self.message = f"Blackjack! +{int(bet * BLACKJACK_RATIO)} fichas."

        elif result in (HandResult.PLAYER_WIN, HandResult.DEALER_BUST):
            payout = bet * 2
            self.message = f"Voce venceu! +{bet} fichas."

        elif result == HandResult.PUSH:
            payout = bet
            self.message = "Empate. Aposta devolvida."

        elif result in (HandResult.PLAYER_BUST, HandResult.DEALER_WIN):
            payout = 0
            self.message = "Voce perdeu."

        self.balance += payout
        return payout

    def settle_all_hands(self, hands: list) -> int:
        """
        Processa o pagamento de todas as mãos (útil após Split).

        Args:
            hands (list[Hand]): Lista de mãos do jogador.

        Returns:
            int: Total adicionado ao saldo nesta rodada.
        """
        total_payout = 0
        for hand in hands:
            total_payout += self.settle_hand(hand)
        return total_payout

    # ── Informações ──────────────────────────────────────────────────

    def add_funds(self, amount: int) -> bool:
        """
        Adiciona fichas ao saldo (rebuy).

        Args:
            amount (int): Quantidade de fichas a adicionar.

        Returns:
            bool: True se válido, False se amount <= 0.
        """
        if amount <= 0:
            self.message = "Valor de rebuy deve ser positivo."
            return False
        self.balance += amount
        self.message = f"Rebuy de {amount} fichas! Saldo: {self.balance}."
        return True

    def can_afford(self, amount: int) -> bool:
        """Verifica se o jogador tem saldo para determinado valor."""
        return self.balance >= amount

    def is_broke(self) -> bool:
        """Retorna True se o jogador não tiver saldo nem para a aposta mínima."""
        return self.balance < MIN_BET

    def __repr__(self) -> str:
        return f"<BettingManager saldo={self.balance} | aposta={self.current_bet}>"
