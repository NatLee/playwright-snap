"""Snapshot functions for code that is not async.

``snap_png()`` and ``snap_pdf()`` return the file content and raise SnapshotError.
``get_image_snapshot_by_url()`` and ``get_pdf_snapshot_by_url()`` are pyppeteer-snap's
functions with the same arguments and return values (base64, None on failure), so
code written for pyppeteer-snap only has to change its import. They stay for as
long as people move over from pyppeteer-snap; new code can use either pair.
"""
import asyncio
import base64
import logging
from collections.abc import Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

from .errors import SnapshotError
from .options import DEFAULT_OPTIONS, SnapshotOptions
from .session import Capture, capture_pdf, capture_png, take_snapshot

T = TypeVar("T")

logger = logging.getLogger(__package__)


def run_sync(work: Coroutine[Any, Any, T]) -> T:
    """Run ``work`` on a new event loop in a worker thread and return its result.

    The worker thread leaves the caller's event loop alone, and makes the functions
    work where a loop is already running (Jupyter, async web apps), where
    ``asyncio.run()`` refuses to start.
    """
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright-snap") as worker:
        return worker.submit(asyncio.run, work).result()


def _snap(url: str, capture: Capture, options: SnapshotOptions | None) -> bytes:
    return run_sync(take_snapshot(url, capture, options or DEFAULT_OPTIONS))


def snap_png(url: str, options: SnapshotOptions | None = None) -> bytes:
    """Return a PNG of what fits in the browser window of ``url``.

    Starts its own Chromium and closes it again. Raises NavigationError when the
    page does not load, BrowserLaunchError when Chromium does not start,
    SnapshotTimeoutError after ``snapshot_timeout`` and SnapshotError otherwise.
    """
    return _snap(url, capture_png, options)


def snap_pdf(url: str, options: SnapshotOptions | None = None) -> bytes:
    """Return the whole page at ``url`` as a single-page PDF. Raises like :func:`snap_png`."""
    return _snap(url, capture_pdf, options)


def _or_none(take: Callable[[str, SnapshotOptions], bytes], url: str, options: SnapshotOptions) -> bytes | None:
    """``take(url, options)``, or None after logging why it failed (pyppeteer-snap printed it)."""
    try:
        return take(url, options)
    except SnapshotError as error:
        logger.error("%s", error)
        return None


def get_image_snapshot_by_url(
    url: str,
    width: int = DEFAULT_OPTIONS.width,
    height: int = DEFAULT_OPTIONS.height,
    is_mobile: bool = DEFAULT_OPTIONS.is_mobile,
) -> str | None:
    """Return a PNG of the page's first ``width`` x ``height`` pixels as base64 text.

    On failure, log the reason (logger ``playwright_snap``) and return None.
    """
    png = _or_none(snap_png, url, SnapshotOptions(width=width, height=height, is_mobile=is_mobile))
    return None if png is None else base64.b64encode(png).decode("ascii")


def get_pdf_snapshot_by_url(
    url: str,
    width: int = DEFAULT_OPTIONS.width,
    height: int = DEFAULT_OPTIONS.height,
    is_mobile: bool = DEFAULT_OPTIONS.is_mobile,
) -> bytes | None:
    """Return the whole page as a single-page PDF, base64-encoded bytes.

    ``width`` and ``height`` set the browser window the page is laid out in.
    On failure, log the reason (logger ``playwright_snap``) and return None.
    """
    pdf = _or_none(snap_pdf, url, SnapshotOptions(width=width, height=height, is_mobile=is_mobile))
    return None if pdf is None else base64.b64encode(pdf)
