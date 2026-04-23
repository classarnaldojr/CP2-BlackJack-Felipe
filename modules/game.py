"""
game.py — Módulo de Regras do Blackjack
BlackJack Vision

Responsabilidades:
- Calcular o valor total de uma mão (com tratamento de Soft Ace)
- Verificar blackjack natural, bust e vitória
- Controlar o turno do Dealer (regra: comprar até >= 17)
- Gerenciar múltiplas mãos (Split)
- Controlar o estado global da rodada
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional
from modules.deck import Card, Deck


# ─────────────────────────────────────────────
# Estados possíveis do jogo
# ─────────────────────────────────────────────

class GameState(Enum):
    """
    Máquina de estados da rodada.
    Evita que ações inválidas sejam executadas fora do momento certo.
    """
    WAITING_BET  = auto()   # Aguardando o jogador informar a aposta
    DEALING      = auto()   # Distribuindo as cartas iniciais
    PLAYER_TURN  = auto()   # Jogador tomando decisões
    DEALER_TURN  = auto()   # Dealer executando sua lógica
    ROUND_OVER   = auto()   # Resultado exibido, aguardando nova rodada


# ─────────────────────────────────────────────
# Resultado de uma mão
# ─────────────────────────────────────────────

class HandResult(Enum):
    PENDING         = auto()   # Rodada ainda em andamento
    PLAYER_BLACKJACK = auto()  # Blackjack natural do jogador (paga 3:2)
    PLAYER_WIN      = auto()   # Jogador vence normalmente
    DEALER_WIN      = auto()   # Dealer vence
    PUSH            = auto()   # Empate (devolve a aposta)
    PLAYER_BUST     = auto()   # Jogador estourou 21
    DEALER_BUST     = auto()   # Dealer estourou 21 (jogador vence)


# ─────────────────────────────────────────────
# Estrutura de uma mão
# ─────────────────────────────────────────────

@dataclass
class Hand:
    """
    Representa uma mão de cartas (do jogador ou do dealer).

    Suporta múltiplas mãos via Split: cada mão é independente,
    com suas próprias cartas, aposta e resultado.

    Atributos:
        cards   (list[Card]): Cartas na mão
        bet     (int):        Valor apostado nesta mão
        result  (HandResult): Resultado após a rodada
        doubled (bool):       Se True, o Double foi aplicado nesta mão
        done    (bool):       Se True, o jogador encerrou a ação nesta mão
    """
    cards:   list = field(default_factory=list)
    bet:     int  = 0
    result:  HandResult = HandResult.PENDING
    doubled: bool = False
    done:    bool = False

    # ── Cálculo do valor ──────────────────────────────────────────────

    def calculate_value(self) -> int:
        """
        Calcula o valor total da mão com tratamento de Soft Ace.

        Regra de Soft Cards:
        - Ás começa valendo 11
        - Se o total ultrapassar 21 e houver Ás contando como 11,
          ele é convertido para 1 (subtrai 10 do total)
        - Isso ocorre para cada Ás na mão, individualmente

        Exemplos:
            [A, 7]        → 18  (Soft 18)
            [A, 7, 6]     → 14  (Soft convertido: 11+7+6=24 > 21, usa 1+7+6=14)
            [A, A]        → 12  (11+1, o segundo As vira 1)
            [A, A, 9]     → 21  (11+1+9)
            [10, A]       → 21  (Blackjack natural)
        """
        total = 0
        aces_as_eleven = 0

        for card in self.cards:
            if not card.face_up:
                continue  # Carta oculta não conta no display do jogador
            val = card.get_numeric_value()
            total += val
            if card.value == "A":
                aces_as_eleven += 1

        # Converte Ases de 11 para 1 enquanto o total ultrapassar 21
        while total > 21 and aces_as_eleven > 0:
            total -= 10
            aces_as_eleven -= 1

        return total

    def calculate_value_full(self) -> int:
        """
        Calcula o valor total contando TODAS as cartas (incluindo ocultas).
        Usado internamente pelo Dealer para decidir suas ações.
        """
        total = 0
        aces_as_eleven = 0

        for card in self.cards:
            val = card.get_numeric_value()
            total += val
            if card.value == "A":
                aces_as_eleven += 1

        while total > 21 and aces_as_eleven > 0:
            total -= 10
            aces_as_eleven -= 1

        return total

    # ── Verificações de estado ────────────────────────────────────────

    def is_bust(self) -> bool:
        """Retorna True se o total visível ultrapassar 21."""
        return self.calculate_value() > 21

    def is_blackjack(self) -> bool:
        """
        Blackjack natural: exatamente 2 cartas totalizando 21.
        Só é possível na distribuição inicial.
        """
        return len(self.cards) == 2 and self.calculate_value_full() == 21

    def is_soft(self) -> bool:
        """
        Retorna True se a 
          for 'soft' (contém um Ás valendo 11).
        Útil para informação visual ao jogador.
        """
        total = sum(c.get_numeric_value() for c in self.cards if c.face_up)
        aces = sum(1 for c in self.cards if c.value == "A" and c.face_up)
        return aces > 0 and total <= 21

    def can_split(self) -> bool:
        """
        Split permitido apenas quando:
        - A mão tem exatamente 2 cartas
        - Ambas têm o mesmo valor nominal
        """
        return (
            len(self.cards) == 2
            and self.cards[0].value == self.cards[1].value
        )

    def can_double(self) -> bool:
        """
        Double permitido apenas na primeira decisão (2 cartas na mão).
        """
        return len(self.cards) == 2

    def reveal_hidden(self) -> None:
        """Vira todas as cartas ocultas da mão para cima."""
        for card in self.cards:
            card.face_up = True

    def __repr__(self) -> str:
        return f"<Hand {self.cards} = {self.calculate_value()} | aposta={self.bet}>"


# ─────────────────────────────────────────────
# Motor do jogo
# ─────────────────────────────────────────────

class BlackjackGame:
    """
    Orquestra toda a lógica de uma partida de Blackjack.

    Gerencia:
    - O sapato de cartas (Deck com 4 decks)
    - As mãos do Dealer e do Jogador (incluindo múltiplas mãos por Split)
    - O estado atual da rodada (GameState)
    - Comunicação de resultados para o módulo de apostas
    """

    DEALER_STAND_VALUE = 17  # Dealer para de comprar ao atingir 17 ou mais

    def __init__(self):
        self.deck = Deck()
        self.dealer_hand: Hand = Hand()
        self.player_hands: list[Hand] = []   # Lista para suportar Split
        self.active_hand_index: int = 0       # Índice da mão atual do jogador
        self.state: GameState = GameState.WAITING_BET

    # ── Acesso conveniente ────────────────────────────────────────────

    @property
    def active_hand(self) -> Optional[Hand]:
        """Retorna a mão do jogador que está sendo jogada agora."""
        if not self.player_hands:
            return None
        if self.active_hand_index >= len(self.player_hands):
            return None
        return self.player_hands[self.active_hand_index]

    # ── Início de rodada ──────────────────────────────────────────────

    def start_round(self, bet: int) -> None:
        """
        Inicia uma nova rodada: distribui 4 cartas (2 para cada lado).

        Sequência de distribuição clássica:
            1. Jogador recebe 1 carta aberta
            2. Dealer recebe 1 carta aberta
            3. Jogador recebe 1 carta aberta
            4. Dealer recebe 1 carta OCULTA (verso)

        Args:
            bet (int): Valor apostado pelo jogador nesta rodada.
        """
        self.state = GameState.DEALING

        # Cria mão inicial do jogador com a aposta
        initial_hand = Hand(bet=bet)
        initial_hand.cards.append(self.deck.deal(face_up=True))
        initial_hand.cards.append(self.deck.deal(face_up=True))

        self.player_hands = [initial_hand]
        self.active_hand_index = 0

        # Dealer: 1 carta visível + 1 carta oculta
        self.dealer_hand = Hand()
        self.dealer_hand.cards.append(self.deck.deal(face_up=True))
        self.dealer_hand.cards.append(self.deck.deal_hidden())

        # Verifica blackjack natural do jogador antes de iniciar o turno
        if initial_hand.is_blackjack():
            initial_hand.result = HandResult.PLAYER_BLACKJACK
            self._reveal_dealer()
            self._check_dealer_blackjack_push(initial_hand)
            self.state = GameState.ROUND_OVER
        else:
            self.state = GameState.PLAYER_TURN

    # ── Ações do jogador ──────────────────────────────────────────────

    def player_hit(self) -> bool:
        """
        Jogador pede mais uma carta.

        Returns:
            bool: True se a ação foi executada com sucesso.
        """
        if self.state != GameState.PLAYER_TURN or not self.active_hand:
            return False

        hand = self.active_hand
        hand.cards.append(self.deck.deal(face_up=True))

        if hand.is_bust():
            hand.result = HandResult.PLAYER_BUST
            hand.done = True
            self._advance_hand()

        return True

    def player_stand(self) -> bool:
        """
        Jogador encerra a jogada nesta mão.

        Returns:
            bool: True se a ação foi executada com sucesso.
        """
        if self.state != GameState.PLAYER_TURN or not self.active_hand:
            return False

        self.active_hand.done = True
        self._advance_hand()
        return True

    def player_double(self) -> bool:
        """
        Jogador dobra a aposta e recebe exatamente mais 1 carta.

        Só permitido na primeira decisão (2 cartas na mão).

        Returns:
            bool: True se a ação foi executada com sucesso.
        """
        if self.state != GameState.PLAYER_TURN or not self.active_hand:
            return False

        hand = self.active_hand
        if not hand.can_double():
            return False

        hand.bet *= 2
        hand.doubled = True
        hand.cards.append(self.deck.deal(face_up=True))

        if hand.is_bust():
            hand.result = HandResult.PLAYER_BUST

        hand.done = True
        self._advance_hand()
        return True

    def player_split(self) -> bool:
        """
        Divide a mão atual em duas mãos independentes.

        Condição: as 2 cartas iniciais têm o mesmo valor nominal.
        Cada nova mão recebe uma carta adicional e mantém a aposta original.

        Returns:
            bool: True se a ação foi executada com sucesso.
        """
        if self.state != GameState.PLAYER_TURN or not self.active_hand:
            return False

        hand = self.active_hand
        if not hand.can_split():
            return False

        # Separa as cartas em duas novas mãos
        card1 = hand.cards[0]
        card2 = hand.cards[1]

        new_hand1 = Hand(bet=hand.bet)
        new_hand1.cards = [card1, self.deck.deal(face_up=True)]

        new_hand2 = Hand(bet=hand.bet)
        new_hand2.cards = [card2, self.deck.deal(face_up=True)]

        # Substitui a mão atual pelas duas novas
        self.player_hands[self.active_hand_index] = new_hand1
        self.player_hands.insert(self.active_hand_index + 1, new_hand2)

        # Verifica blackjack nas novas mãos (split de Ases)
        for new_hand in [new_hand1, new_hand2]:
            if new_hand.is_blackjack():
                new_hand.result = HandResult.PLAYER_BLACKJACK
                new_hand.done = True

        return True

    # ── Turno do dealer ───────────────────────────────────────────────

    def run_dealer_turn(self) -> None:
        """Executa o turno completo do dealer de uma vez (mantido para compatibilidade)."""
        self.begin_dealer_turn()
        while self.dealer_deal_one():
            pass

    def begin_dealer_turn(self) -> None:
        """
        Inicia o turno do dealer: revela a carta oculta e entra no estado DEALER_TURN.
        Chamado uma vez; depois o loop externo chama dealer_deal_one() a cada intervalo.
        """
        self.state = GameState.DEALER_TURN
        self._reveal_dealer()

    def dealer_deal_one(self) -> bool:
        """
        Avança o turno do dealer em uma carta.
        Deve ser chamado externamente a cada intervalo de tempo para criar o efeito de animação.

        Returns:
            True  → dealer ainda precisa de mais cartas (chamar novamente)
            False → dealer encerrou (estado muda para ROUND_OVER)
        """
        if self.state != GameState.DEALER_TURN:
            return False

        if self.dealer_hand.calculate_value_full() < self.DEALER_STAND_VALUE:
            self.dealer_hand.cards.append(self.deck.deal(face_up=True))
            return True

        self._finalize_dealer_turn()
        return False

    def _finalize_dealer_turn(self) -> None:
        """Determina o resultado de cada mão do jogador após o dealer parar."""
        dealer_value = self.dealer_hand.calculate_value_full()
        dealer_bust  = dealer_value > 21

        for hand in self.player_hands:
            if hand.result in (HandResult.PLAYER_BUST, HandResult.PLAYER_BLACKJACK):
                continue

            player_value = hand.calculate_value()

            if dealer_bust:
                hand.result = HandResult.DEALER_BUST
            elif player_value > dealer_value:
                hand.result = HandResult.PLAYER_WIN
            elif player_value < dealer_value:
                hand.result = HandResult.DEALER_WIN
            else:
                hand.result = HandResult.PUSH

        self.state = GameState.ROUND_OVER

    # ── Auxiliares internos ───────────────────────────────────────────

    def _advance_hand(self) -> None:
        """
        Avança para a próxima mão do jogador após uma ação ser concluída.
        Se todas as mãos terminaram, inicia o turno do Dealer.
        """
        # Procura a próxima mão que ainda não foi encerrada
        next_index = self.active_hand_index + 1
        while next_index < len(self.player_hands):
            if not self.player_hands[next_index].done:
                self.active_hand_index = next_index
                return
            next_index += 1

        # Nenhuma mão pendente: vai para o turno do Dealer
        # (mas só se houver alguma mão viva — não todas em bust)
        all_bust = all(
            h.result == HandResult.PLAYER_BUST
            for h in self.player_hands
        )
        if all_bust:
            self._reveal_dealer()
            self.state = GameState.ROUND_OVER
        else:
            self.begin_dealer_turn()  # loop externo chama dealer_deal_one() com intervalo

    def _reveal_dealer(self) -> None:
        """Revela a carta oculta do Dealer."""
        self.dealer_hand.reveal_hidden()

    def _check_dealer_blackjack_push(self, player_hand: Hand) -> None:
        """
        Verifica empate quando o jogador tem blackjack natural.
        Se o Dealer também tiver blackjack, é Push (empate).
        """
        self._reveal_dealer()
        if self.dealer_hand.is_blackjack():
            player_hand.result = HandResult.PUSH

    def reset(self) -> None:
        """Reseta o estado do jogo para uma nova rodada (preserva o sapato)."""
        self.dealer_hand = Hand()
        self.player_hands = []
        self.active_hand_index = 0
        self.state = GameState.WAITING_BET
        self.deck.rebuild_if_needed()

    def __repr__(self) -> str:
        return (
            f"<BlackjackGame state={self.state.name} | "
            f"dealer={self.dealer_hand} | "
            f"player_hands={self.player_hands}>"
        )
