"""A local web server for the real-browser tests: the pages in tests/pages/ plus a few made on request."""
import functools
import http.server
import io
import pathlib
import threading
import time
import urllib.parse
from collections.abc import Callable, Iterator

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

#: The test pages are served on http://127.0.0.1:18030. A fixed port, so a page can
#: be opened in a browser by hand while a test is being debugged.
PORT = 18030
PAGES = pathlib.Path(__file__).resolve().parent / "pages"
#: How long /slow/... waits before it answers: long enough to arrive after the load event.
SLOW_SECONDS = 1

#: /tall?height=<px>: a page exactly that high, fractions included.
TALL_PAGE = """<!doctype html>
<html><body style="margin: 0"><div style="height: {height}px; background: #36c"></div></body></html>"""


def tall_page(query: dict[str, list[str]]) -> tuple[str, bytes]:
    return "text/html; charset=utf-8", TALL_PAGE.format(height=float(query["height"][0])).encode()


@functools.cache
def tall_font() -> tuple[str, bytes]:
    """A font whose lines are 4 em high: 1 em of "x" boxes and 3 em above them."""
    units_per_em = 1000
    box = TTGlyphPen(None)
    box.moveTo((0, 0))
    box.lineTo((0, 500))
    box.lineTo((500, 500))
    box.lineTo((500, 0))
    box.closePath()
    glyphs = {".notdef": box.glyph(), "space": TTGlyphPen(None).glyph(), "x": box.glyph()}
    builder = FontBuilder(units_per_em, isTTF=True)
    builder.setupGlyphOrder(list(glyphs))
    builder.setupCharacterMap({ord(" "): "space", ord("x"): "x"})
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({name: (600, 0) for name in glyphs})
    builder.setupHorizontalHeader(ascent=4 * units_per_em, descent=0)
    builder.setupOS2(sTypoAscender=4 * units_per_em, sTypoDescender=0, usWinAscent=4 * units_per_em, usWinDescent=0)
    builder.setupNameTable({"familyName": "Tall", "styleName": "Regular"})
    builder.setupPost()
    font = io.BytesIO()
    builder.save(font)
    return "font/ttf", font.getvalue()


#: Path -> what to answer, made from the query string. Anything else comes from tests/pages/.
MADE_ON_REQUEST: dict[str, Callable[[dict[str, list[str]]], tuple[str, bytes]]] = {
    "/tall": tall_page,
    "/slow/tall-font.ttf": lambda query: tall_font(),
}


class _Handler(http.server.SimpleHTTPRequestHandler):
    server: "_Server"

    def do_GET(self) -> None:
        path, _, query = self.path.partition("?")
        if path == "/hang":
            # Never answer (until the server stops), so the page never finishes loading.
            self.server.stopping.wait()
            return
        if path not in MADE_ON_REQUEST:
            super().do_GET()
            return
        if path.startswith("/slow/"):
            time.sleep(SLOW_SECONDS)
        content_type, body = MADE_ON_REQUEST[path](urllib.parse.parse_qs(query))
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass  # keep the test output readable


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    stopping = threading.Event()


@pytest.fixture(scope="session")
def site() -> Iterator[str]:
    """The base URL of the test pages."""
    server = _Server(("127.0.0.1", PORT), functools.partial(_Handler, directory=str(PAGES)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{PORT}"
    finally:
        server.stopping.set()
        server.shutdown()
        server.server_close()
