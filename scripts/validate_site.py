#!/usr/bin/env python3
"""Kiểm tra toàn bộ website tĩnh (chỉ dùng thư viện chuẩn). Chạy ở thư mục gốc repository:

  python3 scripts/validate_site.py

Kiểm tra HTML, JSON-LD, RSS, sitemap, robots, ảnh web (kích thước, định dạng, không còn
metadata EXIF/GPS) và gọi HTTP thật tới một static server tạm thời trên localhost.
Trả về mã thoát khác 0 nếu có lỗi.
"""
import functools
import http.server
import json
import re
import struct
import sys
import threading
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://gammabook.store"
SOCIAL = [
    "https://www.facebook.com/thegammabook/",
    "https://www.instagram.com/thegamma.math",
    "https://www.threads.com/@thegamma.math",
    "https://www.tiktok.com/@gammabook.store",
    "https://www.youtube.com/@gammabookstore",
]
ATOM = "{http://www.w3.org/2005/Atom}"
SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
METRICOOL_HASH = "9747b99897eb037092e02bbf953b41c9"
VOID = {"meta", "link", "img", "br", "hr", "input", "source"}
MAX_KB = {"og": 1024, "1600": 500, "1200": 350, "800": 220}

errors = []


def fail(msg):
    errors.append(msg)
    print("LỖI:", msg)


def ok(msg):
    print("ok:", msg)


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.mismatch, self.h1 = [], [], 0
        self.links, self.refs = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "h1":
            self.h1 += 1
        if tag not in VOID:
            self.stack.append(tag)
        for k in ("href", "src"):
            if a.get(k):
                self.refs.append(a[k])
        for part in (a.get("srcset") or "").split(","):
            if part.strip():
                self.refs.append(part.strip().split()[0])

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.mismatch.append(tag)
        else:
            self.stack.pop()


def jpeg_info(path):
    """Trả về (width, height, danh sách marker metadata) của file JPEG."""
    data = path.read_bytes()
    if data[:2] != b"\xff\xd8":
        raise ValueError("không phải JPEG")
    i, meta, size = 2, [], None
    while i < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker == 0xDA:
            break
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        seg = data[i + 4:i + 2 + length]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            size = struct.unpack(">HH", seg[1:5])[::-1]
        if marker == 0xE1:  # APP1: Exif hoặc XMP
            meta.append("Exif" if seg.startswith(b"Exif") else "APP1")
        if marker == 0xED:  # APP13: IPTC/Photoshop
            meta.append("IPTC")
        if marker == 0xFE:
            meta.append("COM")
        i += 2 + length
    return size[0], size[1], meta


def check_html():
    pages = [ROOT / "index.html", ROOT / "blog" / "index.html"]
    pages += sorted((ROOT / "blog").glob("*/index.html"))
    all_refs = {}
    for path in pages:
        rel = "/" + str(path.relative_to(ROOT).parent).replace("\\", "/") + "/"
        rel = "/" if rel == "/./" else rel
        text = path.read_text(encoding="utf-8")
        name = str(path.relative_to(ROOT))
        p = Page()
        p.feed(text)
        if p.stack or p.mismatch:
            fail(f"{name}: thẻ HTML không cân bằng {p.stack} {p.mismatch}")
        if p.h1 != 1:
            fail(f"{name}: có {p.h1} thẻ h1 (cần đúng 1)")
        if text.count("tracker.metricool.com") != 1 or text.count(METRICOOL_HASH) != 1:
            fail(f"{name}: Metricool tracking phải xuất hiện đúng một lần")
        if f'href="{SITE}/feed.xml"' not in text or 'type="application/rss+xml"' not in text:
            fail(f"{name}: thiếu RSS autodiscovery")
        for url in SOCIAL:
            if text.count(f'href="{url}"') < 1:
                fail(f"{name}: thiếu link mạng xã hội {url}")
        if re.search(r'href="(?:#|)"', text):
            fail(f"{name}: có href rỗng hoặc '#'")
        for tag in re.findall(r'<a [^>]*target="_blank"[^>]*>', text):
            if "noopener" not in tag:
                fail(f"{name}: link target=_blank thiếu rel noopener: {tag[:80]}")
        if "\u2014" in text:
            fail(f"{name}: chứa dấu gạch dài (em dash)")
        if ("HỘ KINH DOANH" in text) != (rel == "/"):
            fail(f"{name}: khối hộ kinh doanh chỉ được xuất hiện ở trang chủ")
        for bad in ("localhost", "/blob/", "-original", "IMG_4684", "lisanyuk"):
            if bad in text:
                fail(f"{name}: chứa '{bad}'")
        if 'charset="UTF-8"' not in text or 'name="viewport"' not in text or '<html lang="vi">' not in text:
            fail(f"{name}: thiếu charset/viewport/lang=vi")
        if rel != "/":
            m = re.findall(r'<link rel="canonical" href="([^"]+)"', text)
            if m != [SITE + rel]:
                fail(f"{name}: canonical sai {m}")
            for prop in ("og:title", "og:description", "og:url", "og:image", "twitter:card", "twitter:image"):
                if prop not in text:
                    fail(f"{name}: thiếu {prop}")
            for img in re.findall(r'content="(https://gammabook\.store/assets/images/[^"]+)"', text):
                if not img.endswith("-og.jpg"):
                    fail(f"{name}: ảnh social không phải bản -og: {img}")
        # Lệnh LaTeX thô sót lại ngoài vùng công thức.
        visible = re.sub(r"<script.*?</script>", "", text, flags=re.S)
        visible = re.sub(r"\\\[.*?\\\]|\\\(.*?\\\)", "", visible, flags=re.S)
        raw = re.findall(r"\\[A-Za-z]+", visible)
        if raw:
            fail(f"{name}: còn lệnh LaTeX thô ngoài công thức: {sorted(set(raw))}")
        # MathJax chỉ ở trang có công thức, và chỉ một lần.
        has_math = bool(re.search(r"\\\(|\\\[", re.sub(r"<script.*?</script>", "", text, flags=re.S)))
        mj = text.count("mathjax@")
        if has_math and mj != 1:
            fail(f"{name}: trang có công thức cần đúng một thẻ MathJax (có {mj})")
        if not has_math and mj:
            fail(f"{name}: trang không có công thức nhưng tải MathJax")
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S):
            try:
                ld = json.loads(block)
                if ld.get("@type") == "Organization":
                    if sorted(ld.get("sameAs", [])) != sorted(SOCIAL):
                        fail(f"{name}: Organization sameAs không khớp 5 kênh chính thức")
                    continue
                for k in ("@context", "@type", "headline", "description", "image", "datePublished",
                          "dateModified", "inLanguage", "mainEntityOfPage", "author", "publisher"):
                    if k not in ld:
                        fail(f"{name}: JSON-LD thiếu {k}")
            except json.JSONDecodeError as e:
                fail(f"{name}: JSON-LD không hợp lệ: {e}")
        all_refs[rel] = p.refs
    ok(f"HTML: {len(pages)} trang")
    return all_refs


def check_feed_sitemap(pages):
    articles = sorted(p.parent.name for p in (ROOT / "blog").glob("*/index.html"))
    urls = {f"{SITE}/blog/{a}/" for a in articles}
    try:
        ch = ET.parse(ROOT / "feed.xml").getroot()
    except ET.ParseError as e:
        return fail(f"feed.xml không parse được: {e}")
    if ch.tag != "rss" or ch.get("version") != "2.0":
        fail("feed.xml không phải RSS 2.0")
    ch = ch.find("channel")
    for tag in ("title", "link", "description", "language", "lastBuildDate"):
        if ch.find(tag) is None or not (ch.find(tag).text or "").strip():
            fail(f"feed.xml: channel thiếu {tag}")
    parsedate_to_datetime(ch.find("lastBuildDate").text)
    selfl = ch.find(ATOM + "link")
    if selfl is None or selfl.get("rel") != "self" or selfl.get("href") != f"{SITE}/feed.xml":
        fail("feed.xml: thiếu atom:link self đúng")
    items = ch.findall("item")
    if {i.find("link").text for i in items} != urls or len(items) != len(urls):
        fail("feed.xml: các item không khớp với các bài trong blog/")
    for i in items:
        g = i.find("guid")
        if g is None or g.get("isPermaLink") != "true" or g.text != i.find("link").text:
            fail("feed.xml: guid phải là permalink trùng link")
        parsedate_to_datetime(i.find("pubDate").text)
        for tag in ("title", "description"):
            if not (i.find(tag).text or "").strip():
                fail(f"feed.xml: item thiếu {tag}")
        if "\\" in (i.find("description").text or ""):
            fail("feed.xml: description chứa LaTeX thô")
    ok(f"feed.xml: RSS 2.0, {len(items)} item")

    try:
        sm = ET.parse(ROOT / "sitemap.xml").getroot()
    except ET.ParseError as e:
        return fail(f"sitemap.xml không parse được: {e}")
    locs = [u.find(SM + "loc").text for u in sm.findall(SM + "url")]
    expected = [f"{SITE}/", f"{SITE}/blog/"] + sorted(urls)
    if sorted(locs) != sorted(expected):
        fail(f"sitemap.xml: URL không khớp. Có {locs}, cần {expected}")
    for u in sm.findall(SM + "url"):
        lm = u.find(SM + "lastmod")
        if lm is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", lm.text):
            fail("sitemap.xml: lastmod sai định dạng")
    ok(f"sitemap.xml: {len(locs)} URL")

    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    if f"Sitemap: {SITE}/sitemap.xml" not in robots or "Disallow" in robots:
        fail("robots.txt không đúng")
    else:
        ok("robots.txt")


def check_images():
    base = ROOT / "assets" / "images" / "blog"
    files = sorted(base.glob("*.jpg"))
    if not files:
        fail("không có ảnh web trong assets/images/blog/")
    for f in files:
        try:
            w, h, meta = jpeg_info(f)
        except Exception as e:
            fail(f"{f.name}: {e}")
            continue
        kb = f.stat().st_size / 1024
        suffix = f.stem.rsplit("-", 1)[-1]
        if meta:
            fail(f"{f.name}: còn metadata {meta}")
        if suffix in MAX_KB and kb > MAX_KB[suffix]:
            fail(f"{f.name}: {kb:.0f} KB vượt {MAX_KB[suffix]} KB")
        if suffix == "og" and (w, h) != (1200, 630):
            fail(f"{f.name}: ảnh OG phải 1200x630, đang {w}x{h}")
        if suffix.isdigit() and (w != int(suffix) or abs(w / h - 1.5) > 0.01):
            fail(f"{f.name}: kích thước/tỷ lệ 3:2 sai ({w}x{h})")
        print(f"     {f.name}: {w}x{h}, {kb:.0f} KB, metadata: {meta or 'không'}")
    for src in (ROOT / "assets" / "images" / "source").glob("*"):
        print(f"     nguồn giữ nguyên: {src.name}, {src.stat().st_size / 1024 / 1024:.1f} MB")
    ok(f"ảnh web: {len(files)} file")


def check_http(all_refs):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    paths = set(all_refs) | {"/feed.xml", "/sitemap.xml", "/robots.txt", "/assets/css/blog.css"}
    for refs in all_refs.values():
        for r in refs:
            if r.startswith(SITE):
                r = r[len(SITE):]
            if r.startswith("/") and not r.startswith("//"):
                paths.add(r.split("#")[0])
    try:
        for path in sorted(paths):
            try:
                with urllib.request.urlopen(base + path, timeout=10) as r:
                    r.read()
                    status = r.status
            except Exception as e:
                status = e
            if status != 200:
                fail(f"HTTP {status} cho {path}")
        ok(f"HTTP local: {len(paths)} đường dẫn trả 200")
    finally:
        server.shutdown()


def main():
    refs = check_html()
    check_feed_sitemap(refs)
    check_images()
    check_http(refs)
    if errors:
        print(f"\n{len(errors)} lỗi.")
        return 1
    print("\nTất cả kiểm tra đạt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
