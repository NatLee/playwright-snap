"""SnapshotOptions: the defaults, and the checks that catch bad values before Chromium starts."""
import dataclasses
import typing

import pytest
from playwright.async_api import Page

from playsnap import SnapshotOptions
from playsnap.options import WAIT_UNTIL_CHOICES

NUMBERS = ["width", "height", "device_scale_factor", "navigation_timeout", "snapshot_timeout"]


def test_the_defaults_are_pyppeteer_snaps():
    # pyppeteer-snap 1.1.0: a 1600 x 900 window at 1 image pixel per CSS pixel, not
    # mobile, the load event, 30 s for the page to load and 120 s for a whole snapshot.
    assert dataclasses.asdict(SnapshotOptions()) == {
        "width": 1600,
        "height": 900,
        "is_mobile": False,
        "device_scale_factor": 1,
        "wait_until": "load",
        "navigation_timeout": 30,
        "snapshot_timeout": 120,
    }


def test_options_cannot_be_changed_after_creation():
    options = SnapshotOptions()

    with pytest.raises(dataclasses.FrozenInstanceError):
        options.width = 800  # type: ignore[misc]


@pytest.mark.parametrize("name", NUMBERS)
@pytest.mark.parametrize("value", [0, -1])
def test_numbers_must_be_greater_than_zero(name, value):
    with pytest.raises(ValueError, match=f"^{name} must be greater than 0, got {value}$"):
        SnapshotOptions(**{name: value})


def test_every_number_is_checked():
    # The check finds the numbers by their value, so a new number option is covered too.
    numbers = [f.name for f in dataclasses.fields(SnapshotOptions) if f.type in (int, float)]

    assert sorted(numbers) == sorted(NUMBERS)


def test_wait_until_must_be_one_playwright_knows():
    with pytest.raises(ValueError, match="^wait_until must be one of 'commit', 'domcontentloaded', 'load', 'networkidle', got 'idle'$"):
        SnapshotOptions(wait_until="idle")  # type: ignore[arg-type]


def test_wait_until_choices_are_playwrights():
    # Read from Playwright's own type hints for page.goto(wait_until=...).
    hint = typing.get_type_hints(Page.goto)["wait_until"]
    literal = next(arg for arg in typing.get_args(hint) if typing.get_origin(arg) is typing.Literal)

    assert sorted(WAIT_UNTIL_CHOICES) == sorted(typing.get_args(literal))
