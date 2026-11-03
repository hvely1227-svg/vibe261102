"""
앱 아이콘(app.ico) 생성 스크립트 - 파랑 배경 위 상승 라인 차트

필요 패키지:
    pip install pillow
"""

from PIL import Image, ImageDraw

SIZE = 256
TOP, BOTTOM = (37, 99, 235), (30, 58, 138)
LINE = [(40, 190), (80, 150), (110, 170), (150, 110), (180, 128), (216, 64)]


def main():
    # 세로 그라데이션 배경
    bg = Image.new("RGBA", (SIZE, SIZE))
    px = bg.load()
    for y in range(SIZE):
        t = y / (SIZE - 1)
        c = tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM))
        for x in range(SIZE):
            px[x, y] = c + (255,)

    # 둥근 사각형 모양으로 자르기
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((8, 8, SIZE - 8, SIZE - 8), radius=56, fill=255)
    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    icon.paste(bg, mask=mask)

    d = ImageDraw.Draw(icon)
    # 옅은 격자선
    for y in (80, 128, 176):
        d.line((36, y, 220, y), fill=(255, 255, 255, 60), width=2)
    # 흰색 상승 라인 + 끝점의 초록 점
    d.line(LINE, fill="white", width=14, joint="curve")
    x, y = LINE[-1]
    d.ellipse((x - 16, y - 16, x + 16, y + 16), fill=(34, 197, 94), outline="white", width=5)

    icon.save("app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    icon.save("app.png")
    print("app.ico, app.png 생성 완료")


if __name__ == "__main__":
    main()
