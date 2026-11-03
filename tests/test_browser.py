"""Real snapshots with a real headless Chromium, of the local test pages (see conftest.py).

Needs `python -m playwright install chromium`. Leave these out with `pytest -m "not browser"`.
"""
import asyncio
import base64
import io
import math
import pathlib
import socket
import time

import pytest
from PIL import Image
from pypdf import PdfReader

from playwright_snap import (
    BrowserLaunchError,
    NavigationError,
    SnapSession,
    SnapshotOptions,
    SnapshotTimeoutError,
    get_image_snapshot_by_url,
    get_pdf_snapshot_by_url,
    snap_pdf,
    snap_png,
)

pytestmark = pytest.mark.browser

SMALL = SnapshotOptions(width=800, height=600)


def png_image(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    assert image.format == "PNG"
    return image.convert("RGB")


def pdf_pages(data: bytes) -> list[tuple[float, float]]:
    """(width, height) of every page, in CSS pixels."""
    # PDF sizes are in points: 72 to the inch, where CSS has 96 pixels.
    return [(float(p.mediabox.width) * 96 / 72, float(p.mediabox.height) * 96 / 72) for p in PdfReader(io.BytesIO(data)).pages]


def red_run(image: Image.Image, y: int = 10) -> int:
    """How many pixels of row ``y`` are red."""
    return sum(1 for x in range(image.width) if image.getpixel((x, y)) == (255, 0, 0))


def closed_port() -> int:
    """A local port nothing listens on."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]



# --- PNG -------------------------------------------------------------------


def test_png_is_what_fits_in_the_browser_window(site):
    image = png_image(snap_png(f"{site}/tall?height=3000", SMALL))

    assert image.size == (800, 600)
    assert image.getpixel((400, 300)) == (51, 102, 204)  # the page's #36c


def test_device_scale_factor_multiplies_the_png_size(site):
    image = png_image(snap_png(f"{site}/tall?height=3000", SnapshotOptions(width=400, height=300, device_scale_factor=2)))

    assert image.size == (800, 600)


def test_is_mobile_lays_the_page_out_like_a_phone(site):
    url = f"{site}/no-viewport-tag.html"
    phone_window = {"width": 390, "height": 844}

    desktop = png_image(snap_png(url, SnapshotOptions(**phone_window)))
    phone = png_image(snap_png(url, SnapshotOptions(**phone_window, is_mobile=True)))

    # The page has a 390 px wide red box. In a 390 px desktop window it fills the row.
    assert red_run(desktop) == 390
    # A phone lays a page without a viewport tag out 980 px wide and zooms out to fit:
    # 390 * 390 / 980 = 155 px.
    assert 150 <= red_run(phone) <= 160


# --- PDF -------------------------------------------------------------------


@pytest.mark.parametrize("height", [300, 1000, 1234.4, 5000.3])
def test_pdf_is_the_whole_page_on_one_sheet(site, height):
    # 5000.3 px used to need a second sheet when the height was rounded down.
    pages = pdf_pages(snap_pdf(f"{site}/tall?height={height}", SMALL))

    assert len(pages) == 1
    assert pages[0][0] == pytest.approx(800, abs=1)
    assert pages[0][1] == pytest.approx(math.ceil(height), abs=2)


def test_pdf_is_measured_with_the_print_styles(site):
    # 500 px high on screen and 3000 px in print. Measured on screen, the PDF ran
    # over several sheets.
    pages = pdf_pages(snap_pdf(f"{site}/print-taller.html", SMALL))

    assert len(pages) == 1
    assert pages[0][1] == pytest.approx(3000, abs=2)


def test_pdf_waits_for_web_fonts_before_measuring(site):
    # The font arrives after the load event and makes every line 4 times as high:
    # 20 lines x 4 x 20 px = 1600 px. Measured before it arrived, the PDF ran over
    # several sheets.
    pages = pdf_pages(snap_pdf(f"{site}/late-font.html", SMALL))

    assert len(pages) == 1
    assert pages[0][1] == pytest.approx(1600, abs=2)


def test_pdf_includes_what_sticks_out_of_the_body(site):
    # The body is 500 px high; a box positioned below it reaches down to 640 px.
    pages = pdf_pages(snap_pdf(f"{site}/sticks-out.html", SMALL))

    assert len(pages) == 1
    assert pages[0][1] == pytest.approx(640, abs=2)


# --- pyppeteer-snap's functions --------------------------------------------


def test_image_snapshot_is_a_base64_png_of_the_default_window(site):
    png = get_image_snapshot_by_url(f"{site}/tall?height=2000")

    assert isinstance(png, str)
    assert png_image(base64.b64decode(png)).size == (1600, 900)


def test_pdf_snapshot_is_base64_bytes_of_a_one_page_pdf(site):
    pdf = get_pdf_snapshot_by_url(f"{site}/tall?height=2000")

    assert isinstance(pdf, bytes)
    assert base64.b64decode(pdf).startswith(b"%PDF-")
    assert len(pdf_pages(base64.b64decode(pdf))) == 1


def test_failed_snapshot_returns_none_and_logs_why(caplog):
    url = f"http://127.0.0.1:{closed_port()}/"

    assert get_image_snapshot_by_url(url) is None
    assert f"Could not take a snapshot of {url}: " in caplog.text
    assert "net::ERR_CONNECTION_REFUSED" in caplog.text


def test_works_inside_a_running_event_loop(site):
    async def from_async_code():
        return get_image_snapshot_by_url(f"{site}/tall?height=100", width=200, height=100)

    assert png_image(base64.b64decode(asyncio.run(from_async_code()))).size == (200, 100)


# --- SnapSession -----------------------------------------------------------


def test_a_session_takes_several_snapshots_each_in_a_fresh_context(site):
    async def snapshots():
        async with SnapSession() as session:
            first = await session.png(f"{site}/fresh-context.html", SMALL)
            pdf = await session.pdf(f"{site}/tall?height=1500", SMALL)
            second = await session.png(f"{site}/fresh-context.html", SnapshotOptions(width=200, height=100))
        return first, pdf, second

    first, pdf, second = asyncio.run(snapshots())

    # The page turns red when a cookie from an earlier visit is still there.
    assert png_image(first).getpixel((5, 5)) == (0, 255, 0)
    assert png_image(second).getpixel((5, 5)) == (0, 255, 0)
    assert png_image(second).size == (200, 100)
    assert len(pdf_pages(pdf)) == 1


# --- failures --------------------------------------------------------------


def test_url_without_scheme_is_a_navigation_error_with_a_hint():
    with pytest.raises(NavigationError) as caught:
        snap_png("example.com", SMALL)

    assert "Cannot navigate to invalid URL" in str(caught.value)
    assert str(caught.value).endswith("(the URL needs a scheme, e.g. https://example.com)")


def test_page_that_never_loads_hits_the_navigation_timeout(site):
    with pytest.raises(NavigationError, match="Timeout 1000ms exceeded"):
        snap_png(f"{site}/never-loads.html", SnapshotOptions(navigation_timeout=1))


def _playwright_processes() -> set[int]:
    """PIDs of running Chromium and Playwright processes (Linux: read from /proc)."""
    found = set()
    for entry in pathlib.Path("/proc").iterdir():
        try:
            if not entry.name.isdigit() or (entry / "stat").read_text().rsplit(")", 1)[1].split()[0] == "Z":
                continue
            command = (entry / "cmdline").read_bytes().lower()
        except OSError:
            continue  # the process ended meanwhile
        if b"chrom" in command or b"playwright" in command:
            found.add(int(entry.name))
    return found


@pytest.mark.skipif(not pathlib.Path("/proc/self/stat").exists(), reason="lists processes through /proc (Linux)")
def test_snapshot_timeout_gives_up_and_closes_chromium(site):
    url = f"{site}/never-loads.html"
    before = _playwright_processes()
    started = time.monotonic()

    with pytest.raises(SnapshotTimeoutError) as caught:
        snap_png(url, SnapshotOptions(snapshot_timeout=3))

    assert time.monotonic() - started < 15
    assert str(caught.value) == f"Could not take a snapshot of {url}: gave up after 3 s"
    deadline = time.monotonic() + 10
    while _playwright_processes() - before and time.monotonic() < deadline:
        time.sleep(0.2)
    assert _playwright_processes() - before == set()


def test_chromium_that_is_not_installed_gets_the_install_command(monkeypatch, tmp_path, site):
    # PLAYWRIGHT_BROWSERS_PATH is where Playwright looks for its browsers. Empty means none installed.
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))

    with pytest.raises(BrowserLaunchError) as caught:
        snap_png(f"{site}/tall?height=100")

    assert "python -m playwright install chromium" in str(caught.value)

