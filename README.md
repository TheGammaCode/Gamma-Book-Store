# Gamma-Book-Store
Trang chính thức của The Gamma. Khám phá lý thuyết tập hợp, logic và vô hạn qua một góc nhìn xa hơn. NXB ĐHQG TP.HCM.

Website HTML tĩnh, không dùng framework hay bước build. Production: https://gammabook.store/

## Cấu trúc

```
/
├── index.html                # Trang chủ
├── blog/
│   ├── index.html            # Danh sách bài viết
│   └── <slug>/index.html     # Mỗi bài một thư mục
├── assets/
│   ├── css/blog.css          # CSS chung của Blog
│   └── images/blog/<slug>.jpg
├── feed.xml                  # RSS 2.0
├── sitemap.xml
└── robots.txt
```

## Thêm bài viết mới

1. Chọn slug: chữ thường, không dấu, dùng dấu gạch ngang (ví dụ `nghich-ly-luat-su-va-nguoi-hoc-tro`).
2. Lưu ảnh tại `assets/images/blog/<slug>.jpg`.
3. Tạo `blog/<slug>/index.html` bằng cách sao chép bài hiện có. Mỗi bài phải có:
   - SEO metadata (title, description, robots)
   - canonical
   - Open Graph và Twitter Card
   - RSS autodiscovery
   - Metricool tracking (đúng một lần)
   - JSON-LD `BlogPosting`
4. Cập nhật `blog/index.html`, `feed.xml` và `sitemap.xml`.

## Deploy

commit → push `main` → Netlify tự deploy.

Không đưa token, API key hay credential vào Git.
