#!/usr/bin/env python3
"""Tạo ảnh web cho một bài Blog từ ảnh nguồn (chạy trên máy tác giả, không chạy trên Netlify).

Yêu cầu: Pillow (pip install pillow). Ảnh nguồn không bị sửa.

Ví dụ:
  python3 scripts/optimize_images.py \\
      assets/images/source/<slug>-original.jpg <slug> --og-top 270

Đầu ra trong assets/images/blog/:
  <slug>-1600.jpg, <slug>-1200.jpg, <slug>-800.jpg   (tỷ lệ giữ nguyên)
  <slug>-og.jpg                                      (1200x630, crop từ ảnh nguồn)

Mọi metadata (EXIF, GPS, thông tin thiết bị) bị loại bỏ. Ảnh được lưu JPEG progressive.
"""
import argparse
import os
import sys

from PIL import Image, ImageOps

OUT_DIR = os.path.join("assets", "images", "blog")
WIDTHS = (1600, 1200, 800)
OG_SIZE = (1200, 630)
QUALITY = 85


def save_jpeg(img, path):
    # Không truyền exif/icc: Pillow không ghi metadata nào của ảnh nguồn.
    img.save(path, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    print(f"{path}: {img.size[0]}x{img.size[1]}, {os.path.getsize(path) / 1024:.0f} KB")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("slug")
    ap.add_argument("--og-top", type=int, default=None,
                    help="tọa độ y (px, trên ảnh nguồn) của mép trên vùng crop Open Graph; mặc định căn giữa")
    args = ap.parse_args()

    src = Image.open(args.source)
    src = ImageOps.exif_transpose(src).convert("RGB")
    w, h = src.size

    os.makedirs(OUT_DIR, exist_ok=True)
    for width in WIDTHS:
        height = round(h * width / w)
        save_jpeg(src.resize((width, height), Image.LANCZOS), os.path.join(OUT_DIR, f"{args.slug}-{width}.jpg"))

    crop_h = round(w * OG_SIZE[1] / OG_SIZE[0])
    if crop_h > h:
        sys.exit("Ảnh nguồn không đủ cao để crop tỷ lệ 1.91:1 mà không kéo giãn.")
    top = (h - crop_h) // 2 if args.og_top is None else args.og_top
    if not 0 <= top <= h - crop_h:
        sys.exit(f"--og-top phải nằm trong khoảng 0..{h - crop_h}")
    og = src.crop((0, top, w, top + crop_h)).resize(OG_SIZE, Image.LANCZOS)
    save_jpeg(og, os.path.join(OUT_DIR, f"{args.slug}-og.jpg"))


if __name__ == "__main__":
    main()
