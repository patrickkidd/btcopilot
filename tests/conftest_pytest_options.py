import pytest


def pytest_addoption(parser):
    """Add custom command-line options for pytest"""
    parser.addoption(
        "--e2e",
        action="store_true",
        default=False,
        help="run end-to-end tests (requires browser setup)"
    )