"""Test cho scripts/latex_to_blog.py. Chạy: python3 -m unittest discover -s tests -v"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import latex_to_blog as lb  # noqa: E402


def conv(src, citations=()):
    body, has_math, refs = lb.convert(src, citations)
    return body


class ConverterTests(unittest.TestCase):
    def test_vd_environment(self):
        html = conv("\\begin{vd}{Tiêu đề (Title)}\n\nNội dung.\n\n\\end{vd}")
        self.assertIn('class="gamma-example"', html)
        self.assertIn('class="gamma-example__title"', html)
        self.assertIn("Tiêu đề (Title)", html)
        self.assertIn("<p>Nội dung.</p>", html)

    def test_inline_commands(self):
        html = conv("Từ \\tm{khóa} và \\eng{key term}, \\textit{nghiêng}, \\textbf{đậm}, \\emph{nhấn}.")
        self.assertIn("<em>khóa</em>", html)
        self.assertIn('<span class="english-term">key term</span>', html)
        self.assertIn("<i>nghiêng</i>", html)
        self.assertIn("<strong>đậm</strong>", html)
        self.assertIn("<em>nhấn</em>", html)

    def test_custom_math_macros(self):
        html = conv("$A \\pl B$ và $A \\plpl B$ và $\\mnt{x}\\mnn{y}\\mnv{z}$.")
        self.assertIn(r"\(A \Rightarrow B\)", html)
        self.assertIn(r"\(A \Leftrightarrow B\)", html)
        self.assertIn(r"\left(x\right)\left\{y\right\}\left[z\right]", html)
        for macro in ("\\pl ", "\\plpl", "\\mnt", "\\mnn", "\\mnv"):
            self.assertNotIn(macro, html)

    def test_nested_macro_argument(self):
        html = conv("\\[\\mnt{a \\pl \\mnv{b}}\\]")
        self.assertIn(r"\left(a \Rightarrow \left[b\right]\right)", html)

    def test_math_delimiters(self):
        html = conv("Inline $x$ và \\(y\\).\n\n\\[\nz \\models w\n\\]\n")
        self.assertIn(r"\(x\)", html)
        self.assertIn(r"\(y\)", html)
        self.assertIn('<div class="math-display">', html)
        self.assertIn(r"z \models w", html)

    def test_standard_symbols_pass_through(self):
        html = conv("$\\neg P \\vee Q \\wedge R \\Rightarrow S \\Leftrightarrow T \\models U$")
        for sym in ("\\neg", "\\vee", "\\wedge", "\\Rightarrow", "\\Leftrightarrow", "\\models"):
            self.assertIn(sym, html)

    def test_itemize(self):
        html = conv("\\begin{itemize}\n  \\item Một\n  \\item Hai $x$\n\\end{itemize}")
        self.assertEqual(html.count("<li>"), 2)
        self.assertIn("<ul>", html)
        self.assertIn(r"<li>Hai \(x\)</li>", html)

    def test_vietnamese_utf8_preserved(self):
        text = "Nghịch lý Protagoras: “thắng” hay “thua”, tòa án, luật sư già."
        self.assertIn(text, conv(text))

    def test_sections_and_paragraphs(self):
        html = conv("\\section*{Mục một}\n\nĐoạn một.\n\nĐoạn hai.\n\n\\subsection*{Mục nhỏ}\n\nĐoạn ba.")
        self.assertIn("<h2>Mục một</h2>", html)
        self.assertIn("<h3>Mục nhỏ</h3>", html)
        self.assertEqual(html.count("<p>"), 3)

    def test_comment_only_line_does_not_split_paragraph(self):
        html = conv("Dòng một\n% ghi chú\ndòng hai\n")
        self.assertEqual(html.count("<p>"), 1)
        self.assertIn("Dòng một dòng hai", html)

    def test_text_is_escaped(self):
        html = conv("Nếu a < b và c > d thì <script>alert(1)</script> \\& hết.")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("a &lt; b", html)
        self.assertIn("&amp; hết", html)

    def test_math_is_escaped(self):
        html = conv("$a < b$")
        self.assertIn(r"\(a &lt; b\)", html)

    def test_unsupported_commands_raise(self):
        cases = [
            "\\index{x}", "\\ref{a}", "\\input{x}", "\\include{x}", "\\label{a}", "\\footnote{x}",
            "\\unknowncmd{x}", "\\begin{tikzpicture}\\end{tikzpicture}", "\\begin{tcolorbox}\\end{tcolorbox}",
            "\\\\", "$$x$$", "A_b",
        ]
        for src in cases:
            with self.subTest(src=src):
                with self.assertRaises(lb.LatexError):
                    conv(src)

    def test_unsupported_math_commands_raise(self):
        for src in ("$\\input{x}$", "$\\href{u}{t}$", "$\\newcommand{\\a}{b}$", "$\\begin{tikzpicture}$"):
            with self.subTest(src=src):
                with self.assertRaises(lb.LatexError):
                    conv(src)

    def test_error_reports_line_number(self):
        try:
            conv("Dòng 1\n\nDòng 3 \\index{x}")
        except lb.LatexError as e:
            self.assertEqual(e.line, 3)
        else:
            self.fail("phải báo lỗi")

    def test_structural_errors(self):
        for src in ("\\begin{vd}{A}\nnội dung", "\\end{vd}", "$x", "\\(x", "\\tm{chưa đóng",
                    "\\begin{itemize}\\item a", "\\begin{itemize}\n\\end{itemize}", "}", "$\\frac{1$"):
            with self.subTest(src=src):
                with self.assertRaises(lb.LatexError):
                    conv(src)

    def test_cite_requires_metadata(self):
        with self.assertRaises(lb.LatexError):
            conv("Xem \\cite{khong-co}.")
        cites = [{"key": "k1", "text": "Tác giả A. Tên sách. 2020."}]
        body, _, refs = lb.convert("Xem \\cite{k1}.", cites)
        self.assertIn('<a href="#ref-k1">[1]</a>', body)
        self.assertIn("Tác giả A. Tên sách. 2020.", refs)

    def test_no_content_lost(self):
        src = "Một \\tm{hai} ba $x$ bốn.\n\n\\begin{itemize}\\item năm\\end{itemize}\n\nsáu \\[y\\] bảy"
        html = conv(src)
        for word in ("Một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "x", "y"):
            self.assertIn(word, html)

    def test_deterministic(self):
        src = (ROOT / "content" / "blog" / "nghich-ly-luat-su-va-nguoi-hoc-tro.tex").read_text(encoding="utf-8")
        self.assertEqual(lb.convert(src), lb.convert(src))

    def test_real_article_page(self):
        tex = ROOT / "content" / "blog" / "nghich-ly-luat-su-va-nguoi-hoc-tro.tex"
        meta, body, has_math, refs = lb.build(tex)
        page1 = lb.render_page(meta, body, has_math, refs)
        page2 = lb.render_page(meta, body, has_math, refs)
        self.assertEqual(page1, page2)
        self.assertTrue(has_math)
        self.assertEqual(page1.count("tracker.metricool.com"), 1)
        self.assertEqual(page1.count("<h1>"), 1)
        self.assertTrue(page1.rstrip().endswith("</html>"))
        # Trang đã commit phải khớp với bản sinh ra từ nguồn .tex.
        committed = (ROOT / "blog" / meta["slug"] / "index.html").read_text(encoding="utf-8")
        self.assertEqual(committed, page1)
        self.assertNotIn("HỘ KINH DOANH", page1)
        # Khối hỏi đáp Messenger: đúng một khối, trỏ tới Page chính thức, nằm trước hàng điều hướng cuối bài.
        self.assertEqual(page1.count('class="ask"'), 1)
        self.assertEqual(page1.count("https://m.me/thegammabook"), 1)
        self.assertIn("Có câu hỏi hoặc góc nhìn khác? Nhắn tin cho Gamma Book Store.", page1)
        self.assertIn("Hỏi về bài viết qua Messenger", page1)
        self.assertEqual(page1.count('class="ask__fallback"'), 1)
        self.assertIn('href="https://www.facebook.com/thegammabook/"', page1[page1.index('class="ask__fallback"'):])
        self.assertLess(page1.index('class="ask"'), page1.index('class="cta-row"'))
        self.assertGreater(page1.index('class="ask"'), page1.index('class="note"'))
        self.assertLess(page1.index('class="cta-row"'), page1.index("<footer"))
        self.assertNotIn("\u2014", page1)
        for raw in ("\\begin{vd}", "\\tm{", "\\pl", "\\mnt", "\\mnn", "\\mnv", "\\cite", "lisanyuk"):
            self.assertNotIn(raw, page1)

    def _meta_with(self, **changes):
        import json
        import tempfile
        meta = json.loads((ROOT / "content" / "blog" / "nghich-ly-luat-su-va-nguoi-hoc-tro.json").read_text(encoding="utf-8"))
        meta.update(changes)
        tmp = Path(tempfile.mkdtemp()) / "nghich-ly-luat-su-va-nguoi-hoc-tro.json"
        tmp.write_text(json.dumps(meta), encoding="utf-8")
        return tmp

    def test_unapproved_image_is_refused(self):
        with self.assertRaises(lb.LatexError):
            lb.load_meta(self._meta_with(imageApproved=False), "nghich-ly-luat-su-va-nguoi-hoc-tro")

    def test_image_source_validation(self):
        slug = "nghich-ly-luat-su-va-nguoi-hoc-tro"
        bad = [
            {"type": "drive", "fileId": "https://drive.google.com/file/d/abc/view"},
            {"type": "drive"},
            {"type": "upload", "path": "../secret.jpg"},
            {"type": "upload", "path": "assets/images/source/khong-ton-tai.jpg"},
            {"type": "web", "url": "https://example.com/a.jpg"},
        ]
        for src in bad:
            with self.subTest(src=src):
                with self.assertRaises(lb.LatexError):
                    lb.load_meta(self._meta_with(imageSource=src), slug)
        ok = {"type": "drive", "fileId": "1959YVfbMNPpkNXjeTN9Q9VJ5GvCTMQZP"}
        lb.load_meta(self._meta_with(imageSource=ok), slug)

    def test_image_source_not_rendered(self):
        tex = ROOT / "content" / "blog" / "nghich-ly-luat-su-va-nguoi-hoc-tro.tex"
        meta, body, has_math, refs = lb.build(tex)
        page = lb.render_page(meta, body, has_math, refs)
        self.assertNotIn("imageSource", page)
        self.assertNotIn("assets/images/source", page)
        self.assertNotIn("drive.google.com", page)

    def test_favicon_tags_in_template(self):
        tex = ROOT / "content" / "blog" / "nghich-ly-luat-su-va-nguoi-hoc-tro.tex"
        page = lb.render_page(*lb.build(tex))
        for href in ("/favicon.ico", "/assets/favicon/favicon-32x32.png",
                     "/assets/favicon/favicon-16x16.png", "/assets/favicon/apple-touch-icon.png"):
            self.assertIn(f'href="{href}"', page)

    def test_css_has_no_character_width_caps(self):
        # Chống tái phát: max-width theo ký tự (ch) làm khối chữ hẹp hơn ảnh và khung Ví dụ.
        css = (ROOT / "assets" / "css" / "blog.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"max-width:\s*[\d.]+ch")

    def test_brand_name_is_unified(self):
        import re
        self.assertEqual(lb.BRAND, "Gamma Book Store")
        tex = ROOT / "content" / "blog" / "nghich-ly-luat-su-va-nguoi-hoc-tro.tex"
        meta, body, has_math, refs = lb.build(tex)
        page = lb.render_page(meta, body, has_math, refs)
        # Ngoại lệ được phép: tên tác phẩm trong nội dung bài (\eng{...}) chỉ gồm "Protagoras Paradox".
        self.assertNotIn("The Gamma", page)
        self.assertIn('<meta property="og:site_name" content="Gamma Book Store">', page)
        self.assertIn('<a class="brand" href="/">Gamma Book Store</a>', page)
        self.assertIn("| Gamma Book Store</title>", page)
        self.assertIn("Khám phá Gamma Book Store", page)
        self.assertEqual(page.count('"name": "Gamma Book Store"'), 2)
        for path in ("content/blog/nghich-ly-luat-su-va-nguoi-hoc-tro.json", "feed.xml", "blog/index.html"):
            text = (ROOT / path).read_text(encoding="utf-8")
            self.assertNotIn("The Gamma", text, path)
            self.assertNotIn("THE GAMMA", text, path)

    def test_input_path_is_restricted(self):
        with self.assertRaises(lb.LatexError):
            lb.resolve_input(str(ROOT / "README.md"))
        with self.assertRaises(lb.LatexError):
            lb.resolve_input("/etc/passwd")


if __name__ == "__main__":
    unittest.main()
