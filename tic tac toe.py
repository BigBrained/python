import time
import random
class Format:
    end = '\033[0m'
    underline = '\033[4m'

board = [[0,0,0],
         [0,0,0],
         [0,0,0]]

def think():
    # Using weighted random.choices so that higher numbers have greater chances
    """
    stages = list("|/-\\")
    random.seed(time.time())
    r = random.randint(15, 20)
    for i in range(r//4):
        for i in range(4):
            print(stages[i], end="\r")
            time.sleep(0.25)
    for i in range(r%4):    
        print(stages[i], end="\r")
        time.sleep(0.25)"""


def print_board(board):
    b = []
    for row in board:
        a = []
        for cell in row:
            if cell == 0:
                a.append(' ')
            elif cell == 1:
                a.append('x')
            else:
                a.append('o')
        b.append(a)
    
    print(Format.underline + f'{b[0][0]}|{b[0][1]}|{b[0][2]}' + Format.end)
    print(Format.underline + f'{b[1][0]}|{b[1][1]}|{b[1][2]}' + Format.end)
    print(f'{b[2][0]}|{b[2][1]}|{b[2][2]}')

def evaluate(board):
    for row in board:
        if row[0] == row[1] == row[2] and row[0] != 0:
            return row[0]
    for col in range(3):
        if board[0][col] == board[1][col] == board[2][col] and board[0][col] != 0:
            return board[0][col]
    if board[0][0] == board[1][1] == board[2][2] and board[0][0] != 0:
        return board[0][0]
    if board[0][2] == board[1][1] == board[2][0] and board[0][2] != 0:
        return board[0][2]
    for row in board:
        for cell in row:
            if cell == 0:
                return None
    return 0

def move(board, player, x, y):
    if board[x][y] == 0:
        board[x][y] = player
        return True
    return False

def minimax(board, player):
    result = evaluate(board)
    if result is not None:
        return result, None
    if player == 1:
        best = -1
        best_move = None
        for i in range(3):
            for j in range(3):
                if board[i][j] == 0:
                    board[i][j] = player
                    score, _ = minimax(board, -player)
                    board[i][j] = 0
                    if score == 1:
                        return score, (i, j)
                    if score > best:
                        best = score
                        best_move = (i, j)
        return best, best_move
    else:  # player == -1
        best = 1
        best_move = None
        for i in range(3):
            for j in range(3):
                if board[i][j] == 0:
                    board[i][j] = player
                    score, _ = minimax(board, -player)
                    board[i][j] = 0
                    if score == -1:
                        return score, (i, j)
                    if score < best:
                        best = score
                        best_move = (i, j)
        return best, best_move

def main():
    # Human is player1 or player2? Mapping: User chosen player will be human.
    # Using internal representation: 1 for one side, -1 for the other.
    human_choice = int(input('Enter player (1 or 2): '))
    # For this example human goes first if they choose 2 (mapped to 1), computer otherwise.
    human = 1 if human_choice == 1 else -1
    p = 1  # Always alternate starting with player represented by 1.
    print_board(board)
    
    while True:
        if p == human:
            try:
                x, y = map(int, input('Enter row and column (1-3): ').split())
                x-=1
                y-=1
            except Exception:
                print("Invalid input.")
                continue
            if not (0 <= x <= 2 and 0 <= y <= 2):
                print("Coordinates must be between 0 and 2.")
                continue
            if not move(board, p, x, y):
                print("Invalid move.")
                continue
            print_board(board)
            p = -p
        else:
            _, m = minimax(board, p)
            if m is None:
                # No valid moves
                pass
            else:
                x, y = m
                move(board, p, x, y)
                think()
                print("Computer move:")
                print_board(board)
                p = -p

        result = evaluate(board)
        if result is not None:
            if result == 0:
                print("Draw")
            else:
                # Mapping internal representation to player number (1 or 2)
                winner = 2 if result == 1 else 1
                print(f'Player {winner} wins!')
            break

main()