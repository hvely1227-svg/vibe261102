import tkinter as tk


WIDTH = 800
HEIGHT = 600
TOP = 72
PADDLE_WIDTH = 112
PADDLE_HEIGHT = 14
BALL_RADIUS = 9
TICK_MS = 16


class Breakout:
    def __init__(self, root):
        self.root = root
        self.root.title("블록깨기")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            root,
            width=WIDTH,
            height=HEIGHT,
            bg="#101923",
            highlightthickness=0,
        )
        self.canvas.pack()
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Button-1>", self.on_click)
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        self.root.focus_set()

        self.keys = set()
        self.paddle_x = WIDTH / 2
        self.score = 0
        self.lives = 3
        self.bricks = []
        self.state = "title"
        self.message = ""
        self.reset_ball()
        self.draw()
        self.root.after(TICK_MS, self.tick)

    def reset_ball(self):
        self.ball_x = self.paddle_x
        self.ball_y = HEIGHT - 62
        self.ball_vx = 3.2
        self.ball_vy = -5.2

    def new_game(self):
        self.score = 0
        self.lives = 3
        self.paddle_x = WIDTH / 2
        self.bricks = []
        colors = ["#ff6b5f", "#ff9f43", "#f6c85f", "#49c5b6", "#5c9ded"]
        columns = 10
        gap = 7
        brick_width = (WIDTH - 72 - gap * (columns - 1)) / columns
        for row in range(5):
            for column in range(columns):
                left = 36 + column * (brick_width + gap)
                top = 104 + row * 31
                self.bricks.append(
                    {
                        "box": (left, top, left + brick_width, top + 22),
                        "color": colors[row],
                        "points": (5 - row) * 10,
                    }
                )
        self.reset_ball()
        self.state = "ready"
        self.message = "스페이스를 눌러 공을 발사하세요"

    def serve(self):
        self.state = "running"
        self.message = ""

    def on_key_press(self, event):
        self.keys.add(event.keysym.lower())
        if event.keysym in ("space", "Return"):
            if self.state == "title":
                self.new_game()
                self.serve()
            elif self.state in ("game_over", "won"):
                self.new_game()
                self.serve()
            elif self.state == "ready":
                self.serve()

    def on_key_release(self, event):
        self.keys.discard(event.keysym.lower())

    def on_mouse_move(self, event):
        self.paddle_x = self.clamp(event.x, PADDLE_WIDTH / 2, WIDTH - PADDLE_WIDTH / 2)
        if self.state == "ready":
            self.ball_x = self.paddle_x

    def on_click(self, _event):
        if self.state == "title":
            self.new_game()
            self.serve()
        elif self.state == "ready":
            self.serve()
        elif self.state in ("game_over", "won"):
            self.new_game()
            self.serve()

    @staticmethod
    def clamp(value, lower, upper):
        return max(lower, min(value, upper))

    def update(self):
        direction = 0
        if self.keys.intersection(("left", "a")):
            direction -= 1
        if self.keys.intersection(("right", "d")):
            direction += 1
        self.paddle_x = self.clamp(
            self.paddle_x + direction * 8,
            PADDLE_WIDTH / 2,
            WIDTH - PADDLE_WIDTH / 2,
        )

        self.ball_x += self.ball_vx
        self.ball_y += self.ball_vy

        if self.ball_x - BALL_RADIUS <= 0 or self.ball_x + BALL_RADIUS >= WIDTH:
            self.ball_vx *= -1
            self.ball_x = self.clamp(self.ball_x, BALL_RADIUS, WIDTH - BALL_RADIUS)
        if self.ball_y - BALL_RADIUS <= TOP:
            self.ball_vy = abs(self.ball_vy)
            self.ball_y = TOP + BALL_RADIUS

        paddle_left = self.paddle_x - PADDLE_WIDTH / 2
        paddle_right = self.paddle_x + PADDLE_WIDTH / 2
        paddle_top = HEIGHT - 44
        if (
            self.ball_vy > 0
            and self.ball_y + BALL_RADIUS >= paddle_top
            and self.ball_y - BALL_RADIUS <= paddle_top + PADDLE_HEIGHT
            and paddle_left <= self.ball_x <= paddle_right
        ):
            offset = (self.ball_x - self.paddle_x) / (PADDLE_WIDTH / 2)
            self.ball_vx = offset * 5.2
            self.ball_vy = -max(4.0, 6.2 - abs(offset) * 1.2)
            self.ball_y = paddle_top - BALL_RADIUS

        ball_left = self.ball_x - BALL_RADIUS
        ball_right = self.ball_x + BALL_RADIUS
        ball_top = self.ball_y - BALL_RADIUS
        ball_bottom = self.ball_y + BALL_RADIUS
        for brick in self.bricks[:]:
            left, top, right, bottom = brick["box"]
            overlap_x = min(ball_right, right) - max(ball_left, left)
            overlap_y = min(ball_bottom, bottom) - max(ball_top, top)
            if overlap_x > 0 and overlap_y > 0:
                self.bricks.remove(brick)
                self.score += brick["points"]
                if overlap_x < overlap_y:
                    self.ball_vx *= -1
                else:
                    self.ball_vy *= -1
                break

        if not self.bricks:
            self.state = "won"
            self.message = "모든 블록을 깼어요! 스페이스를 눌러 다시 시작"
        elif self.ball_y - BALL_RADIUS > HEIGHT:
            self.lives -= 1
            if self.lives <= 0:
                self.state = "game_over"
                self.message = "게임 오버! 스페이스를 눌러 다시 시작"
            else:
                self.state = "ready"
                self.message = "공을 놓쳤어요. 스페이스를 눌러 계속"
                self.reset_ball()

    def draw(self):
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, WIDTH, TOP, fill="#182632", outline="")
        self.canvas.create_text(
            28, 35, anchor="w", text="블록깨기", fill="#f2f5f7",
            font=("Segoe UI", 18, "bold"),
        )
        self.canvas.create_text(
            WIDTH - 210, 35, anchor="w", text=f"점수  {self.score}", fill="#d9e3ea",
            font=("Segoe UI", 12, "bold"),
        )
        self.canvas.create_text(
            WIDTH - 28, 35, anchor="e", text=f"목숨  {self.lives}", fill="#ff9f8f",
            font=("Segoe UI", 12, "bold"),
        )
        self.canvas.create_line(0, TOP, WIDTH, TOP, fill="#2a3c49", width=2)

        for brick in self.bricks:
            left, top, right, bottom = brick["box"]
            self.canvas.create_rectangle(
                left, top, right, bottom,
                fill=brick["color"], outline="#101923", width=2,
            )

        paddle_top = HEIGHT - 44
        self.canvas.create_rectangle(
            self.paddle_x - PADDLE_WIDTH / 2,
            paddle_top,
            self.paddle_x + PADDLE_WIDTH / 2,
            paddle_top + PADDLE_HEIGHT,
            fill="#e9f1f5",
            outline="",
        )
        self.canvas.create_oval(
            self.ball_x - BALL_RADIUS,
            self.ball_y - BALL_RADIUS,
            self.ball_x + BALL_RADIUS,
            self.ball_y + BALL_RADIUS,
            fill="#f6c85f",
            outline="",
        )

        if self.state != "running":
            if self.state == "title":
                title = "블록깨기"
                subtitle = "스페이스 또는 클릭으로 시작"
            else:
                title = self.message
                subtitle = "← → 또는 A / D 키로 이동 · 마우스로도 조작 가능"
            self.canvas.create_rectangle(
                100, 245, WIDTH - 100, 355, fill="#101923", outline="#344957", width=2
            )
            self.canvas.create_text(
                WIDTH / 2, 285, text=title, fill="#f2f5f7",
                font=("Segoe UI", 20, "bold"), width=560,
            )
            self.canvas.create_text(
                WIDTH / 2, 328, text=subtitle, fill="#aebec8",
                font=("Segoe UI", 11),
            )
        else:
            self.canvas.create_text(
                16, HEIGHT - 12, anchor="sw", text="← → / A D 이동   ·   마우스 이동",
                fill="#718491", font=("Segoe UI", 9),
            )

    def tick(self):
        if self.state == "running":
            self.update()
        self.draw()
        self.root.after(TICK_MS, self.tick)


if __name__ == "__main__":
    window = tk.Tk()
    Breakout(window)
    window.mainloop()