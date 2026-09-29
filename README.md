# Gamma-Book-Store
Trang chính thức của The Gamma. Khám phá lý thuyết tập hợp, logic và vô hạn qua một góc nhìn xa hơn. NXB ĐHQG TP.HCM.

Website HTML tĩnh, không framework và không bước build phía Netlify. Production: https://gammabook.store/

## Cấu trúc

```
/
├── index.html                       # Trang chủ
├── blog/
│   ├── index.html                   # Danh sách bài viết
│   └── <slug>/index.html            # Sinh từ content/blog/<slug>.tex
├── content/blog/
│   ├── <slug>.tex                   # Nguồn bài (tập con LaTeX)
│   └── <slug>.json                  # Metadata bài
├── assets/
│   ├── css/blog.css
│   └── images/
│       ├── source/<slug>-original.jpg   # Ảnh gốc, không dùng trong HTML
│       └── blog/<slug>-{1600,1200,800,og}.jpg
├── scripts/                         # latex_to_blog.py, optimize_images.py, validate_site.py
├── tests/                           # test bộ chuyển đổi
├── docs/latex-blog-authoring.md     # Tập LaTeX được hỗ trợ và quy trình chi tiết
├── feed.xml                         # RSS 2.0
├── sitemap.xml
└── robots.txt
```

## Bài viết hiện có

- Nghịch lý Protagoras: Học Phí Một Nửa: `/blog/nghich-ly-luat-su-va-nguoi-hoc-tro/`

## Thêm bài mới

Slug: chữ thường, không dấu, nối bằng dấu gạch ngang.

1. Tạo nguồn `content/blog/<slug>.tex`.
2. Tạo metadata `content/blog/<slug>.json` (mẫu: bài hiện có).
3. Đặt ảnh gốc vào `assets/images/source/<slug>-original.jpg`.
4. Tạo ảnh web: `python3 scripts/optimize_images.py assets/images/source/<slug>-original.jpg <slug>` (cần Pillow; ảnh OG phải dưới 1 MB).
5. Chuyển đổi: `python3 scripts/latex_to_blog.py content/blog/<slug>.tex`.
6. Cập nhật thẻ bài trong `blog/index.html`.
7. Cập nhật `feed.xml` (thêm `<item>`, cập nhật `lastBuildDate`).
8. Cập nhật `sitemap.xml`.
9. Kiểm tra: `python3 scripts/validate_site.py` và `python3 -m unittest discover -s tests`.
10. Commit và push `main`.
11. Netlify tự deploy.

Lưu ý:

- Chỉ dùng tập con LaTeX được hỗ trợ và các macro ThamChieu đã whitelist (`\pl`, `\plpl`, `\mnt`, `\mnn`, `\mnv`, `\tm`, `\eng`, ...). Không paste toàn bộ preamble và không dùng `\include{ThamChieu}` trong bài.
- Không dùng macro chưa được hỗ trợ nếu chưa thêm parser và test.
- Mọi công thức phải được xem thử bằng MathJax trong trình duyệt.
- `\cite{key}` cần metadata thư mục thật trong `.json`; không bịa nguồn.
- Không đưa ảnh nguồn nhiều MB vào HTML, RSS hay metadata mạng xã hội.
- Mỗi bài cần SEO metadata, canonical, Open Graph, RSS autodiscovery, Metricool tracking và JSON-LD (bộ chuyển đổi tự thêm).

## Deploy

commit → push `main` → Netlify tự deploy.

Không đưa token, API key hay credential vào Git.
