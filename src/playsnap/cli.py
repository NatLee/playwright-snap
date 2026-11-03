"""The ``playwright-snap`` command: print a snapshot of a web page as base64 text.

The options and the output are the same as pyppeteer-snap's ``pyppesnap`` command,
so scripts that read the base64 text from line 5 keep working.
"""
import argparse
import base64
import sys
from collections.abc import Callable, Sequence

from .errors import SnapshotError
from .options import DEFAULT_OPTIONS, SnapshotOptions
from .snapshot import snap_pdf, snap_png

PROG = "playwright-snap"

#: --type value -> (what it prints, the function that takes it). The first one is the default.
SNAPSHOTS: dict[str, tuple[str, Callable[[str, SnapshotOptions], bytes]]] = {
    "img": (f"PNG of the first {DEFAULT_OPTIONS.width}x{DEFAULT_OPTIONS.height} pixels", snap_png),
    "pdf": ("the whole page as a PDF", snap_pdf),
}
DEFAULT_TYPE = next(iter(SNAPSHOTS))

#: The lines around the parameters and the base64 text (pyppeteer-snap's output).
PARAMETERS_RULE = "------------- Parameters ---------------"
BASE64_RULE = "--------------- Base64 ------------------"
END_RULE = "-------------------------------------"


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Print a snapshot of a web page as base64 text, taken with a headless Chromium.",
        epilog="Exit status: 0 when it worked, 1 when the snapshot failed, 2 for wrong options.",
    )
    parser.add_argument("--url", required=True, help="the page to snapshot, with its scheme, e.g. https://example.com")
    parser.add_argument(
        "--type",
        type=str.lower,
        choices=SNAPSHOTS,
        default=DEFAULT_TYPE,
        help="; ".join(
            f"{name}: {prints}{' (default)' if name == DEFAULT_TYPE else ''}" for name, (prints, _) in SNAPSHOTS.items()
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return its exit status: 0 success, 1 snapshot failed.

    Wrong options exit with status 2, like every argparse program.
    """
    args = get_parser().parse_args(argv)
    print(PARAMETERS_RULE)
    print(f"URL: {args.url}")
    print(f"Type: {args.type}")
    try:
        data = SNAPSHOTS[args.type][1](args.url, DEFAULT_OPTIONS)
    except SnapshotError as error:
        print(f"{PROG}: error: {error}", file=sys.stderr)
        return 1
    print(BASE64_RULE)
    print(base64.b64encode(data).decode("ascii"))
    print(END_RULE)
    return 0
