"""What familydiagram.com answers on the app box."""

import re

from btcopilot.tests.test_boxsecrets import DEPLOY

SITE = re.search(
    r"^familydiagram\.com \{\n(.*?)^\}", (DEPLOY / "Caddyfile").read_text(), re.M | re.S
).group(1)


def test_the_app_is_served_at_slash_app():
    # R-0356
    assert re.search(r"handle /app\* \{\s*(#[^\n]*\n\s*)*reverse_proxy fd-app:", SITE)


def test_everything_else_keeps_redirecting_to_alaska_family_systems():
    # R-0356
    catchall = re.search(r"^    handle \{\n(.*?)^    \}", SITE, re.M | re.S).group(1)
    assert catchall.strip() == (
        "redir https://alaskafamilysystems.com/family-diagram{uri} 301"
    )


def test_the_update_feeds_are_forwarded_to_the_legacy_box():
    # R-0600
    feeds = re.search(r"^    handle /appcast_\*\.xml \{\n(.*?)^    \}", SITE, re.M | re.S)
    assert feeds
    assert "reverse_proxy https://database.familydiagram.com" in feeds.group(1)
    assert "header_up Host familydiagram.com" in feeds.group(1)


def test_the_bare_address_is_the_landing_page():
    # R-0601
    landing = re.search(r"^    handle / \{\n(.*?)^    \}", SITE, re.M | re.S)
    assert landing
    assert landing.group(1).strip() == "reverse_proxy fd-app:8888"
    assert landing.start() < re.search(r"^    handle \{", SITE, re.M).start()
