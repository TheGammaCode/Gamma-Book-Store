#!/usr/bin/env python3
"""Chuyển một bài Blog viết bằng tập con LaTeX thành trang HTML tĩnh.

Chỉ dùng thư viện chuẩn của Python. Bộ chuyển đổi KHÔNG chạy TeX, không dùng shell,
không thực thi lệnh nào trong file nguồn và chỉ đọc file trong content/blog/.

Cách dùng (chạy ở thư mục gốc repository):
  python3 scripts/latex_to_blog.py content/blog/<slug>.tex            # ghi blog/<slug>/index.html
  python3 scripts/latex_to_blog.py content/blog/<slug>.tex --check    # chỉ kiểm tra, không ghi
  python3 scripts/latex_to_blog.py content/blog/<slug>.tex --fragment # in phần thân bài ra stdout

Metadata của bài nằm trong content/blog/<slug>.json (xem docs/latex-blog-authoring.md).
"""
import argparse
import bisect
import html
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "content" / "blog"
OUT_DIR = ROOT / "blog"
SITE = "https://gammabook.store"
BRAND = "Gamma Book Store"  # tên thương hiệu hiển thị (không dùng "The Gamma")
# Cuộc trò chuyện Messenger với đúng Facebook Page chính thức (https://www.facebook.com/thegammabook/).
MESSENGER_URL = "https://m.me/thegammabook"
# Kênh mạng xã hội chính thức (nguồn duy nhất; cùng danh sách với footer và trang chủ).
SOCIAL_URLS = [
    "https://www.facebook.com/thegammabook/",
    "https://www.instagram.com/thegamma.math",
    "https://www.threads.com/@thegamma.math",
    "https://www.tiktok.com/@gammabook.store",
    "https://www.youtube.com/@gammabookstore",
    "https://www.pinterest.com/thegammamath/",
]

MATHJAX_URL = "https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js"
MATHJAX_SRI = "sha384-KKWa9jJ1MZvssLeOoXG6FiOAZfAgmzsIIfw8BXwI9+kYm0lPCbC6yTQPBC00F1/L"

# ---------------------------------------------------------------- lỗi


class LatexError(Exception):
    def __init__(self, message, line=None):
        super().__init__(message)
        self.line = line


# ---------------------------------------------------------------- macro toán

# Macro của hệ ThamChieu được whitelist, khai triển ngay khi chuyển đổi để HTML không
# phụ thuộc vào cấu hình MathJax (trang bài vẫn khai báo cùng macro như một lớp an toàn thứ hai).
MATH_MACROS = {
    "plpl": (0, r"\Leftrightarrow"),
    "pl": (0, r"\Rightarrow"),
    "mnt": (1, r"\left(#1\right)"),
    "mnn": (1, r"\left\{#1\right\}"),
    "mnv": (1, r"\left[#1\right]"),
}

# Lệnh không có ý nghĩa (hoặc nguy hiểm) trong công thức trên web.
FORBIDDEN_MATH = {
    "input", "include", "write", "def", "gdef", "edef", "xdef", "let", "newcommand",
    "renewcommand", "providecommand", "csname", "href", "url", "require", "class",
    "style", "unicode", "usepackage", "index", "label", "ref", "eqref", "nameref",
    "cite", "tikz", "includegraphics",
}
ALLOWED_MATH_ENVS = {
    "aligned", "gathered", "split", "cases", "array", "matrix", "pmatrix", "bmatrix",
    "vmatrix", "Bmatrix", "Vmatrix", "smallmatrix",
}

# Lệnh văn bản không hỗ trợ, kèm lý do (để báo lỗi rõ ràng, không bỏ qua âm thầm).
UNSUPPORTED_TEXT = {
    "index": "\\index không dùng trên web; dùng \\tm{...} để nhấn mạnh thuật ngữ",
    "makeindex": "không hỗ trợ chỉ mục",
    "ref": "không hỗ trợ tham chiếu chéo trong Blog",
    "eqref": "không hỗ trợ tham chiếu chéo trong Blog",
    "nameref": "không hỗ trợ tham chiếu chéo trong Blog",
    "label": "không hỗ trợ nhãn trong Blog",
    "include": "không hỗ trợ \\include; không nhúng ThamChieu vào bài Blog",
    "input": "không hỗ trợ \\input; không nhúng ThamChieu vào bài Blog",
    "usepackage": "không đặt preamble trong bài Blog",
    "documentclass": "không đặt preamble trong bài Blog",
    "bibliography": "dùng \\cite{key} kèm metadata citations trong file .json",
    "includegraphics": "ảnh được khai báo trong metadata, không nhúng trong .tex",
    "tikz": "không hỗ trợ TikZ",
    "newcommand": "không định nghĩa macro mới trong bài Blog",
    "renewcommand": "không định nghĩa macro mới trong bài Blog",
    "def": "không định nghĩa macro mới trong bài Blog",
    "footnote": "chưa hỗ trợ chú thích cuối trang",
    "textcolor": "chưa hỗ trợ màu chữ",
    "newpage": "không hỗ trợ bố cục trang in",
    "clearpage": "không hỗ trợ bố cục trang in",
    "pagebreak": "không hỗ trợ bố cục trang in",
}

INLINE_TAGS = {
    "tm": ("em", None),
    "emph": ("em", None),
    "textit": ("i", None),
    "textbf": ("strong", None),
    "eng": ("span", "english-term"),
}
HEADINGS = {"section": "h2", "section*": "h2", "subsection": "h3", "subsection*": "h3"}


def expand_math(s, line):
    """Khai triển macro whitelist, chặn lệnh cấm, kiểm tra ngoặc và môi trường."""
    depth = 0
    for i, ch in enumerate(s):
        if ch in "{}" and not (i > 0 and s[i - 1] == "\\"):
            depth += 1 if ch == "{" else -1
            if depth < 0:
                raise LatexError("ngoặc } thừa trong công thức", line)
    if depth != 0:
        raise LatexError("ngoặc { chưa đóng trong công thức", line)

    out = []
    i = 0
    while i < len(s):
        if s[i] != "\\":
            out.append(s[i])
            i += 1
            continue
        env = re.match(r"\\(begin|end)\{([A-Za-z*]+)\}", s[i:])
        if env:
            if env.group(2) not in ALLOWED_MATH_ENVS:
                raise LatexError(f"môi trường toán không hỗ trợ: {env.group(2)}", line)
            out.append(env.group(0))
            i += env.end()
            continue
        m = re.match(r"\\([A-Za-z]+)", s[i:])
        if not m:
            out.append(s[i:i + 2])
            i += 2
            continue
        name = m.group(1)
        i += m.end()
        if name in FORBIDDEN_MATH:
            raise LatexError(f"lệnh không hỗ trợ trong công thức: \\{name}", line)
        if name not in MATH_MACROS:
            out.append("\\" + name)
            continue
        nargs, template = MATH_MACROS[name]
        if nargs == 0:
            out.append(template)
            continue
        while i < len(s) and s[i] in " \t":
            i += 1
        if i >= len(s) or s[i] != "{":
            raise LatexError(f"\\{name} cần một đối số trong ngoặc {{...}}", line)
        j, level = i, 0
        while j < len(s):
            if s[j] == "{" and s[j - 1] != "\\":
                level += 1
            elif s[j] == "}" and s[j - 1] != "\\":
                level -= 1
                if level == 0:
                    break
            j += 1
        arg = expand_math(s[i + 1:j], line)
        out.append(template.replace("#1", arg))
        i = j + 1
    return "".join(out)


# ---------------------------------------------------------------- lexer


def strip_comments(src):
    lines = []
    for line in src.split("\n"):
        pos = 0
        while True:
            j = line.find("%", pos)
            if j == -1:
                break
            k = j
            while k > 0 and line[k - 1] == "\\":
                k -= 1
            if (j - k) % 2 == 0:
                line = line[:j]
                # Dòng chỉ có chú thích không được tạo ra ngắt đoạn: đánh dấu bằng \x00 (bị lexer bỏ qua).
                if not line.strip():
                    line = "\x00"
                break
            pos = j + 1
        lines.append(line)
    return "\n".join(lines)


def tokenize(src):
    """Trả về danh sách token (kind, value, line)."""
    newlines = [m.start() for m in re.finditer("\n", src)]

    def lineno(i):
        return bisect.bisect_left(newlines, i) + 1

    toks, buf, buf_start = [], [], 0

    def flush():
        if buf:
            toks.append(("text", "".join(buf), lineno(buf_start)))
            buf.clear()

    def add_text(s, at):
        nonlocal buf_start
        if not buf:
            buf_start = at
        buf.append(s)

    blank = re.compile(r"\n[ \t]*\n\s*")
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "\n":
            m = blank.match(src, i)
            if m:
                flush()
                toks.append(("par", "", lineno(i)))
                i = m.end()
            else:
                add_text(" ", i)
                i += 1
        elif c == "\\":
            nxt = src[i + 1] if i + 1 < n else ""
            if nxt and nxt in "%&$#_{}":
                add_text(nxt, i)
                i += 2
            elif nxt == "(":
                end = src.find("\\)", i + 2)
                if end == -1:
                    raise LatexError("thiếu \\) để đóng công thức", lineno(i))
                flush()
                toks.append(("math", src[i + 2:end], lineno(i)))
                i = end + 2
            elif nxt == "[":
                end = src.find("\\]", i + 2)
                if end == -1:
                    raise LatexError("thiếu \\] để đóng công thức", lineno(i))
                flush()
                toks.append(("display", src[i + 2:end], lineno(i)))
                i = end + 2
            elif nxt == "\\":
                raise LatexError("\\\\ (xuống dòng cưỡng bức) không được hỗ trợ; dùng đoạn văn mới", lineno(i))
            else:
                m = re.compile(r"[A-Za-z]+\*?").match(src, i + 1)
                if not m:
                    raise LatexError(f"lệnh không hỗ trợ: \\{nxt}", lineno(i))
                name = m.group(0)
                j = m.end()
                if name in ("begin", "end"):
                    g = re.compile(r"\s*\{([A-Za-z*]+)\}").match(src, j)
                    if not g:
                        raise LatexError(f"\\{name} thiếu tên môi trường", lineno(i))
                    flush()
                    toks.append((name, g.group(1), lineno(i)))
                    i = g.end()
                else:
                    flush()
                    toks.append(("cmd", name, lineno(i)))
                    while j < n and src[j] in " \t":
                        j += 1
                    i = j
        elif c == "$":
            if src.startswith("$$", i):
                raise LatexError("$$ không được hỗ trợ; dùng \\[ ... \\] cho công thức display", lineno(i))
            j = i + 1
            while j < n and not (src[j] == "$" and src[j - 1] != "\\"):
                j += 1
            if j >= n:
                raise LatexError("thiếu $ để đóng công thức", lineno(i))
            flush()
            toks.append(("math", src[i + 1:j], lineno(i)))
            i = j + 1
        elif c in "{}":
            flush()
            toks.append((c, c, lineno(i)))
            i += 1
        elif c == "\x00":
            i += 1
        elif c == "~":
            add_text("\u00a0", i)
            i += 1
        elif c in "#^_&":
            raise LatexError(f"ký tự {c!r} chỉ dùng được trong công thức hoặc khi viết \\{c}", lineno(i))
        else:
            add_text(c, i)
            i += 1
    flush()
    return toks


# ---------------------------------------------------------------- parser -> AST
# Nút inline: ("text", s) ("math", s, display) ("tag", tag, cls, children) ("cite", key)
# Khối:       ("p", inline) ("display", s) ("heading", tag, inline) ("list", [inline]) ("example", title, [blocks])


class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.p = 0

    def peek(self):
        return self.toks[self.p] if self.p < len(self.toks) else ("eof", "", None)

    def next(self):
        t = self.peek()
        self.p += 1
        return t

    def group(self):
        kind, _, line = self.next()
        if kind != "{":
            raise LatexError("thiếu đối số trong ngoặc {...}", line)
        nodes = self.inline(stop=("}",))
        kind, _, line = self.next()
        if kind != "}":
            raise LatexError("thiếu } để đóng đối số", line)
        return nodes

    def group_text(self):
        nodes = self.group()
        if any(n[0] != "text" for n in nodes):
            raise LatexError("đối số này chỉ được chứa văn bản thường", self.toks[self.p - 1][2])
        return "".join(n[1] for n in nodes).strip()

    def is_stop(self, tok, stop):
        kind, val, _ = tok
        if kind == "eof":
            return True
        if kind in stop:
            return True
        if kind == "cmd" and ("cmd:" + val) in stop:
            return True
        return False

    def inline(self, stop):
        nodes = []
        while True:
            tok = self.peek()
            if self.is_stop(tok, stop):
                return nodes
            kind, val, line = tok
            if kind == "text":
                nodes.append(("text", val))
                self.p += 1
            elif kind == "math":
                nodes.append(("math", expand_math(val, line), False))
                self.p += 1
            elif kind == "display":
                nodes.append(("math", expand_math(val, line), True))
                self.p += 1
            elif kind == "{":
                self.p += 1
                nodes.extend(self.inline(stop=("}",)))
                k, _, ln = self.next()
                if k != "}":
                    raise LatexError("thiếu } để đóng nhóm", ln)
            elif kind == "}":
                raise LatexError("ngoặc } thừa", line)
            elif kind == "cmd":
                self.p += 1
                if val in INLINE_TAGS:
                    tag, cls = INLINE_TAGS[val]
                    nodes.append(("tag", tag, cls, self.group()))
                elif val == "cite":
                    nodes.append(("cite", self.group_text(), line))
                elif val in UNSUPPORTED_TEXT:
                    raise LatexError(f"\\{val}: {UNSUPPORTED_TEXT[val]}", line)
                else:
                    raise LatexError(f"lệnh không được hỗ trợ: \\{val}", line)
            elif kind in ("begin", "end", "par"):
                # Kết thúc đoạn; do cấp cao hơn quyết định xử lý.
                return nodes
            else:
                raise LatexError(f"token không mong đợi: {kind}", line)

    PARAGRAPH_STOP = ("par", "begin", "end", "}", "cmd:section", "cmd:section*", "cmd:subsection", "cmd:subsection*")

    def blocks(self, end_env=None):
        blocks = []
        while True:
            kind, val, line = self.peek()
            if kind == "eof":
                if end_env:
                    raise LatexError(f"thiếu \\end{{{end_env}}}", line)
                return blocks
            if kind == "par":
                self.p += 1
            elif kind == "end":
                if val != end_env:
                    raise LatexError(f"\\end{{{val}}} không khớp", line)
                self.p += 1
                return blocks
            elif kind == "begin":
                self.p += 1
                if val == "vd":
                    if end_env == "vd":
                        raise LatexError("không lồng môi trường vd", line)
                    title = self.group()
                    blocks.append(("example", title, self.blocks("vd")))
                elif val == "itemize":
                    blocks.append(self.itemize(line))
                else:
                    raise LatexError(f"môi trường không được hỗ trợ: {val}", line)
            elif kind == "cmd" and val in HEADINGS:
                self.p += 1
                blocks.append(("heading", HEADINGS[val], self.group()))
            elif kind == "display":
                self.p += 1
                blocks.append(("display", expand_math(val, line)))
            elif kind == "}":
                raise LatexError("ngoặc } thừa", line)
            else:
                nodes = self.inline(stop=self.PARAGRAPH_STOP + ("display",))
                if not self.is_blank(nodes):
                    blocks.append(("p", nodes))

    @staticmethod
    def is_blank(nodes):
        return all(n[0] == "text" and not n[1].strip() for n in nodes)

    def itemize(self, line):
        items = []
        # Bỏ khoảng trắng và ngắt đoạn trước \item đầu tiên.
        while self.peek()[0] in ("par", "text") and (self.peek()[0] == "par" or not self.peek()[1].strip()):
            self.p += 1
        while True:
            kind, val, ln = self.peek()
            if kind == "end":
                if val != "itemize":
                    raise LatexError(f"\\end{{{val}}} không khớp", ln)
                self.p += 1
                break
            if kind == "cmd" and val == "item":
                self.p += 1
                nodes = self.inline(stop=("end", "begin", "cmd:item", "par"))
                while self.peek()[0] == "par":
                    self.p += 1
                    nxt = self.peek()
                    if not (nxt[0] == "end" or (nxt[0] == "cmd" and nxt[1] == "item")):
                        raise LatexError("đoạn văn thứ hai trong một \\item chưa được hỗ trợ", nxt[2])
                if self.peek()[0] == "begin":
                    raise LatexError("môi trường lồng trong \\item chưa được hỗ trợ", self.peek()[2])
                items.append(nodes)
            elif kind == "eof":
                raise LatexError("thiếu \\end{itemize}", line)
            else:
                raise LatexError("nội dung trong itemize phải nằm sau một \\item", ln)
        if not items:
            raise LatexError("itemize rỗng", line)
        return ("list", items)


# ---------------------------------------------------------------- render


class Renderer:
    def __init__(self, citations):
        self.citations = {c["key"]: c for c in citations}
        self.cited = []
        self.has_math = False

    def inline(self, nodes):
        out = []
        for n in nodes:
            kind = n[0]
            if kind == "text":
                out.append(html.escape(re.sub(r"[ \t]+", " ", n[1]), quote=False))
            elif kind == "math":
                self.has_math = True
                body = html.escape(n[1].strip(), quote=False)
                out.append(f"\\[{body}\\]" if n[2] else f"\\({body}\\)")
            elif kind == "tag":
                inner = self.inline(n[3])
                cls = f' class="{n[2]}"' if n[2] else ""
                out.append(f"<{n[1]}{cls}>{inner}</{n[1]}>")
            elif kind == "cite":
                key = n[1]
                if key not in self.citations:
                    raise LatexError(
                        f"citation '{key}' chưa có metadata trong mục citations của file .json", n[2])
                if key not in self.cited:
                    self.cited.append(key)
                num = self.cited.index(key) + 1
                out.append(f'<a href="#ref-{html.escape(key)}">[{num}]</a>')
        return re.sub(r"[ \t]+", " ", "".join(out)).strip()

    def blocks(self, blocks, indent):
        pad = " " * indent
        out, in_section = [], False

        def close():
            nonlocal in_section
            if in_section:
                out.append(f"{pad}</section>")
                in_section = False

        for b in blocks:
            kind = b[0]
            if kind == "heading":
                close()
                out.append(f"{pad}<section>")
                in_section = True
                out.append(f"{pad}  <{b[1]}>{self.inline(b[2])}</{b[1]}>")
                continue
            if kind == "example":
                close()
                out.append(self.example(b, indent))
                continue
            inner = pad + ("  " if in_section else "")
            if kind == "p":
                out.append(f"{inner}<p>{self.inline(b[1])}</p>")
            elif kind == "display":
                self.has_math = True
                body = html.escape(b[1].strip(), quote=False)
                out.append(f'{inner}<div class="math-display">\\[{body}\\]</div>')
            elif kind == "list":
                out.append(f"{inner}<ul>")
                for item in b[1]:
                    out.append(f"{inner}  <li>{self.inline(item)}</li>")
                out.append(f"{inner}</ul>")
        close()
        return "\n".join(out)

    def example(self, b, indent):
        pad = " " * indent
        self.example_count = getattr(self, "example_count", 0) + 1
        ident = f"example-{self.example_count}"
        title = self.inline(b[1])
        inner = self.blocks(b[2], indent + 4)
        return (
            f'{pad}<div class="gamma-example" role="group" aria-labelledby="{ident}">\n'
            f'{pad}  <div class="gamma-example__header"><p class="gamma-example__title" id="{ident}">{title}</p></div>\n'
            f'{pad}  <div class="gamma-example__body">\n{inner}\n{pad}  </div>\n'
            f"{pad}</div>"
        )

    def references(self):
        if not self.cited:
            return ""
        lines = ['    <section class="references">', "      <h2>Tài liệu tham khảo</h2>", "      <ol>"]
        for key in self.cited:
            c = self.citations[key]
            text = html.escape(c["text"], quote=False)
            if c.get("url"):
                text += f' <a href="{html.escape(c["url"])}" rel="noopener">{html.escape(c["url"], quote=False)}</a>'
            lines.append(f'        <li id="ref-{html.escape(key)}">{text}</li>')
        lines += ["      </ol>", "    </section>"]
        return "\n".join(lines)


def convert(source, citations=()):
    """Trả về (body_html, has_math, references_html)."""
    parser = Parser(tokenize(strip_comments(source)))
    blocks = parser.blocks()
    r = Renderer(citations)
    body = r.blocks(blocks, 6)
    return body, r.has_math, r.references()


def word_count(body_html):
    text = re.sub(r"<[^>]+>", " ", body_html)
    return len(html.unescape(text).split())


# ---------------------------------------------------------------- metadata & trang

REQUIRED_META = [
    "slug", "title", "subtitle", "description", "datePublished", "dateModified",
    "readingTime", "canonical", "image", "imageAlt", "keywords", "citations",
    "rssDescription", "note", "imageSource", "imageApproved",
]
WORDS_PER_MINUTE = 250  # âm tiết/phút, tính cả công thức; chỉ để gợi ý readingTime
IMG_VARIANTS = ((800, 533), (1200, 800), (1600, 1067))


def load_meta(path, slug):
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise LatexError(f"thiếu file metadata {path.relative_to(ROOT)}")
    except json.JSONDecodeError as e:
        raise LatexError(f"metadata JSON không hợp lệ: {e}")
    missing = [k for k in REQUIRED_META if k not in meta]
    if missing:
        raise LatexError("metadata thiếu trường: " + ", ".join(missing))
    if meta["slug"] != slug:
        raise LatexError(f"slug trong metadata ({meta['slug']}) khác tên file ({slug})")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
        raise LatexError("slug phải viết thường, không dấu, nối bằng dấu gạch ngang")
    for k in ("datePublished", "dateModified"):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta[k]):
            raise LatexError(f"{k} phải có dạng YYYY-MM-DD")
    if meta["canonical"] != f"{SITE}/blog/{slug}/":
        raise LatexError(f"canonical phải là {SITE}/blog/{slug}/")
    if not isinstance(meta["readingTime"], int) or meta["readingTime"] < 1:
        raise LatexError("readingTime phải là số nguyên phút >= 1")
    # Ảnh phải được tác giả duyệt trước khi xuất bản; nguồn ảnh chỉ để truy vết, không đưa vào HTML.
    if meta["imageApproved"] is not True:
        raise LatexError("imageApproved phải là true: tác giả chưa duyệt ảnh cho bài này")
    src = meta["imageSource"]
    if not isinstance(src, dict) or src.get("type") not in ("drive", "upload"):
        raise LatexError('imageSource phải là {"type": "drive", "fileId": ...} hoặc {"type": "upload", "path": ...}')
    if src["type"] == "drive" and not re.fullmatch(r"[A-Za-z0-9_-]{10,}", str(src.get("fileId", ""))):
        raise LatexError("imageSource.fileId chỉ chứa mã file Drive, không dùng đường link")
    if src["type"] == "upload":
        rel = str(src.get("path", ""))
        if not rel.startswith("assets/images/source/") or not (ROOT / rel).is_file():
            raise LatexError("imageSource.path phải là file có thật trong assets/images/source/")
    for c in meta["citations"]:
        if not {"key", "text"} <= set(c):
            raise LatexError("mỗi citation cần trường key và text (dữ liệu thư mục thật)")
    return meta


def check_images(meta):
    base = ROOT / "assets" / "images" / "blog"
    names = [f"{meta['image']}-{w}.jpg" for w, _ in IMG_VARIANTS] + [f"{meta['image']}-og.jpg"]
    missing = [n for n in names if not (base / n).is_file()]
    if missing:
        raise LatexError("thiếu ảnh web: " + ", ".join(missing) + " (chạy scripts/optimize_images.py)")


def metricool_script():
    src = (ROOT / "index.html").read_text(encoding="utf-8")
    found = re.findall(r"<script>function loadScript.*?</script>", src, re.S)
    if len(found) != 1 or "tracker.metricool.com" not in found[0]:
        raise LatexError("không tìm thấy đúng một Metricool tracking code trong index.html")
    return found[0]


def date_vi(iso):
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def render_page(meta, body, has_math, references):
    a = lambda s: html.escape(s, quote=True)
    slug, base = meta["slug"], meta["image"]
    canon = meta["canonical"]
    og_img = f"{SITE}/assets/images/blog/{base}-og.jpg"
    title = a(meta["title"])
    desc = a(meta["description"])
    alt = a(meta["imageAlt"])

    ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": meta["title"],
        "alternativeHeadline": meta["subtitle"],
        "description": meta["description"],
        "image": og_img,
        "datePublished": meta["datePublished"],
        "dateModified": meta["dateModified"],
        "inLanguage": "vi-VN",
        "mainEntityOfPage": canon,
        "keywords": ", ".join(meta["keywords"]),
        "author": {"@type": "Organization", "name": BRAND, "url": SITE + "/", "sameAs": SOCIAL_URLS},
        "publisher": {"@type": "Organization", "name": BRAND, "url": SITE + "/", "sameAs": SOCIAL_URLS},
    }
    ld_json = json.dumps(ld, ensure_ascii=False, indent=2).replace("</", "<\\/")

    mathjax = ""
    if has_math:
        mathjax = f"""<script>
window.MathJax = {{
  tex: {{
    inlineMath: [['\\\\(', '\\\\)']],
    displayMath: [['\\\\[', '\\\\]']],
    processEscapes: true,
    packages: {{'[-]': ['autoload', 'require']}},
    macros: {{
      pl: '\\\\Rightarrow',
      plpl: '\\\\Leftrightarrow',
      mnt: ['\\\\left(#1\\\\right)', 1],
      mnn: ['\\\\left\\\\{{#1\\\\right\\\\}}', 1],
      mnv: ['\\\\left[#1\\\\right]', 1]
    }}
  }},
  options: {{ enableMenu: false }}
}};
</script>
<script defer src="{MATHJAX_URL}" integrity="{MATHJAX_SRI}" crossorigin="anonymous"></script>
"""

    srcset = ", ".join(f"/assets/images/blog/{base}-{w}.jpg {w}w" for w, _ in IMG_VARIANTS)
    w_full, h_full = IMG_VARIANTS[-1]
    refs = ("\n" + references) if references else ""

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{metricool_script()}
<title>{title} | {BRAND}</title>
<meta name="description" content="{desc}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{canon}">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/assets/favicon/favicon-16x16.png">
<link rel="apple-touch-icon" href="/assets/favicon/apple-touch-icon.png">
<link rel="alternate" type="application/rss+xml" title="{BRAND} Blog RSS Feed" href="{SITE}/feed.xml">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{BRAND}">
<meta property="og:locale" content="vi_VN">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{og_img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{alt}">
<meta property="article:published_time" content="{meta['datePublished']}">
<meta property="article:modified_time" content="{meta['dateModified']}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{og_img}">
<link rel="stylesheet" href="/assets/css/blog.css">
<script type="application/ld+json">
{ld_json}
</script>
{mathjax}</head>
<body>
<header class="site-header">
  <div class="inner">
    <a class="brand" href="/">{BRAND}</a>
    <nav aria-label="Điều hướng chính">
      <ul>
        <li><a href="/">Trang chủ</a></li>
        <li><a href="/blog/" aria-current="page">Blog</a></li>
      </ul>
    </nav>
  </div>
</header>

<main>
  <article class="inner">
    <header class="post-head">
      <p class="meta"><time datetime="{meta['datePublished']}">{date_vi(meta['datePublished'])}</time> · {meta['readingTime']} phút đọc</p>
      <h1>{title}</h1>
      <p class="post-subtitle">{a(meta['subtitle'])}</p>
    </header>

    <figure class="post-figure">
      <img src="/assets/images/blog/{base}-{w_full}.jpg" srcset="{srcset}" sizes="(min-width: 680px) 632px, calc(100vw - 3rem)" width="{w_full}" height="{h_full}" alt="{alt}" loading="eager" fetchpriority="high" decoding="async">
    </figure>

    <div class="post-body">
{body}
    </div>
{refs}
    <aside class="note" aria-label="Ghi chú">
      <p>{a(meta['note'])}</p>
    </aside>

    <section class="ask" aria-labelledby="ask-title">
      <p class="ask__text" id="ask-title">Có câu hỏi hoặc góc nhìn khác? Nhắn tin cho {BRAND}.</p>
      <a class="btn" href="{MESSENGER_URL}" target="_blank" rel="noopener noreferrer">Hỏi về bài viết qua Messenger</a>
    </section>

    <nav class="cta-row" aria-label="Điều hướng cuối bài">
      <a class="btn" href="/blog/">Quay lại Blog</a>
      <a class="btn" href="/">Khám phá {BRAND}</a>
    </nav>
  </article>
</main>

<footer class="site-footer">
  <div class="inner">
    <div class="follow-mini">
      <span class="follow-mini__label">Theo dõi Gamma</span>
      <ul class="follow-mini__list">
        <li><a class="follow-mini__link" href="https://www.facebook.com/thegammabook/" target="_blank" rel="noopener noreferrer" aria-label="Gamma trên Facebook"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></svg></a></li>
        <li><a class="follow-mini__link" href="https://www.instagram.com/thegamma.math" target="_blank" rel="noopener noreferrer" aria-label="Gamma trên Instagram"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg></a></li>
        <li><a class="follow-mini__link" href="https://www.threads.com/@thegamma.math" target="_blank" rel="noopener noreferrer" aria-label="Gamma trên Threads"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-4 8"/></svg></a></li>
        <li><a class="follow-mini__link" href="https://www.tiktok.com/@gammabook.store" target="_blank" rel="noopener noreferrer" aria-label="Gamma trên TikTok"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M9 12a4 4 0 1 0 4 4V4a5 5 0 0 0 5 5"/></svg></a></li>
        <li><a class="follow-mini__link" href="https://www.youtube.com/@gammabookstore" target="_blank" rel="noopener noreferrer" aria-label="Gamma trên YouTube"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M2.5 17a24.12 24.12 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.56 49.56 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.12 24.12 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.55 49.55 0 0 1-16.2 0A2 2 0 0 1 2.5 17"/><path d="m10 15 5-3-5-3z"/></svg></a></li>
        <li><a class="follow-mini__link" href="https://www.pinterest.com/thegammamath/" target="_blank" rel="noopener noreferrer" aria-label="Gamma trên Pinterest"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="10"/><path d="M10.4 21.6 12.4 11"/><path d="M8.6 12.3a3.9 3.9 0 1 1 5.8 3.4c-1.2.6-2.1.1-2.3-.9"/></svg></a></li>
      </ul>
    </div>
    <div>
      <a href="/feed.xml">RSS</a>
      &nbsp;·&nbsp;
      <a href="https://claude.ai/artifact/8Zg2hi3Mc2nTTnBJ6mN28t" target="_blank" rel="noopener">Chính sách quyền riêng tư</a>
      &nbsp;·&nbsp;
      <a href="https://claude.ai/artifact/DGJWhUZzoiTJAerfdsssLq" target="_blank" rel="noopener">Điều khoản dịch vụ</a>
    </div>
    <div>thegamma.math@gmail.com</div>
  </div>
</footer>

</body>
</html>
"""


# ---------------------------------------------------------------- CLI


def resolve_input(arg):
    path = Path(arg).resolve()
    try:
        path.relative_to(CONTENT_DIR.resolve())
    except ValueError:
        raise LatexError(f"chỉ được đọc file trong {CONTENT_DIR.relative_to(ROOT)}/")
    if path.suffix != ".tex" or not path.is_file():
        raise LatexError("đầu vào phải là một file .tex có sẵn")
    return path


def build(tex_path):
    slug = tex_path.stem
    meta = load_meta(tex_path.with_suffix(".json"), slug)
    check_images(meta)
    body, has_math, refs = convert(tex_path.read_text(encoding="utf-8"), meta["citations"])
    return meta, body, has_math, refs


def main(argv=None):
    ap = argparse.ArgumentParser(description="Chuyển bài Blog LaTeX (tập con) sang HTML.")
    ap.add_argument("tex", help="đường dẫn tới content/blog/<slug>.tex")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="chỉ kiểm tra nguồn và metadata, không ghi file")
    mode.add_argument("--fragment", action="store_true", help="in phần thân bài (HTML) ra stdout")
    args = ap.parse_args(argv)

    try:
        tex_path = resolve_input(args.tex)
        meta, body, has_math, refs = build(tex_path)
        words = word_count(body)
        estimate = max(1, math.ceil(words / WORDS_PER_MINUTE))
        if args.check:
            print(f"OK: {tex_path.name} ({words} từ, công thức: {'có' if has_math else 'không'}, "
                  f"ước tính {estimate} phút đọc; metadata ghi {meta['readingTime']})")
            return 0
        if args.fragment:
            sys.stdout.write(body + "\n")
            return 0
        page = render_page(meta, body, has_math, refs)
        out = OUT_DIR / meta["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8", newline="\n")
        print(f"Đã ghi {out.relative_to(ROOT)} ({words} từ, ước tính {estimate} phút đọc; metadata ghi {meta['readingTime']})")
        return 0
    except LatexError as e:
        where = f"{args.tex}:{e.line}: " if e.line else f"{args.tex}: "
        print(f"Lỗi: {where}{e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
