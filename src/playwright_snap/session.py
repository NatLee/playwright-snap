"""The browser session: start Chromium, take snapshots, close Chromium again.

Everything that talks to Playwright lives here, and only uses its public async API.
The functions in :mod:`playwright_snap.snapshot` and the command line tool are thin
wrappers around :func:`take_snapshot`.
"""
import asyncio
from collections.abc import Awaitable, Callable, Iterator
from contextlib import AsyncExitStack, contextmanager
from types import TracebackType
from typing import TypeVar

from playwright.async_api import Browser, Page, async_playwright
from playwright.async_api import Error as PlaywrightError

from .errors import BrowserLaunchError, NavigationError, SnapshotError, SnapshotTimeoutError
from .options import DEFAULT_OPTIONS, SnapshotOptions

T = TypeVar("T")

#: Captures a loaded page as file content, e.g. :func:`capture_png`.
Capture = Callable[[Page], Awaitable[bytes]]

#: The size of the laid-out page, for the single-sheet PDF. Its height is the
#: document with its margins, or what sticks out of the body (absolutely positioned
#: boxes), whichever is lower. It can have a fraction (5000.3 px); rounding that
#: down would push the last bit onto a second sheet.
_MEASURE_PAGE = """async () => {
    // Web fonts change the layout, and the load event does not wait for them. Laying
    // the page out starts loading the ones it uses; then wait until they are in.
    document.documentElement.getBoundingClientRect();
    await document.fonts.ready;
    return {
        width: document.scrollingElement.scrollWidth,
        height: Math.ceil(Math.max(
            document.documentElement.getBoundingClientRect().height,
            document.body ? document.body.scrollHeight : 0,
        )),
    };
}"""


async def capture_png(page: Page) -> bytes:
    """What fits in the browser window, as a PNG."""
    return await page.screenshot(type="png")


async def capture_pdf(page: Page) -> bytes:
    """The whole page as a PDF on a single sheet, as wide as the browser window."""
    # page.pdf() lays the page out with its print styles. Measure it with the same
    # styles, or a page whose print layout is taller spills onto more sheets.
    await page.emulate_media(media="print")
    size = await page.evaluate(_MEASURE_PAGE)
    return await page.pdf(width=f"{size['width']}px", height=f"{size['height']}px", print_background=True)


@contextmanager
def _failures_as(error_type: type[SnapshotError], url: str | None) -> Iterator[None]:
    """Turn a Playwright error raised in the block into ``error_type``."""
    try:
        yield
    except PlaywrightError as error:
        lines = [line.strip() for line in error.message.splitlines() if line.strip()]
        raise error_type(lines[0] if lines else type(error).__name__, url) from error


async def _within(seconds: float, url: str, work: Awaitable[T]) -> T:
    """Return what ``work`` returns, or raise SnapshotTimeoutError after ``seconds``."""
    try:
        return await asyncio.wait_for(work, seconds)
    except asyncio.TimeoutError:
        raise SnapshotTimeoutError(f"gave up after {seconds:g} s", url) from None


class SnapSession:
    """One headless Chromium for several snapshots::

        async with SnapSession() as session:
            png = await session.png("https://example.com")
            pdf = await session.pdf("https://example.com", SnapshotOptions(width=800))

    Each snapshot opens the page in a fresh browser context, so cookies and storage
    from one page never reach the next. Chromium closes when the ``async with`` block
    ends, also when it ends with an error. When Chromium does not start, ``async with``
    raises BrowserLaunchError.
    """

    def __init__(self) -> None:
        self._browser: Browser | None = None
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> "SnapSession":
        async with AsyncExitStack() as stack:
            with _failures_as(BrowserLaunchError, None):
                playwright = await stack.enter_async_context(async_playwright())
                browser = await playwright.chromium.launch()
            stack.push_async_callback(browser.close)
            # Started: from now on __aexit__ closes Chromium and Playwright.
            self._browser, self._stack = browser, stack.pop_all()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._browser = None
        await self._stack.aclose()

    async def png(self, url: str, options: SnapshotOptions | None = None) -> bytes:
        """Load ``url`` and return a PNG of what fits in the browser window.

        Raises NavigationError when the page does not load, SnapshotTimeoutError after
        ``snapshot_timeout`` and SnapshotError for anything else.
        """
        return await self._snapshot(url, capture_png, options or DEFAULT_OPTIONS)

    async def pdf(self, url: str, options: SnapshotOptions | None = None) -> bytes:
        """Load ``url`` and return the whole page as a single-page PDF. Raises like :meth:`png`."""
        return await self._snapshot(url, capture_pdf, options or DEFAULT_OPTIONS)

    async def _snapshot(self, url: str, capture: Capture, options: SnapshotOptions) -> bytes:
        return await _within(options.snapshot_timeout, url, self._take(url, capture, options))

    async def _take(self, url: str, capture: Capture, options: SnapshotOptions) -> bytes:
        """Load ``url`` in a fresh context and return ``capture(page)``, without a time limit."""
        if self._browser is None:
            raise RuntimeError("SnapSession takes snapshots only inside `async with SnapSession() as session:`")
        with _failures_as(SnapshotError, url):
            context = await self._browser.new_context(
                viewport={"width": options.width, "height": options.height},
                device_scale_factor=options.device_scale_factor,
                is_mobile=options.is_mobile,
            )
            try:
                page = await context.new_page()
                with _failures_as(NavigationError, url):
                    await page.goto(url, wait_until=options.wait_until, timeout=options.navigation_timeout * 1000)
                return await capture(page)
            finally:
                await context.close()


async def take_snapshot(url: str, capture: Capture, options: SnapshotOptions) -> bytes:
    """Start Chromium, return ``capture(page)`` for ``url`` and close Chromium.

    All of it has to finish within ``options.snapshot_timeout``.
    """

    async def start_take_close() -> bytes:
        async with SnapSession() as session:
            return await session._take(url, capture, options)

    return await _within(options.snapshot_timeout, url, start_take_close())
