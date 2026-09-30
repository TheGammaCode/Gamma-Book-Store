#!/usr/bin/env python3
"""Tạo favicon từ logo Gamma gốc. Chỉ crop vuông rồi thu nhỏ, không vẽ lại logo.

Yêu cầu: Pillow. Chạy ở thư mục gốc repository:
  python3 scripts/make_favicon.py

Nguồn: docs/GammaBookStoreAvatar.jpg (480x360, nền #202020). Vùng logo nằm trong khung
(89,40)-(392,320); crop vuông 322px quanh tâm logo (chừa lề khoảng 3%) rồi thu nhỏ.
Đầu ra:
  favicon.ico (16, 32, 48) ở thư mục gốc, vì trình duyệt tự hỏi /favicon.ico
  assets/favicon/favicon-16x16.png, favicon-32x32.png, apple-touch-icon.png (180x180)
"""
import os

from PIL import Image

SOURCE = os.path.join("docs", "GammaBookStoreAvatar.jpg")
OUT_DIR = os.path.join("assets", "favicon")
SIDE = 322
CENTER = (240.5, 180)  # tâm khung logo (89..392, 40..320)


def main():
    src = Image.open(SOURCE).convert("RGB")
    left = round(CENTER[0] - SIDE / 2)
    top = round(CENTER[1] - SIDE / 2)
    square = src.crop((left, top, left + SIDE, top + SIDE))

    os.makedirs(OUT_DIR, exist_ok=True)
    for size, name in ((16, "favicon-16x16.png"), (32, "favicon-32x32.png"), (180, "apple-touch-icon.png")):
        square.resize((size, size), Image.LANCZOS).save(os.path.join(OUT_DIR, name), optimize=True)
        print(os.path.join(OUT_DIR, name), size)
    square.resize((48, 48), Image.LANCZOS).save("favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print("favicon.ico 16/32/48")


if __name__ == "__main__":
    main()
