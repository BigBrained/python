import tkinter as tk
import socket
import sys
import time
from tkinter import messagebox
from collections import deque

CELL_SIZE = 40
BOARD_SIZE = 10

class Board:
    def __init__(self):
        self.board = [[" "] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.ships = []
        self.ship_cells = 0
        self.ship_map = {}

    def place_ship(self, row, col, size, horizontal):
        if horizontal and col + size > BOARD_SIZE:
            return False
        if not horizontal and row + size > BOARD_SIZE:
            return False
        for i in range(size):
            if horizontal:
                if self.board[row][col + i] == "S":
                    return False
            else:
                if self.board[row + i][col] == "S":
                    return False
        ship_index = len(self.ships)
        ship_coords = []
        if horizontal:
            for i in range(size):
                self.board[row][col + i] = "S"
                self.ship_map[(row, col + i)] = ship_index
                ship_coords.append((row, col + i))
        else:
            for i in range(size):
                self.board[row + i][col] = "S"
                self.ship_map[(row + i, col)] = ship_index
                ship_coords.append((row + i, col))
        self.ships.append({
            "start": (row, col),
            "size": size,
            "horizontal": horizontal,
            "coords": ship_coords,
            "hits": 0
        })
        self.ship_cells += size
        return True

    def receive_attack(self, row, col):
        if not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE):
            return "invalid"
        cell = self.board[row][col]
        if cell == "S":
            self.board[row][col] = "X"
            self.ship_cells -= 1
            ship_index = self.ship_map.get((row, col))
            if ship_index is not None:
                ship = self.ships[ship_index]
                ship["hits"] += 1
                if ship["hits"] == ship["size"]:
                    sunk_coords = ",".join([f"{r},{c}" for r, c in ship["coords"]])
                    return f"sunk {sunk_coords}"
            return "hit"
        elif cell == " ":
            self.board[row][col] = "O"
            return "miss"
        elif cell in ["X", "O", "D"]:
            return "retry"
        return "invalid"

    def all_ships_sunk(self):
        return self.ship_cells == 0

class BattleshipGUI:
    def __init__(self, root, self_board, enemy_board, is_host, conn):
        self.root = root
        self.root.title("Battleship")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.canvas = tk.Canvas(root, width=2*BOARD_SIZE*CELL_SIZE+CELL_SIZE, height=BOARD_SIZE*CELL_SIZE)
        self.canvas.pack()
        self.status_label = tk.Label(root, text="Place your ships. Press 'r' to rotate")
        self.status_label.pack(pady=5)
        self.self_board = self_board
        self.enemy_board = enemy_board
        self.is_placing = True
        self.is_game_over = False
        self.both_players_ready = False
        self.current_ship_index = 0
        self.ships_to_place = [5, 4, 3, 3, 2]
        self.horizontal = True
        self.enemy_ships_sunk = 0
        self.total_enemy_ships = len(self.ships_to_place)
        self.mouse_position = None
        self.enemy_mouse_position = None
        self.last_sent_position = None
        self.cursor_update_cooldown = 0
        self.is_host = is_host
        self.turn = False
        self.conn = conn
        self.connection_lost = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        self.attack_queue = deque()
        self.last_attack_time = 0
        self.attack_cooldown = 0.5
        self.pending_attacks = {}
        self.CROSS_COLOR = "#000000"
        self.HIT_COLOR = "#ff4d4d"
        self.SELF_COLORS = {"S": "#4da6ff", "X": "#ff4d4d", "O": "#d3d3d3", " ": "#d3d3d3", "D": "#000000"}
        self.ENEMY_COLORS = {"X": "#ff4d4d", "O": "#d3d3d3", " ": "#d3d3d3", "D": "#000000"}
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<Button-1>", self._on_mouse_click)
        self.root.bind("r", self._toggle_orientation)
        self.opponent_ready = False
        self.draw_boards()
        self.root.after(100, self.poll)

    def on_closing(self):
        try:
            if self.conn and not self.connection_lost:
                self.conn.sendall(b"DISCONNECT")
                self.conn.close()
        except:
            pass
        self.root.destroy()
        sys.exit(0)

    def update_status(self, message):
        self.status_label.config(text=message)

    def draw_boards(self):
        self.canvas.delete("all")
        offsets = {"self": 0, "enemy": BOARD_SIZE * CELL_SIZE + CELL_SIZE}
        self.canvas.create_text(BOARD_SIZE * CELL_SIZE // 2, BOARD_SIZE * CELL_SIZE + 15,
                               text="Your Board", font=("Arial", 12))
        self.canvas.create_text(BOARD_SIZE * CELL_SIZE + CELL_SIZE + BOARD_SIZE * CELL_SIZE // 2,
                               BOARD_SIZE * CELL_SIZE + 15, text="Enemy Board", font=("Arial", 12))
        for board_type, board in [("self", self.self_board), ("enemy", self.enemy_board)]:
            offset_x = offsets[board_type]
            colors = self.SELF_COLORS if board_type == "self" else self.ENEMY_COLORS
            for r in range(BOARD_SIZE):
                self.canvas.create_text(offset_x - 10, r * CELL_SIZE + CELL_SIZE/2,
                                       text=chr(65 + r), font=("Arial", 10))
                for c in range(BOARD_SIZE):
                    if r == 0:
                        self.canvas.create_text(offset_x + c * CELL_SIZE + CELL_SIZE/2, -10,
                                              text=str(c+1), font=("Arial", 10))
                    value = board.board[r][c]
                    fill = colors.get(value, colors[" "])
                    x0 = offset_x + c * CELL_SIZE
                    y0 = r * CELL_SIZE
                    x1 = x0 + CELL_SIZE
                    y1 = y0 + CELL_SIZE
                    self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline="black")
                    if value == "O":
                        self.canvas.create_line(x0+5, y0+5, x1-5, y1-5, fill=self.CROSS_COLOR, width=2)
                        self.canvas.create_line(x0+5, y1-5, x1-5, y0+5, fill=self.CROSS_COLOR, width=2)
                    elif value == "X":
                        padding = 5
                        self.canvas.create_rectangle(x0+padding, y0+padding, x1-padding, y1-padding,
                                                   fill=self.HIT_COLOR, outline=self.HIT_COLOR)
                    elif value == "D":
                        self.canvas.create_rectangle(x0+2, y0+2, x1-2, y1-2, fill="black", outline="gray", width=1)
        if self.enemy_mouse_position and not self.is_placing and self.both_players_ready:
            r, c = self.enemy_mouse_position
            offset_x = 0
            if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
                x0 = offset_x + c * CELL_SIZE
                y0 = r * CELL_SIZE
                x1 = x0 + CELL_SIZE
                y1 = y0 + CELL_SIZE
                center_x = (x0 + x1) / 2
                center_y = (y0 + y1) / 2
                radius = CELL_SIZE * 0.4
                self.canvas.create_line(center_x, center_y - radius, center_x, center_y + radius,
                                       fill="red", width=2)
                self.canvas.create_line(center_x - radius, center_y, center_x + radius, center_y,
                                       fill="red", width=2)
                self.canvas.create_oval(center_x - radius, center_y - radius,
                                      center_x + radius, center_y + radius,
                                      outline="red", width=2)
        if self.mouse_position and not self.is_game_over:
            r, c = self.mouse_position
            offset_x = 0 if self.is_placing else BOARD_SIZE * CELL_SIZE + CELL_SIZE
            size = self.ships_to_place[self.current_ship_index] if self.is_placing else 1
            valid = True
            for i in range(size):
                rr = r if self.horizontal else r + i
                cc = c + i if self.horizontal else c
                if not (0 <= rr < BOARD_SIZE and 0 <= cc < BOARD_SIZE):
                    valid = False
                    break
                if self.is_placing:
                    if self.self_board.board[rr][cc] == "S":
                        valid = False
                        break
                elif not self.turn or self.enemy_board.board[rr][cc] in ["X", "O", "D"]:
                    valid = False
            highlight_color = "green" if valid else "red"
            for i in range(size):
                rr = r if self.horizontal else r + i
                cc = c + i if self.horizontal else c
                if 0 <= rr < BOARD_SIZE and 0 <= cc < BOARD_SIZE:
                    x0 = offset_x + cc * CELL_SIZE
                    y0 = rr * CELL_SIZE
                    x1 = x0 + CELL_SIZE
                    y1 = y0 + CELL_SIZE
                    self.canvas.create_rectangle(x0, y0, x1, y1, outline=highlight_color, width=3)
        self.root.update_idletasks()

    def _toggle_orientation(self, event):
        if self.is_placing:
            self.horizontal = not self.horizontal
            self.draw_boards()

    def _on_mouse_move(self, event):
        if self.is_game_over or self.connection_lost:
            return
        board_to_use = self.self_board if self.is_placing else self.enemy_board
        offset_x = 0 if self.is_placing else BOARD_SIZE * CELL_SIZE + CELL_SIZE
        if offset_x <= event.x < offset_x + BOARD_SIZE * CELL_SIZE and 0 <= event.y < BOARD_SIZE * CELL_SIZE:
            c = (event.x - offset_x) // CELL_SIZE
            r = event.y // CELL_SIZE
            self.mouse_position = (r, c)
            if not self.is_placing and self.both_players_ready:
                self.cursor_update_cooldown += 1
                if self.cursor_update_cooldown >= 5:
                    self.cursor_update_cooldown = 0
                    current_pos = (r, c)
                    if current_pos != self.last_sent_position:
                        try:
                            msg = f"CURSOR {r} {c}"
                            self.conn.sendall(msg.encode("utf-8"))
                            self.last_sent_position = current_pos
                        except:
                            pass
        else:
            self.mouse_position = None
        self.draw_boards()

    def _on_mouse_click(self, event):
        if not self.mouse_position or self.is_game_over or self.connection_lost:
            return
        r, c = self.mouse_position
        if self.is_placing:
            size = self.ships_to_place[self.current_ship_index]
            if self.self_board.place_ship(r, c, size, self.horizontal):
                self.current_ship_index += 1
                if self.current_ship_index >= len(self.ships_to_place):
                    self.is_placing = False
                    try:
                        self.conn.sendall(b"READY")
                        self.update_status("Waiting for opponent...")
                        if self.opponent_ready:
                            self.start_game()
                    except socket.error:
                        self.handle_connection_loss()
        elif self.turn and (time.time() - self.last_attack_time >= self.attack_cooldown):
            if not (self.enemy_board.board[r][c] in ["X", "O", "D"]):
                self.attack_queue.append((r, c))
                self.process_attack_queue()
        self.draw_boards()

    def process_attack_queue(self):
        if not self.turn or not self.attack_queue or self.connection_lost:
            return
        if time.time() - self.last_attack_time < self.attack_cooldown:
            self.root.after(int(self.attack_cooldown * 1000), self.process_attack_queue)
            return
        r, c = self.attack_queue.popleft()
        try:
            msg = f"ATTACK {r} {c}"
            self.conn.sendall(msg.encode("utf-8"))
            self.pending_attacks[(r, c)] = time.time()
            self.last_attack_time = time.time()
            self.update_status("Attack sent. Waiting for response...")
        except socket.error:
            self.handle_connection_loss()

    def start_game(self):
        self.both_players_ready = True
        self.turn = self.is_host
        if self.turn:
            self.update_status("Game started! Your turn to attack.")
        else:
            self.update_status("Game started! Opponent's turn.")

    def handle_game_over(self, winner):
        self.is_game_over = True
        if winner == "self":
            self.update_status("YOU WON! GAME OVER.")
        else:
            self.update_status("YOU LOST! GAME OVER.")

    def handle_connection_loss(self):
        if self.connection_lost:
            return
        self.connection_lost = True
        self.update_status("Connection lost. Attempting to reconnect...")
        self.reconnect_attempts += 1
        if self.reconnect_attempts <= self.max_reconnect_attempts:
            self.root.after(2000, self.attempt_reconnect)
        else:
            messagebox.showerror("Connection Error", "Failed to reconnect. Game over.")
            self.on_closing()

    def attempt_reconnect(self):
        if self.is_host:
            return
        try:
            new_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            new_conn.connect((self.host_ip, 12345))
            self.conn.close()
            self.conn = new_conn
            self.connection_lost = False
            self.reconnect_attempts = 0
            self.update_status("Reconnected! Resuming game.")
            self.conn.sendall(b"RECONNECT")
        except socket.error:
            self.handle_connection_loss()

    def poll(self):
        if self.is_game_over or self.connection_lost:
            self.draw_boards()
            self.root.after(100, self.poll)
            return
        try:
            self.conn.settimeout(0.1)
            msg = self.conn.recv(1024).decode("utf-8")
            if not msg:
                self.handle_connection_loss()
                return
            if msg == "READY":
                self.opponent_ready = True
                if not self.is_placing:
                    self.start_game()
                else:
                    self.update_status("Opponent is ready. Place your ships.")
            elif msg.startswith("CURSOR"):
                try:
                    _, r, c = msg.split()
                    r, c = int(r), int(c)
                    self.enemy_mouse_position = (r, c)
                except:
                    pass
            elif msg.startswith("ATTACK"):
                _, r, c = msg.split()
                r, c = int(r), int(c)
                result = self.self_board.receive_attack(r, c)
                try:
                    self.conn.sendall(result.encode("utf-8"))
                except socket.error:
                    self.handle_connection_loss()
                    return
                if result.startswith("sunk"):
                    _, coords_str = result.split(" ", 1)
                    coords_pairs = coords_str.split(",")
                    for i in range(0, len(coords_pairs), 2):
                        if i+1 < len(coords_pairs):
                            try:
                                r = int(coords_pairs[i])
                                c = int(coords_pairs[i+1])
                                self.self_board.board[r][c] = "D"
                            except (ValueError, IndexError):
                                pass
                if self.self_board.all_ships_sunk():
                    try:
                        self.conn.sendall(b"GAMEOVER")
                    except socket.error:
                        self.handle_connection_loss()
                        return
                    self.handle_game_over("enemy")
                elif result == "miss":
                    self.turn = True
                    self.update_status("Enemy missed! Your turn.")
                    self.process_attack_queue()
                else:
                    self.turn = False
                    self.update_status("Enemy hit your ship! Their turn again.")
            elif msg in ["hit", "miss", "retry", "invalid"] or msg.startswith("sunk"):
                if not self.pending_attacks:
                    return
                r, c = list(self.pending_attacks.keys())[0]
                del self.pending_attacks[(r, c)]
                if msg == "hit":
                    self.update_status("Hit! Your turn again.")
                    self.enemy_board.board[r][c] = "X"
                    self.turn = True
                    self.process_attack_queue()
                elif msg == "miss":
                    self.update_status("Miss! Opponent's turn.")
                    self.enemy_board.board[r][c] = "O"
                    self.turn = False
                elif msg in ["retry", "invalid"]:
                    self.update_status("Invalid attack. Try again.")
                    self.turn = True
                    self.attack_queue.appendleft((r, c))
                    self.process_attack_queue()
                elif msg.startswith("sunk"):
                    self.enemy_board.board[r][c] = "X"
                    _, coords_str = msg.split(" ", 1)
                    coords_pairs = coords_str.split(",")
                    for i in range(0, len(coords_pairs), 2):
                        if i+1 < len(coords_pairs):
                            try:
                                r = int(coords_pairs[i])
                                c = int(coords_pairs[i+1])
                                self.enemy_board.board[r][c] = "D"
                            except (ValueError, IndexError):
                                pass
                    self.enemy_ships_sunk += 1
                    if self.enemy_ships_sunk >= self.total_enemy_ships:
                        self.update_status("YOU WON! You sunk all enemy ships!")
                        try:
                            self.conn.sendall(b"GAMEOVER")
                        except socket.error:
                            self.handle_connection_loss()
                            return
                        self.handle_game_over("self")
                    else:
                        self.update_status(f"You sunk a ship! Your turn again. ({self.enemy_ships_sunk}/{self.total_enemy_ships} sunk)")
                        self.turn = True
                        self.process_attack_queue()
                self.draw_boards()
            elif msg == "GAMEOVER":
                self.handle_game_over("self")
                self.draw_boards()
            elif msg == "DISCONNECT":
                messagebox.showinfo("Game Over", "Opponent disconnected!")
                self.on_closing()
            elif msg == "RECONNECT":
                self.connection_lost = False
                self.update_status("Opponent reconnected! Resuming game.")
            self.conn.settimeout(None)
        except socket.timeout:
            pass
        except socket.error:
            self.handle_connection_loss()
            return
        self.draw_boards()
        self.root.after(100, self.poll)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = "127.0.0.1"
    finally:
        s.close()
    return IP

def main():
    role = input("Host or Client? (h/c): ").strip().lower()
    conn = None
    host_ip = None
    if role == "h":
        host = get_local_ip()
        print(f"Hosting on {host}:12345")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, 12345))
            s.listen(1)
            print("Waiting for opponent to connect...")
            s.settimeout(30)
            conn, addr = s.accept()
            print(f"Opponent connected from {addr}")
        except socket.timeout:
            print("No opponent connected within timeout.")
            s.close()
            sys.exit(1)
        except socket.error as e:
            print(f"Failed to start server: {e}")
            s.close()
            sys.exit(1)
    else:
        host_ip = input("Enter host IP: ").strip()
        if not host_ip:
            print("Invalid IP address.")
            sys.exit(1)
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            conn.connect((host_ip, 12345))
            print("Connected to host!")
        except socket.error as e:
            print(f"Could not connect to host: {e}")
            sys.exit(1)
    root = tk.Tk()
    self_board = Board()
    enemy_board = Board()
    gui = BattleshipGUI(root, self_board, enemy_board, role == "h", conn)
    gui.host_ip = host_ip if role != "h" else None
    root.mainloop()

if __name__ == "__main__":
    main()
