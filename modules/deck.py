"""
deck.py — Módulo de Cartas e Baralho
BlackJack Vision

Responsabilidades:
- Definir a estrutura lógica de uma carta (valor + naipe)
- Construir o baralho base de 52 cartas
- Multiplicar por 4 decks (208 cartas no total = "sapato")
- Embaralhar e distribuir cartas
- Converter a carta lógica para o nome correto do arquivo PNG
"""

import random
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────
# Constantes do baralho
# ─────────────────────────────────────────────

SUITS = ["Clubs", "Diamonds", "Hearts", "Spades"]

# Valores das cartas conforme aparecem nos nomes dos arquivos
VALUES = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]

# Quantos baralhos compõem o "sapato"
NUM_DECKS = 4


# ─────────────────────────────────────────────
# Estrutura de uma carta
# ─────────────────────────────────────────────

@dataclass
class Card:
    """
    Representa uma carta de baralho de forma lógica.
    
    Atributos:
        value (str): Valor textual da carta: "2"–"10", "J", "Q", "K", "A"
        suit  (str): Naipe em inglês: "Clubs", "Diamonds", "Hearts", "Spades"
        face_up (bool): Se True, a carta está visível; se False, está oculta (verso)
    """
    value: str
    suit: str
    face_up: bool = True

    def get_filename(self) -> str:
        """
        Converte a carta lógica no nome exato do arquivo PNG.

        Regra de nomenclatura:
            <Valor><Naipe>.png
        
        Exemplos:
            Card("A",  "Spades")   → "ASpades.png"
            Card("10", "Hearts")   → "10Hearts.png"
            Card("Q",  "Hearts")   → "QHearts.png"
            Card("K",  "Spades")   → "KSpades.png"
            Card("2",  "Clubs")    → "2Clubs.png"
        
        Nota: Esta função é a fonte única de verdade para o mapeamento
        lógica → arquivo. Toda a aplicação deve usá-la.
        """
        return f"{self.value}{self.suit}.png"

    def get_numeric_value(self) -> int:
        """
        Retorna o valor numérico base da carta para cálculo da mão.
        
        - Figuras (J, Q, K) valem 10
        - Números valem seu valor inteiro
        - Ás retorna 11 por padrão; a lógica de Soft Card fica no módulo game.py
        """
        if self.value in ("J", "Q", "K"):
            return 10
        if self.value == "A":
            return 11   # Soft Ace — ajustado para 1 em game.py se necessário
        return int(self.value)

    def __repr__(self) -> str:
        status = "↑" if self.face_up else "↓"
        return f"[{self.value}{self.suit[0]} {status}]"


# ─────────────────────────────────────────────
# Baralho — sapato com 4 decks
# ─────────────────────────────────────────────

class Deck:
    """
    Gerencia o sapato de cartas (4 × 52 = 208 cartas).

    O sapato é uma fila de cartas embaralhadas. As cartas são retiradas
    do início da lista (topo do baralho). Quando o limite mínimo é
    atingido, o sapato é reconstruído e embaralhado novamente.

    Atributos:
        MIN_CARDS (int): Número mínimo de cartas antes de reconstruir o sapato.
        cards (list[Card]): Lista interna representando o sapato.
    """

    MIN_CARDS = 30  # Limiar para reconstrução do sapato

    def __init__(self):
        self.cards: list[Card] = []
        self._build_shoe()

    # ── Construção e embaralhamento ──────────────────────────────────

    def _build_shoe(self) -> None:
        """
        Cria o sapato: 1 baralho-base × NUM_DECKS, depois embaralha.
        A multiplicação por 4 garante que cartas se repitam naturalmente.
        """
        base_deck = [
            Card(value=v, suit=s)
            for s in SUITS
            for v in VALUES
        ]
        # 4 cópias do baralho base → 208 cartas
        self.cards = base_deck * NUM_DECKS
        self._shuffle()
        print(f"[Deck] Sapato criado com {len(self.cards)} cartas.")

    def _shuffle(self) -> None:
        """Embaralha o sapato in-place usando random.shuffle."""
        random.shuffle(self.cards)

    def rebuild_if_needed(self) -> None:
        """Reconstrói o sapato se o número de cartas estiver abaixo do mínimo."""
        if len(self.cards) < self.MIN_CARDS:
            print("[Deck] Sapato abaixo do limite mínimo. Reconstruindo...")
            self._build_shoe()

    # ── Distribuição de cartas ───────────────────────────────────────

    def deal(self, face_up: bool = True) -> Card:
        """
        Retira e retorna a carta do topo do sapato.

        Args:
            face_up (bool): Define se a carta estará visível ou oculta.
        
        Returns:
            Card: A carta retirada do topo.
        
        Raises:
            RuntimeError: Se o sapato estiver vazio (não deve ocorrer com
                          rebuild_if_needed sendo chamado regularmente).
        """
        self.rebuild_if_needed()
        if not self.cards:
            raise RuntimeError("[Deck] Sapato vazio! Isso nao deveria acontecer.")
        card = self.cards.pop(0)
        card.face_up = face_up
        return card

    def deal_hidden(self) -> Card:
        """
        Conveniência: distribui uma carta com o verso para cima (oculta).
        Usada para a carta escondida do Dealer.
        """
        return self.deal(face_up=False)

    # ── Informações ──────────────────────────────────────────────────

    def remaining(self) -> int:
        """Retorna quantas cartas ainda existem no sapato."""
        return len(self.cards)

    def __repr__(self) -> str:
        return f"<Deck: {self.remaining()} cartas restantes>"
