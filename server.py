import os
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ROWS = 6
COLS = 9
RED = 'red'
YELLOW = 'yellow'
EMPTY = None

# ── Game state ───────────────────────────────────────────────────────
board = []
current_player = RED
game_over = False
winner = None
win_cells = []
is_draw = False


def reset_state():
    global board, current_player, game_over, winner, win_cells, is_draw
    board = [[EMPTY] * COLS for _ in range(ROWS)]
    current_player = RED
    game_over = False
    winner = None
    win_cells = []
    is_draw = False


# ── Game logic ───────────────────────────────────────────────────────
def get_target_row(col):
    for r in range(ROWS - 1, -1, -1):
        if board[r][col] is EMPTY:
            return r
    return -1


def check_win_for(row, col, player):
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for dr, dc in directions:
        line = [(row, col)]
        for s in range(1, 4):
            r, c = row + dr * s, col + dc * s
            if not (0 <= r < ROWS and 0 <= c < COLS) or board[r][c] != player:
                break
            line.append((r, c))
        for s in range(1, 4):
            r, c = row - dr * s, col - dc * s
            if not (0 <= r < ROWS and 0 <= c < COLS) or board[r][c] != player:
                break
            line.append((r, c))
        if len(line) >= 4:
            return line
    return None


def get_valid_cols():
    return [c for c in range(COLS) if get_target_row(c) != -1]


def score_window(window, player):
    """Score a window of 4 cells for the given player."""
    opp = RED if player == YELLOW else YELLOW
    score = 0
    if window.count(player) == 4:
        score += 100000
    elif window.count(player) == 3 and window.count(EMPTY) == 1:
        score += 60
    elif window.count(player) == 2 and window.count(EMPTY) == 2:
        score += 10
    if window.count(opp) == 3 and window.count(EMPTY) == 1:
        score -= 80
    return score


def score_board():
    """Heuristic score of the board from YELLOW's perspective."""
    score = 0

    # Centre column preference
    centre = COLS // 2
    centre_array = [board[r][centre] for r in range(ROWS)]
    score += centre_array.count(YELLOW) * 6

    # Horizontal windows
    for r in range(ROWS):
        for c in range(COLS - 3):
            w = [board[r][c + i] for i in range(4)]
            score += score_window(w, YELLOW)

    # Vertical windows
    for c in range(COLS):
        for r in range(ROWS - 3):
            w = [board[r + i][c] for i in range(4)]
            score += score_window(w, YELLOW)

    # Diagonal ↘
    for r in range(ROWS - 3):
        for c in range(COLS - 3):
            w = [board[r + i][c + i] for i in range(4)]
            score += score_window(w, YELLOW)

    # Diagonal ↙
    for r in range(ROWS - 3):
        for c in range(3, COLS):
            w = [board[r + i][c - i] for i in range(4)]
            score += score_window(w, YELLOW)

    return score


def minimax(depth, alpha, beta, maximising):
    """Minimax with alpha-beta pruning. Returns (best_col, score)."""
    valid_cols = get_valid_cols()

    if not valid_cols:
        return None, 0  # draw

    if depth == 0:
        return None, score_board()

    # Move ordering: try centre columns first (improves pruning)
    centre = COLS // 2
    valid_cols.sort(key=lambda c: abs(centre - c))

    if maximising:  # Computer (YELLOW) wants highest score
        best_score = float('-inf')
        best_col = valid_cols[0]
        for col in valid_cols:
            row = get_target_row(col)
            board[row][col] = YELLOW
            if check_win_for(row, col, YELLOW):
                board[row][col] = EMPTY
                return col, 100000 + depth   # win sooner = better
            _, score = minimax(depth - 1, alpha, beta, False)
            board[row][col] = EMPTY
            if score > best_score:
                best_score = score
                best_col = col
            alpha = max(alpha, best_score)
            if alpha >= beta:
                break
        return best_col, best_score

    else:  # Human (RED) wants lowest score
        best_score = float('inf')
        best_col = valid_cols[0]
        for col in valid_cols:
            row = get_target_row(col)
            board[row][col] = RED
            if check_win_for(row, col, RED):
                board[row][col] = EMPTY
                return col, -(100000 + depth)  # human win = bad for computer
            _, score = minimax(depth - 1, alpha, beta, True)
            board[row][col] = EMPTY
            if score < best_score:
                best_score = score
                best_col = col
            beta = min(beta, best_score)
            if alpha >= beta:
                break
        return best_col, best_score


def computer_pick_col():
    col, _ = minimax(5, float('-inf'), float('inf'), True)
    return col if col is not None else -1


def place_piece(col, player):
    global current_player, game_over, winner, win_cells, is_draw
    row = get_target_row(col)
    if row == -1:
        return -1
    board[row][col] = player
    wc = check_win_for(row, col, player)
    if wc:
        game_over = True
        winner = player
        win_cells = wc
    elif all(board[0][c] is not EMPTY for c in range(COLS)):
        game_over = True
        is_draw = True
    else:
        current_player = YELLOW if player == RED else RED
    return row


# ── API helpers ──────────────────────────────────────────────────────
def state_dict(computer_col=None):
    return {
        'board': board,
        'currentPlayer': current_player,
        'gameOver': game_over,
        'winner': winner,
        'winCells': win_cells,
        'draw': is_draw,
        'computerCol': computer_col,
    }


# ── Routes ───────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/state')
def get_state():
    return jsonify(state_dict())


@app.route('/move', methods=['POST'])
def make_move():
    if game_over or current_player != RED:
        return jsonify({'error': 'Not your turn'}), 400

    col = request.json.get('col')
    if col is None or not (0 <= col < COLS):
        return jsonify({'error': 'Invalid column'}), 400
    if get_target_row(col) == -1:
        return jsonify({'error': 'Column full'}), 400

    place_piece(col, RED)

    computer_col = None
    if not game_over:
        computer_col = computer_pick_col()
        if computer_col != -1:
            place_piece(computer_col, YELLOW)

    return jsonify(state_dict(computer_col))


@app.route('/reset', methods=['POST'])
def reset():
    reset_state()
    return jsonify(state_dict())


# ── Start server ─────────────────────────────────────────────────────
if __name__ == '__main__':
    reset_state()
    port = int(os.environ.get('PORT', 8000))
    print(f'Connect 4 running at http://localhost:{port}')
    app.run(host='0.0.0.0', port=port)
