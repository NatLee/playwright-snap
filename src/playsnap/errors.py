"""What can go wrong, by the step that failed. ``str(error)`` says why in one line."""

#: The README section that explains how to install Chromium.
INSTALL_HELP = "https://github.com/NatLee/playwright-snap#installation"


class SnapshotError(Exception):
    """No snapshot was taken. The subclasses say which step failed.

    ``reason`` is the cause in one line, usually the first line of Playwright's
    message; the full Playwright error is chained as ``__cause__``. ``url`` is the
    page, or None when the failure is not about a page (Chromium did not start).
    """

    def __init__(self, reason: str, url: str | None = None) -> None:
        self.reason = reason
        self.url = url
        message = "Could not take a snapshot" + (f" of {url}" if url is not None else "") + f": {reason}"
        hint = self.hint()
        super().__init__(f"{message} ({hint})" if hint else message)

    def hint(self) -> str | None:
        """What to do about it, when the cause is a known one."""
        return None


class BrowserLaunchError(SnapshotError):
    """Chromium did not start: it is not installed, or (on Linux) system libraries are missing."""

    def hint(self) -> str:
        return (
            "install Chromium with `python -m playwright install chromium`; on Linux add --with-deps "
            f"for the system libraries it needs, see {INSTALL_HELP}"
        )


class NavigationError(SnapshotError):
    """The page did not load: bad URL, unreachable host, or ``navigation_timeout`` ran out."""

    def hint(self) -> str | None:
        if self.url is not None and "://" not in self.url:
            return f"the URL needs a scheme, e.g. https://{self.url}"
        return None


class SnapshotTimeoutError(SnapshotError):
    """The whole snapshot took longer than ``snapshot_timeout``."""
