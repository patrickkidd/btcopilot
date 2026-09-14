"""Render every mockup frame in doc/chat-first/mockups/ to doc/chat-first/screens/ and copy
the chosen visual goldens in beside them, so SCREENS.md can show each view as it renders.

  python bin/screenshots.py

Idempotent: every run rewrites the same file names.
"""
import shutil
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

MASK = (255, 0, 255)
MIN_SIDE = 40

ROOT = Path(__file__).resolve().parent.parent
MOCKUPS = ROOT / "doc" / "chat-first" / "mockups"
SCREENS = ROOT / "doc" / "chat-first" / "screens"
GOLDENS = ROOT / "web" / "tests" / "visual"

# The goldens worth showing a reader: real renders of the built app on fixture records.
CHOSEN = [
    "picture.spec.ts-snapshots/rest-three40-phone-darwin.png",
    "picture.spec.ts-snapshots/rest-three40-desktop-darwin.png",
    "picture.spec.ts-snapshots/rest-empty-phone-darwin.png",
    "picture.spec.ts-snapshots/rest-one-phone-darwin.png",
    "picture.spec.ts-snapshots/rest-dense60-phone-darwin.png",
    "picture.spec.ts-snapshots/rest-dense60-desktop-darwin.png",
    "picture.spec.ts-snapshots/shelf-asked-phone-darwin.png",
    "picture.spec.ts-snapshots/tap-moment-phone-darwin.png",
    "picture.spec.ts-snapshots/cluster-open-phone-darwin.png",
    "picture.spec.ts-snapshots/cluster-open-desktop-darwin.png",
    "picture.spec.ts-snapshots/chip-in-composer-phone-darwin.png",
    "chat.spec.ts-snapshots/twelve-chips-phone-darwin.png",
    "chat.spec.ts-snapshots/twelve-chips-desktop-darwin.png",
    "moves.spec.ts-snapshots/spotlight-at-rest-phone-darwin.png",
    "moves.spec.ts-snapshots/offer-in-composer-phone-darwin.png",
    "moves.spec.ts-snapshots/menu-list-phone-darwin.png",
    "moves.spec.ts-snapshots/menu-list-desktop-darwin.png",
    "moves.spec.ts-snapshots/menu-editor-phone-darwin.png",
    "moves.spec.ts-snapshots/menu-editor-desktop-darwin.png",
    "board.spec.ts-snapshots/board-entry-offer-phone-darwin.png",
    "board.spec.ts-snapshots/board-first-move-phone-darwin.png",
    "board.spec.ts-snapshots/board-first-move-desktop-darwin.png",
    "board.spec.ts-snapshots/board-fifth-move-phone-darwin.png",
    "board.spec.ts-snapshots/board-fifth-move-desktop-darwin.png",
    "board.spec.ts-snapshots/board-last-move-phone-darwin.png",
    "board.spec.ts-snapshots/board-back-to-wire-phone-darwin.png",
    "moves.spec.ts-snapshots/board-triangle-phone-darwin.png",
    "moves.spec.ts-snapshots/move-conflict-phone-darwin.png",
    "moves.spec.ts-snapshots/move-distance-phone-darwin.png",
    "moves.spec.ts-snapshots/move-cutoff-phone-darwin.png",
]


def trim_mask(path: Path) -> None:
    """The visual tests paint the parts that change on every run — the thread under the picture —
    in flat magenta. Drop those rows off the top and bottom so a reader sees only what rendered."""
    im = Image.open(path).convert("RGB")
    px = im.load()
    w, h = im.size
    row = lambda y: any(px[x, y] == MASK for x in range(0, w, 4))
    top, bottom, left, right = 0, h, 0, w
    while top < bottom and row(top):
        top += 1
    while bottom > top and row(bottom - 1):
        bottom -= 1
    rest = [y for y in range(top, bottom) if row(y)]
    if rest:
        bottom = rest[0]
    col = lambda x: any(px[x, y] == MASK for y in range(top, bottom, 4))
    while left < right and col(left):
        left += 1
    while right > left and col(right - 1):
        right -= 1
    if right - left < MIN_SIDE or bottom - top < MIN_SIDE:
        print(f"almost entirely masked, left as recorded: {path.name}", file=sys.stderr)
    elif (top, bottom, left, right) != (0, h, 0, w):
        im.crop((left, top, right, bottom)).save(path)


def copy_goldens() -> list[str]:
    names = []
    for rel in CHOSEN:
        src = GOLDENS / rel
        if not src.exists():
            print(f"missing golden: {rel}", file=sys.stderr)
            continue
        name = src.name.replace("-darwin", "")
        shutil.copyfile(src, SCREENS / name)
        trim_mask(SCREENS / name)
        names.append(name)
    return names


def shoot_mockups() -> list[str]:
    names = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": 1400, "height": 1200},
            device_scale_factor=2,
            color_scheme="light",
        )
        for mockup in sorted(MOCKUPS.glob("*.html")):
            page.goto(mockup.as_uri())
            page.wait_for_load_state("networkidle")
            page.evaluate("document.fonts.ready")
            for frame in page.query_selector_all(".frame[id]"):
                name = f"{mockup.stem}-{frame.get_attribute('id')}.png"
                frame.screenshot(path=str(SCREENS / name))
                names.append(name)
        browser.close()
    return names


def main() -> int:
    SCREENS.mkdir(parents=True, exist_ok=True)
    frames = shoot_mockups()
    goldens = copy_goldens()
    print(f"{len(frames)} mockup frames, {len(goldens)} goldens → {SCREENS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
