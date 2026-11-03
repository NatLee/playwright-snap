"""The errors say in one line what failed and, for known causes, what to do about it."""
import asyncio

import pytest
from playwright.async_api import Error as PlaywrightError

from playsnap import BrowserLaunchError, NavigationError, SnapSession, SnapshotError, SnapshotTimeoutError
from playsnap.errors import INSTALL_HELP
from playsnap.session import _failures_as

URL = "https://example.com"


def test_message_names_the_url_and_the_reason():
    error = SnapshotError("net::ERR_CONNECTION_REFUSED at http://localhost:1/", "http://localhost:1")

    assert str(error) == "Could not take a snapshot of http://localhost:1: net::ERR_CONNECTION_REFUSED at http://localhost:1/"
    assert error.reason == "net::ERR_CONNECTION_REFUSED at http://localhost:1/"
    assert error.url == "http://localhost:1"


def test_every_error_is_a_snapshot_error():
    for error_type in (BrowserLaunchError, NavigationError, SnapshotTimeoutError):
        assert issubclass(error_type, SnapshotError)


def test_chromium_that_does_not_start_gets_the_install_command():
    error = BrowserLaunchError("BrowserType.launch: Executable doesn't exist at /x/chrome")

    assert str(error) == (
        "Could not take a snapshot: BrowserType.launch: Executable doesn't exist at /x/chrome (install Chromium "
        "with `python -m playwright install chromium`; on Linux add --with-deps for the system libraries it "
        f"needs, see {INSTALL_HELP})"
    )


def test_url_without_scheme_gets_a_hint():
    error = NavigationError("Page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL", "example.com")

    assert str(error).endswith("Cannot navigate to invalid URL (the URL needs a scheme, e.g. https://example.com)")


def test_url_with_scheme_gets_no_hint():
    error = NavigationError("Page.goto: net::ERR_NAME_NOT_RESOLVED at https://no-such-host.invalid/", URL)

    assert str(error) == f"Could not take a snapshot of {URL}: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://no-such-host.invalid/"


def test_playwright_errors_become_the_given_error_with_the_first_line_as_reason():
    playwright_error = PlaywrightError('Page.goto: Timeout 1000ms exceeded.\nCall log:\n  - navigating to "https://example.com/"')

    with pytest.raises(NavigationError) as caught:
        with _failures_as(NavigationError, URL):
            raise playwright_error

    assert caught.value.reason == "Page.goto: Timeout 1000ms exceeded."
    assert caught.value.url == URL
    # The whole Playwright error, call log included, is still there.
    assert caught.value.__cause__ is playwright_error


def test_a_playwright_error_without_a_message_is_named_by_its_type():
    with pytest.raises(SnapshotError, match=r"^Could not take a snapshot of https://example.com: Error$"):
        with _failures_as(SnapshotError, URL):
            raise PlaywrightError("")


def test_other_errors_are_left_alone():
    # Programming errors must not look like a page that failed to load.
    with pytest.raises(KeyError):
        with _failures_as(SnapshotError, URL):
            raise KeyError("width")


def test_a_session_used_outside_async_with_says_how_to_use_it():
    with pytest.raises(RuntimeError, match="async with SnapSession"):
        asyncio.run(SnapSession().png(URL))
