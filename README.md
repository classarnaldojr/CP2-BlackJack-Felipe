# BlackJack Vision

Jogo de Blackjack em Python controlado por gestos via webcam, usando OpenCV e MediaPipe.

## Tecnologias

- Python 3.10+
- OpenCV
- MediaPipe
- NumPy

## Instalação

```bash
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Gestos

| Gesto | Acao |
|-------|------|
| Mao aberta (4-5 dedos) | Hit |
| Punho fechado | Stand |
| 1 dedo (indicador) | Double |
| 2 dedos (V) | Split |

## Controles de teclado

| Tecla | Acao |
|-------|------|
| H | Hit |
| S | Stand |
| D | Double |
| P | Split |
| N | Nova rodada |
| Q / ESC | Sair |

## Regras

- 4 baralhos (208 cartas)
- Dealer compra ate 17
- Blackjack paga 3:2
- Double e Split disponiveis na primeira jogada
- Jogador inicia com 500 fichas
- Rebuy disponivel ao zerar o saldo

## Estrutura

```
modules/
  deck.py      # Baralho e cartas
  hand.py      # Logica das maos
  game.py      # Regras e estados
  betting.py   # Sistema de apostas
  vision.py    # Deteccao de gestos
  renderer.py  # Interface visual
main.py        # Loop principal
Assets/Cards/  # Imagens das cartas
```
