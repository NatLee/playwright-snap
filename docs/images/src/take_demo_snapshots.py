"""Take the real snapshots shown in the README demo image, with playwright-snap itself.

    python docs/images/src/take_demo_snapshots.py

Needs playwright-snap with Chromium installed, and pdftoppm (poppler-utils) to turn
the PDF into an image. Writes to docs/images/src/out/ (not committed):

  desktop.png    get_image_snapshot_by_url() of demo-page.html
  phone.png      snap_png() of the same page as a phone (is_mobile, 2x pixels)
  page.pdf       get_pdf_snapshot_by_url() of the same page
  pdf-page.png   that PDF page as an image

demo.html then frames these files; render it as described at the top of that file.
"""
import base64
import functools
import http.server
import pathlib
import subprocess
import threading

from playsnap import SnapshotOptions, get_image_snapshot_by_url, get_pdf_snapshot_by_url, snap_png

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "out"
PHONE = SnapshotOptions(width=390, height=844, is_mobile=True, device_scale_factor=2)
#: Resolution of the PDF page image: enough for a thumbnail in demo.html.
PDF_IMAGE_DPI = 40


def serve(directory: pathlib.Path) -> http.server.ThreadingHTTPServer:
    """Serve ``directory`` on a free local port (the OS picks it)."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def decoded(base64_data: str | bytes | None) -> bytes:
    """The file a pyppeteer-snap style function returned; stop if it failed."""
    if base64_data is None:
        raise SystemExit("The snapshot failed, see the reason above.")
    return base64.b64decode(base64_data)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    server = serve(HERE)
    try:
        host, port = server.server_address[:2]
        url = f"http://{host}:{port}/demo-page.html"
        (OUT / "desktop.png").write_bytes(decoded(get_image_snapshot_by_url(url)))
        (OUT / "phone.png").write_bytes(snap_png(url, PHONE))
        (OUT / "page.pdf").write_bytes(decoded(get_pdf_snapshot_by_url(url)))
    finally:
        server.shutdown()
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(PDF_IMAGE_DPI), "-singlefile", str(OUT / "page.pdf"), str(OUT / "pdf-page")],
        check=True,
    )


if __name__ == "__main__":
    main()
