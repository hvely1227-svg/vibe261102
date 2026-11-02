"""뱀 게임 (Snake Game) - tkinter 사용, 추가 설치 불필요.

조작법:
    방향키 / WASD : 이동
    Space         : 일시정지 / 재개
    R             : 게임 오버 후 재시작
"""

import random
import tkinter as tk

CELL = 20          # 한 칸의 픽셀 크기
COLS = 30          # 가로 칸 수
ROWS = 24          # 세로 칸 수
START_SPEED = 120  # 시작 속도 (ms, 작을수록 빠름)
MIN_SPEED = 50     # 최고 속도

DIRECTIONS = {
    "Up": (0, -1), "w": (0, -1), "W": (0, -1),
    "Down": (0, 1), "s": (0, 1), "S": (0, 1),
    "Left": (-1, 0), "a": (-1, 0), "A": (-1, 0),
    "Right": (1, 0), "d": (1, 0), "D": (1, 0),
}


class SnakeGame:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("뱀 게임")
        self.root.resizable(False, False)

        self.score_label = tk.Label(root, font=("Malgun Gothic", 14, "bold"))
        self.score_label.pack(pady=4)

        self.canvas = tk.Canvas(
            root, width=COLS * CELL, height=ROWS * CELL,
            bg="#1e1e1e", highlightthickness=0,
        )
        self.canvas.pack()

        self.high_score = 0
        self.after_id = None
        root.bind("<Key>", self.on_key)
        self.reset()

    # ---------- 게임 상태 ----------
    def reset(self):
        if self.after_id:
            self.root.after_cancel(self.after_id)
        cx, cy = COLS // 2, ROWS // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = (1, 0)
        self.pending = []          # 빠른 연속 입력을 위한 방향 버퍼
        self.score = 0
        self.speed = START_SPEED
        self.paused = False
        self.game_over = False
        self.food = self.spawn_food()
        self.draw()
        self.tick()

    def spawn_food(self):
        free = [(x, y) for x in range(COLS) for y in range(ROWS)
                if (x, y) not in self.snake]
        return random.choice(free) if free else None

    # ---------- 입력 ----------
    def on_key(self, event):
        key = event.keysym
        if key == "space" and not self.game_over:
            self.paused = not self.paused
            self.draw()
            return
        if key in ("r", "R") and self.game_over:
            self.reset()
            return
        if key in DIRECTIONS and len(self.pending) < 3:
            new = DIRECTIONS[key]
            last = self.pending[-1] if self.pending else self.direction
            # 반대 방향 및 같은 방향 입력은 무시
            if new != last and (new[0] + last[0], new[1] + last[1]) != (0, 0):
                self.pending.append(new)

    # ---------- 게임 루프 ----------
    def tick(self):
        if not self.paused and not self.game_over:
            self.step()
            self.draw()
        if not self.game_over:
            self.after_id = self.root.after(self.speed, self.tick)

    def step(self):
        if self.pending:
            self.direction = self.pending.pop(0)

        hx, hy = self.snake[0]
        dx, dy = self.direction
        head = (hx + dx, hy + dy)

        ate = head == self.food
        body = self.snake if ate else self.snake[:-1]  # 꼬리는 이동하므로 제외

        if not (0 <= head[0] < COLS and 0 <= head[1] < ROWS) or head in body:
            self.game_over = True
            self.high_score = max(self.high_score, self.score)
            return

        self.snake.insert(0, head)
        if ate:
            self.score += 10
            self.speed = max(MIN_SPEED, self.speed - 3)
            self.food = self.spawn_food()
            if self.food is None:  # 화면을 가득 채움 = 승리
                self.game_over = True
                self.high_score = max(self.high_score, self.score)
        else:
            self.snake.pop()

    # ---------- 그리기 ----------
    def draw(self):
        c = self.canvas
        c.delete("all")

        if self.food:
            fx, fy = self.food
            c.create_oval(fx * CELL + 3, fy * CELL + 3,
                          (fx + 1) * CELL - 3, (fy + 1) * CELL - 3,
                          fill="#ff5252", outline="")

        for i, (x, y) in enumerate(self.snake):
            color = "#7CFC00" if i == 0 else "#32CD32"
            c.create_rectangle(x * CELL + 1, y * CELL + 1,
                               (x + 1) * CELL - 1, (y + 1) * CELL - 1,
                               fill=color, outline="")

        self.score_label.config(
            text=f"점수: {self.score}    최고 점수: {self.high_score}")

        w, h = COLS * CELL, ROWS * CELL
        if self.paused:
            c.create_text(w / 2, h / 2, text="일시정지",
                          fill="white", font=("Malgun Gothic", 28, "bold"))
        elif self.game_over:
            title = "승리!" if self.food is None else "게임 오버"
            c.create_text(w / 2, h / 2 - 20, text=title,
                          fill="white", font=("Malgun Gothic", 32, "bold"))
            c.create_text(w / 2, h / 2 + 25, text="R 키를 눌러 재시작",
                          fill="#cccccc", font=("Malgun Gothic", 14))


if __name__ == "__main__":
    root = tk.Tk()
    SnakeGame(root)
    root.mainloop()
