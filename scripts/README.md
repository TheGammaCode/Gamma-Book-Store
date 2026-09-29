# scripts/

Công cụ chạy trên máy tác giả. Netlify chỉ phục vụ file tĩnh, không chạy các script này.

| Script | Việc làm | Yêu cầu |
| --- | --- | --- |
| `latex_to_blog.py` | Chuyển `content/blog/<slug>.tex` + `<slug>.json` thành `blog/<slug>/index.html` | Python 3 (thư viện chuẩn) |
| `optimize_images.py` | Tạo ảnh web 1600/1200/800 và ảnh Open Graph 1200x630 từ ảnh nguồn | Python 3 + Pillow |
| `validate_site.py` | Kiểm tra HTML, JSON-LD, RSS, sitemap, ảnh và HTTP local | Python 3 (thư viện chuẩn) |

```
python3 scripts/latex_to_blog.py content/blog/<slug>.tex --check      # chỉ kiểm tra
python3 scripts/latex_to_blog.py content/blog/<slug>.tex              # ghi blog/<slug>/index.html
python3 scripts/latex_to_blog.py content/blog/<slug>.tex --fragment   # in phần thân bài
python3 scripts/optimize_images.py assets/images/source/<slug>-original.jpg <slug> --og-top 270
python3 scripts/validate_site.py
python3 -m unittest discover -s tests -v                              # test bộ chuyển đổi
```

`latex_to_blog.py` không chạy TeX, không dùng shell và chỉ đọc file trong `content/blog/`.
Lệnh ngoài tập con được hỗ trợ sẽ báo lỗi kèm số dòng, không bị bỏ qua âm thầm.
Chi tiết tập lệnh hỗ trợ: [docs/latex-blog-authoring.md](../docs/latex-blog-authoring.md).
