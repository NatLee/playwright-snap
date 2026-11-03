"""What the installed package and its PyPI page need."""
import importlib.metadata
import importlib.resources

import playwright_snap


def test_version_is_the_one_in_the_package_metadata():
    assert playwright_snap.__version__ == importlib.metadata.version("playwright-snap")


def test_type_information_is_shipped():
    # py.typed tells type checkers that the package has type hints (PEP 561).
    assert importlib.resources.files("playwright_snap").joinpath("py.typed").is_file()
