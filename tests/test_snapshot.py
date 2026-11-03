"""The functions for code that is not async, with a fake in place of Chromium.

What they must keep from pyppeteer-snap: the same arguments and return types, None
on failure, the caller's event loop left alone, and working inside a running loop.
"""
import asyncio
import base64
import inspect
import logging
import threading
from types import SimpleNamespace

import pytest

import playsnap
import playsnap.snapshot as snapshot
from playsnap import NavigationError, SnapshotOptions
from playsnap.session import capture_pdf, capture_png

URL = "https://example.com"


@pytest.fixture
def chromium(monkeypatch):
    """Replace "start Chromium, take one snapshot, close it" with a fake.

    It returns ``chromium.result``, or raises ``chromium.error`` when that is set,
    and records what it was called with in ``chromium.calls``.
    """
    state = SimpleNamespace(calls=[], result=b"\x89PNG fake", error=None)

    async def fake_take_snapshot(url, capture, options):
        state.calls.append(SimpleNamespace(url=url, capture=capture, options=options, thread=threading.current_thread()))
        if state.error is not None:
            raise state.error
        return state.result

    monkeypatch.setattr(snapshot, "take_snapshot", fake_take_snapshot)
    return state


def test_snap_png_and_snap_pdf_return_the_raw_file(chromium):
    assert playsnap.snap_png(URL) == b"\x89PNG fake"
    assert playsnap.snap_pdf(URL) == b"\x89PNG fake"

    assert [call.capture for call in chromium.calls] == [capture_png, capture_pdf]
    assert all(call.options == SnapshotOptions() for call in chromium.calls)


def test_snap_png_passes_the_options_on(chromium):
    options = SnapshotOptions(width=390, height=844, is_mobile=True, wait_until="networkidle")

    playsnap.snap_png(URL, options)

    assert chromium.calls[0].options is options


def test_snap_png_raises_the_snapshot_error(chromium):
    chromium.error = NavigationError("net::ERR_NAME_NOT_RESOLVED", URL)

    with pytest.raises(NavigationError):
        playsnap.snap_png(URL)


def test_the_compatible_functions_have_pyppeteer_snaps_signature():
    # pyppeteer-snap 1.1.0: (url, width=1600, height=900, is_mobile=False) for both.
    for function in (playsnap.get_image_snapshot_by_url, playsnap.get_pdf_snapshot_by_url):
        parameters = inspect.signature(function).parameters
        assert [(p.name, p.default) for p in parameters.values()] == [
            ("url", inspect.Parameter.empty),
            ("width", 1600),
            ("height", 900),
            ("is_mobile", False),
        ]


def test_image_snapshot_is_base64_text(chromium):
    png = playsnap.get_image_snapshot_by_url(URL, width=390, height=844, is_mobile=True)

    assert png == base64.b64encode(b"\x89PNG fake").decode("ascii")
    assert isinstance(png, str)
    assert chromium.calls[0].capture is capture_png
    assert chromium.calls[0].options == SnapshotOptions(width=390, height=844, is_mobile=True)


def test_pdf_snapshot_is_base64_bytes(chromium):
    chromium.result = b"%PDF-1.4 fake"

    pdf = playsnap.get_pdf_snapshot_by_url(URL)

    assert pdf == base64.b64encode(b"%PDF-1.4 fake")
    assert chromium.calls[0].capture is capture_pdf
    assert chromium.calls[0].options == SnapshotOptions()


@pytest.mark.parametrize("function", ["get_image_snapshot_by_url", "get_pdf_snapshot_by_url"])
def test_failed_snapshot_logs_the_reason_and_returns_none(chromium, caplog, capsys, function):
    chromium.error = NavigationError("Page.goto: net::ERR_NAME_NOT_RESOLVED", "https://no-such-host.invalid")

    with caplog.at_level(logging.ERROR, logger="playsnap"):
        assert getattr(playsnap, function)("https://no-such-host.invalid") is None

    assert [(r.name, r.levelno, r.getMessage()) for r in caplog.records] == [
        ("playsnap", logging.ERROR, "Could not take a snapshot of https://no-such-host.invalid: Page.goto: net::ERR_NAME_NOT_RESOLVED"),
    ]
    # Nothing on stdout, where it could end up in data the caller pipes somewhere.
    assert capsys.readouterr().out == ""


def test_bad_arguments_are_raised_not_hidden(chromium):
    with pytest.raises(ValueError, match="width must be greater than 0"):
        playsnap.get_image_snapshot_by_url(URL, width=0)
    assert chromium.calls == []


def test_the_snapshot_runs_in_a_worker_thread(chromium):
    playsnap.snap_png(URL)

    assert chromium.calls[0].thread is not threading.current_thread()
    assert chromium.calls[0].thread.name.startswith("playwright-snap")


def test_the_callers_event_loop_is_left_alone(chromium):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        playsnap.get_image_snapshot_by_url(URL)

        assert asyncio.get_event_loop() is loop
        assert not loop.is_closed()
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def test_works_where_an_event_loop_is_already_running(chromium):
    # e.g. a Jupyter notebook or an async web framework, where asyncio.run() refuses.
    async def caller():
        return playsnap.get_image_snapshot_by_url(URL)

    assert asyncio.run(caller()) == base64.b64encode(b"\x89PNG fake").decode("ascii")
