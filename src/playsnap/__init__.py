"""playwright-snap: snapshots of web pages as PNG or PDF, taken with Playwright's headless Chromium."""
__version__ = "0.1.0"

from .cli import main
from .errors import BrowserLaunchError, NavigationError, SnapshotError, SnapshotTimeoutError
from .options import SnapshotOptions, WaitUntil
from .session import SnapSession
from .snapshot import get_image_snapshot_by_url, get_pdf_snapshot_by_url, snap_pdf, snap_png

__all__ = [
    "BrowserLaunchError",
    "NavigationError",
    "SnapSession",
    "SnapshotError",
    "SnapshotOptions",
    "SnapshotTimeoutError",
    "WaitUntil",
    "get_image_snapshot_by_url",
    "get_pdf_snapshot_by_url",
    "main",
    "snap_pdf",
    "snap_png",
]
