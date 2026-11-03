"""Everything you can tune about a snapshot, with the defaults in one place."""
from dataclasses import dataclass, fields
from typing import Literal, get_args

#: When the page counts as loaded, passed to Playwright's ``page.goto(wait_until=...)``:
#: ``"load"`` waits for the load event (HTML, images and stylesheets),
#: ``"domcontentloaded"`` only for the HTML, ``"networkidle"`` until there has been
#: no network traffic for 500 ms, and ``"commit"`` only for the first bytes of the response.
WaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]
WAIT_UNTIL_CHOICES: tuple[str, ...] = get_args(WaitUntil)


@dataclass(frozen=True)
class SnapshotOptions:
    """How to take a snapshot. Sizes are in CSS pixels, times in seconds.

    Every number must be greater than 0. The defaults are the ones pyppeteer-snap uses.
    """

    width: int = 1600
    """Width of the browser window. The PNG is this wide, and so is the PDF page."""

    height: int = 900
    """Height of the browser window. The PNG is this high; the PDF is as high as the whole page."""

    is_mobile: bool = False
    """Lay the page out like a phone browser does: honour its ``<meta name="viewport">`` tag.
    Pair it with a phone-sized window, e.g. ``width=390, height=844``."""

    device_scale_factor: float = 1
    """Image pixels per CSS pixel. 2 gives a PNG twice as wide and high, as on a retina screen."""

    wait_until: WaitUntil = "load"
    """When the page counts as loaded, see :data:`WaitUntil`."""

    navigation_timeout: float = 30
    """How long the page may take to load."""

    snapshot_timeout: float = 120
    """How long one whole snapshot may take: start Chromium (unless a :class:`SnapSession`
    already runs it), load the page and capture it."""

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
            if is_number and not value > 0:
                raise ValueError(f"{field.name} must be greater than 0, got {value!r}")
        if self.wait_until not in WAIT_UNTIL_CHOICES:
            raise ValueError(
                f"wait_until must be one of {', '.join(map(repr, WAIT_UNTIL_CHOICES))}, got {self.wait_until!r}"
            )


#: The options used when none are given.
DEFAULT_OPTIONS = SnapshotOptions()
