"""The command prints pyppeteer-snap's output and reports failures by exit status.

The snapshot functions are replaced by fakes here; tests/test_browser.py runs the
real command.
"""
import subprocess
import sys

import pytest

import playwright_snap.cli as cli
from playwright_snap import NavigationError


def fake_snapshot(monkeypatch, type_, take):
    """Make `--type type_` call ``take(url, options)`` instead of starting Chromium."""
    prints, _ = cli.SNAPSHOTS[type_]
    monkeypatch.setitem(cli.SNAPSHOTS, type_, (prints, take))


def run(capsys, *args):
    status = cli.main(list(args))
    out, err = capsys.readouterr()
    return status, out.splitlines(), err


def test_image_is_printed_as_plain_base64_on_line_5(monkeypatch, capsys):
    fake_snapshot(monkeypatch, "img", lambda url, options: b"\x89PNG\r\n\x1a\n")

    status, lines, err = run(capsys, "--url", "https://example.com", "--type", "img")

    assert status == 0
    assert lines == [
        "------------- Parameters ---------------",
        "URL: https://example.com",
        "Type: img",
        "--------------- Base64 ------------------",
        "iVBORw0KGgo=",
        "-------------------------------------",
    ]
    assert err == ""


def test_pdf_is_printed_as_plain_base64(monkeypatch, capsys):
    fake_snapshot(monkeypatch, "pdf", lambda url, options: b"%PDF-1.4\n")

    status, lines, _ = run(capsys, "--url", "https://example.com", "--type", "pdf")

    assert status == 0
    assert lines[4] == "JVBERi0xLjQK"


def test_type_defaults_to_img_and_ignores_case(monkeypatch, capsys):
    fake_snapshot(monkeypatch, "img", lambda url, options: b"png")
    fake_snapshot(monkeypatch, "pdf", lambda url, options: b"pdf")

    assert run(capsys, "--url", "https://example.com")[1][2:5] == ["Type: img", "--------------- Base64 ------------------", "cG5n"]
    assert run(capsys, "--url", "https://example.com", "--type", "PDF")[1][2:5] == ["Type: pdf", "--------------- Base64 ------------------", "cGRm"]


def test_the_snapshot_uses_the_default_options(monkeypatch, capsys):
    seen = []
    fake_snapshot(monkeypatch, "img", lambda url, options: seen.append((url, options)) or b"png")

    run(capsys, "--url", "https://example.com")

    assert seen == [("https://example.com", cli.DEFAULT_OPTIONS)]


def test_failed_snapshot_exits_with_1_and_says_why_on_stderr(monkeypatch, capsys):
    def fail(url, options):
        raise NavigationError("Page.goto: net::ERR_NAME_NOT_RESOLVED at https://no-such-host.invalid/", url)

    fake_snapshot(monkeypatch, "img", fail)

    status, lines, err = run(capsys, "--url", "https://no-such-host.invalid")

    assert status == 1
    assert lines == ["------------- Parameters ---------------", "URL: https://no-such-host.invalid", "Type: img"]
    assert err == (
        "playwright-snap: error: Could not take a snapshot of https://no-such-host.invalid: "
        "Page.goto: net::ERR_NAME_NOT_RESOLVED at https://no-such-host.invalid/\n"
    )


def test_missing_url_exits_with_2(capsys):
    with pytest.raises(SystemExit) as exit_:
        cli.main([])

    assert exit_.value.code == 2
    assert "the following arguments are required: --url" in capsys.readouterr().err


def test_unknown_type_exits_with_2(capsys):
    with pytest.raises(SystemExit) as exit_:
        cli.main(["--url", "https://example.com", "--type", "jpg"])

    assert exit_.value.code == 2
    assert "invalid choice: 'jpg' (choose from" in capsys.readouterr().err


def test_help_names_the_default_window_size():
    help_text = " ".join(cli.get_parser().format_help().split())

    # 1600 x 900 is SnapshotOptions' default window.
    assert "img: PNG of the first 1600x900 pixels (default); pdf: the whole page as a PDF" in help_text


def test_python_dash_m_runs_the_command():
    result = subprocess.run([sys.executable, "-m", "playwright_snap", "--help"], capture_output=True, text=True)

    assert result.returncode == 0
    assert result.stdout.startswith("usage: playwright-snap ")
