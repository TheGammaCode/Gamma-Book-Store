# Viết bài Blog bằng LaTeX

Tài liệu kỹ thuật cho tác giả và Claude Code. Không chứa ảnh production.

## 1. Phạm vi

Đây là **tập con LaTeX dành cho Blog**, không phải toàn bộ preamble hay hệ ThamChieu của sách.
Không paste preamble vào bài, không dùng `\include{ThamChieu}`. Macro riêng của sách chỉ dùng được
nếu đã được whitelist trong `scripts/latex_to_blog.py` (bảng bên dưới).

## 2. Môi trường hỗ trợ

| LaTeX | HTML |
| --- | --- |
| `\begin{vd}{Tiêu đề}` ... `\end{vd}` | khung Ví dụ (`.gamma-example`, viền và tiêu đề màu Ochre) |
| `\begin{itemize}` ... `\item` ... `\end{itemize}` | `<ul><li>` |
| `\section*{...}`, `\subsection*{...}` | `<section>` + `<h2>` / `<h3>` (không đánh số) |
| đoạn văn (cách nhau một dòng trống) | `<p>` |

`vd` không được lồng nhau. `\item` chỉ chứa văn bản và công thức, chưa hỗ trợ đoạn thứ hai hay môi trường lồng.
Tiêu đề bài (H1) lấy từ metadata, không viết `\section` cho H1.

## 3. Macro hỗ trợ

| LaTeX | Kết quả |
| --- | --- |
| `\tm{x}`, `\emph{x}` | `<em>x</em>` |
| `\textit{x}` | `<i>x</i>` |
| `\textbf{x}` | `<strong>x</strong>` |
| `\eng{x}` | `<span class="english-term">x</span>` |
| `\cite{key}` | liên kết `[n]` tới mục Tài liệu tham khảo (xem mục 6) |
| `\pl` | `\Rightarrow` |
| `\plpl` | `\Leftrightarrow` |
| `\mnt{x}` | `\left(x\right)` |
| `\mnn{x}` | `\left\{x\right\}` |
| `\mnv{x}` | `\left[x\right]` |

Macro trong công thức được khai triển ngay khi chuyển đổi, nên HTML chỉ chứa TeX chuẩn.
Trang bài vẫn khai báo cùng các macro trong cấu hình MathJax như lớp an toàn thứ hai.
Ký hiệu chuẩn của amsmath/amssymb mà MathJax hỗ trợ (`\neg`, `\vee`, `\wedge`, `\models`,
`\Rightarrow`, `\Leftrightarrow`, `\qquad`, ...) được giữ nguyên. Các môi trường toán cho phép:
`aligned`, `gathered`, `split`, `cases`, `array`, `matrix`, `pmatrix`, `bmatrix`, `vmatrix`, `Bmatrix`, `Vmatrix`, `smallmatrix`.

## 4. Công thức

- Inline: `$...$` hoặc `\(...\)`.
- Display: `\[...\]`. `$$...$$` không được hỗ trợ.
- Công thức display dài sẽ cuộn ngang trong vùng công thức, không làm tràn trang.
- Mọi công thức phải được xem thử bằng MathJax trong trình duyệt trước khi xuất bản.
- Ký tự `_`, `^`, `#`, `&` chỉ dùng trong công thức (ngoài công thức phải viết `\_`, `\&`, ...).

## 5. Metadata bài

Mỗi bài có `content/blog/<slug>.json` cùng tên với `.tex`. Không suy đoán metadata từ nội dung.

| Trường | Ý nghĩa |
| --- | --- |
| `slug` | trùng tên file; chữ thường, không dấu, nối bằng `-` |
| `title`, `subtitle` | H1 và dòng phụ dưới H1 |
| `description` | meta description, Open Graph, JSON-LD, thẻ ở trang `/blog/` |
| `datePublished`, `dateModified` | `YYYY-MM-DD` |
| `readingTime` | số phút (script `--check` in ra gợi ý theo số từ) |
| `canonical` | `https://gammabook.store/blog/<slug>/` |
| `image` | tên gốc của bộ ảnh web (thường bằng slug) |
| `imageAlt` | mô tả ảnh, chỉ dựa trên điều nhìn thấy trong ảnh |
| `keywords` | danh sách từ khóa trung tính |
| `citations` | danh sách `{ "key", "text", "url"? }` (mục 6) |
| `rssDescription` | mô tả cho `feed.xml` (văn bản thường, không LaTeX) |
| `note` | ghi chú cuối bài |

## 6. Citation

`\cite{key}` chỉ hợp lệ khi `key` có trong `citations` của file `.json`, với `text` là dòng tài liệu
tham khảo đầy đủ và **có thật** (tác giả, tên, năm, nguồn). Không có metadata thì bộ chuyển đổi báo lỗi.
Không bịa tác giả, tên bài, năm, DOI hay URL; không tải nguồn từ mạng khi build.
Hiện bài Protagoras chưa có citation nào (repository không có dữ liệu cho `lisanyuk2017protagoras`).

## 7. Chạy bộ chuyển đổi

```
python3 scripts/latex_to_blog.py content/blog/<slug>.tex --check
python3 scripts/latex_to_blog.py content/blog/<slug>.tex
```

Kết quả ghi vào `blog/<slug>/index.html` (đầy đủ head, Open Graph, JSON-LD, RSS autodiscovery,
Metricool lấy nguyên từ `index.html`, MathJax chỉ khi bài có công thức). Cùng đầu vào cho cùng đầu ra.

## 8. Ảnh

1. Đặt ảnh gốc vào `assets/images/source/<slug>-original.jpg` (không chỉnh sửa).
2. Chạy `python3 scripts/optimize_images.py assets/images/source/<slug>-original.jpg <slug> [--og-top Y]`.
3. Script tạo `assets/images/blog/<slug>-1600.jpg`, `-1200.jpg`, `-800.jpg` (JPEG progressive, chất lượng 85, giữ tỷ lệ,
   không có EXIF/GPS) và `<slug>-og.jpg` (1200x630, crop từ ảnh nguồn, không kéo giãn). `--og-top` chọn mép trên của vùng crop (px trên ảnh nguồn).
4. Mục tiêu dung lượng: 1600 dưới ~500 KB, 1200 dưới ~350 KB, 800 dưới ~220 KB, OG dưới 1 MB.
5. Không dùng ảnh nguồn trong HTML, RSS hay metadata mạng xã hội. `validate_site.py` kiểm tra các ngưỡng này.

## 9. Sau khi sinh bài

Cập nhật thủ công rồi chạy `python3 scripts/validate_site.py`:

- `blog/index.html`: thêm thẻ bài (ảnh `-1200`/`srcset`, tiêu đề, mô tả, ngày, thời gian đọc, liên kết).
- `feed.xml`: thêm `<item>` (link tuyệt đối, `guid isPermaLink="true"` cố định, `pubDate` RFC 822) và cập nhật `lastBuildDate`.
- `sitemap.xml`: thêm URL bài với `lastmod`.

## 10. Ví dụ tối thiểu

`content/blog/vi-du.tex`:

```latex
\section*{Mở đầu}

Một đoạn văn có \tm{thuật ngữ} và công thức $A \pl B$.

\begin{vd}{Ví dụ}

Nếu $x \in A$ thì \[ \mnt{x \in A} \pl \mnv{x \in B}. \]

\end{vd}
```

## 11. Lệnh không hỗ trợ

Bộ chuyển đổi báo lỗi (kèm số dòng) thay vì bỏ qua âm thầm.

| Lệnh | Lý do |
| --- | --- |
| `\index`, `\makeindex` | chỉ mục chỉ có ý nghĩa trong bản in; dùng `\tm{...}` để nhấn mạnh |
| `\ref`, `\eqref`, `\nameref`, `\label` | nhãn không dùng chung với bài khác trên web |
| `\include`, `\input`, `\usepackage`, `\documentclass` | không nhúng preamble hay file ngoài vào bài |
| TikZ, `tcolorbox` nguyên bản, bố cục trang in | không có ánh xạ web |
| `\bibliography` | dùng `\cite` với metadata `citations` |
| `\\`, `$$...$$`, `\footnote`, `\textcolor` | chưa được hỗ trợ |
| macro âm nhạc, chữ tượng hình, macro riêng khác của sách | chưa whitelist; thêm vào `MATH_MACROS`/parser kèm test trước khi dùng |
