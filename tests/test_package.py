"""What the installed package and its PyPI page need."""
import importlib.metadata
import importlib.resources
import pathlib
import re

import playwright_snap

README = (pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")


def test_version_is_the_one_in_the_package_metadata():
    assert playwright_snap.__version__ == importlib.metadata.version("playwright-snap")


def test_type_information_is_shipped():
    # py.typed tells type checkers that the package has type hints (PEP 561).
    assert importlib.resources.files("playwright_snap").joinpath("py.typed").is_file()


def test_readme_images_and_links_work_on_pypi():
    # PyPI shows the README without the repository around it, so a relative image
    # or link there would be broken.
    targets = re.findall(r'(?:src|srcset|href)="([^"]+)"|\]\(([^)\s]+)\)', README)
    relative = [t for pair in targets for t in pair if t and not re.match(r"[a-z][a-z0-9+.-]*:|#", t)]

    assert relative == []
