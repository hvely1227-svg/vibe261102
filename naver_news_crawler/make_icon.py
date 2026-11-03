"""
앱 아이콘(app.ico) 생성 스크립트 - 배너와 같은 초록→파랑→보라 그라데이션

필요 패키지:
    pip install pillow
"""

from PIL import Image, ImageDraw, ImageFont

SIZE = 256
STOPS = [(0.0, (3, 199, 90)), (0.5, (0, 163, 255)), (1.0, (123, 97, 255))]


def gradient_color(t):
    for (t0, c0), (t1, c1) in zip(STOPS, STOPS[1:]):
        if t <= t1:
            r = (t - t0) / (t1 - t0)
            return tuple(round(a + (b - a) * r) for a, b in zip(c0, c1))
    return STOPS[-1][1]


def main():
    # 대각선 그라데이션 배경
    bg = Image.new("RGBA", (SIZE, SIZE))
    px = bg.load()
    for y in range(SIZE):
        for x in range(SIZE):
            px[x, y] = gradient_color((x + y) / (2 * (SIZE - 1))) + (255,)

    # 둥근 사각형 모양으로 자르기
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((8, 8, SIZE - 8, SIZE - 8), radius=56, fill=255)
    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    icon.paste(bg, mask=mask)

    # 흰색 신문 모양
    d = ImageDraw.Draw(icon)
    d.rounded_rectangle((52, 60, 204, 196), radius=14, fill="white")
    d.rectangle((70, 78, 186, 104), fill=(0, 163, 255))  # 헤드라인
    d.rectangle((70, 118, 120, 172), fill=(3, 199, 90))  # 사진
    for y in (120, 138, 156, 172):  # 본문 줄
        d.rounded_rectangle((132, y - 2, 186, y + 4), radius=3, fill=(123, 97, 255))

    # 우측 하단 "N" 배지
    d.ellipse((160, 156, 236, 232), fill=(255, 107, 107), outline="white", width=6)
    try:
        font = ImageFont.truetype("arialbd.ttf", 46)
    except OSError:
        font = ImageFont.load_default()
    d.text((198, 194), "N", fill="white", font=font, anchor="mm")

    icon.save("app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    icon.save("app.png")
    print("app.ico, app.png 생성 완료")


if __name__ == "__main__":
    main()
