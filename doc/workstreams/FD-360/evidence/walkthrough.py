"""FD-360 manual walkthrough against the live 8889 sandbox (agent-performed,
Patrick away). Screenshots to /tmp/fd360-manual/."""

import json
import os
import re

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8889"
OUT = "/tmp/fd360-manual"
os.makedirs(OUT, exist_ok=True)

results = {}
console_errors = []


def run(pw, width, height, tag, interact):
    browser = pw.chromium.launch(
        executable_path=(
            "/Users/patrick/Library/Caches/ms-playwright/"
            "chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/"
            "chrome-headless-shell"
        )
    )
    page = browser.new_page(viewport={"width": width, "height": height})
    page.on(
        "console",
        lambda m: console_errors.append(f"{tag}: {m.text}") if m.type == "error" else None,
    )
    page.on("pageerror", lambda e: console_errors.append(f"{tag} pageerror: {e}"))
    page.goto(BASE + "/companion/")
    page.wait_for_selector("#strip circle", timeout=15000)
    page.screenshot(path=f"{OUT}/{tag}-1-resting.png")
    if interact:
        interact(page, tag)
    browser.close()


def desktop(page, tag):
    # C9: strip vocabulary — no band rects, no dashed gap paths at strip scale
    strip = page.eval_on_selector_all("#strip rect", "els => els.length")
    dashed = page.eval_on_selector_all(
        "#strip path[stroke-dasharray]", "els => els.length"
    )
    dots = page.eval_on_selector_all("#strip circle", "els => els.length")
    results["strip_band_rects"] = strip
    results["strip_dashed_paths"] = dashed
    results["strip_dots"] = dots
    results["strip_questions"] = page.eval_on_selector_all(
        "#strip text", "els => els.filter(e => e.textContent === '?').length"
    )

    # C10: tap strip -> expanded view
    page.click("#strip-card")
    page.wait_for_selector("#expanded circle", timeout=5000)
    results["expanded_band_rects"] = page.eval_on_selector_all(
        "#expanded rect", "els => els.length"
    )
    results["expanded_gap_dashes"] = page.eval_on_selector_all(
        "#expanded path[stroke-dasharray]", "els => els.length"
    )
    results["picker_chips"] = page.eval_on_selector_all(
        "#lane-pick .chp", "els => els.map(e => e.textContent)"
    )
    results["shelf_chips"] = page.eval_on_selector_all(
        "#shelf .shelfchip", "els => els.map(e => e.textContent)"
    )
    page.screenshot(path=f"{OUT}/{tag}-2-expanded.png", full_page=True)

    # C11: tap a mark -> sentence bubble
    page.click("#expanded circle >> nth=0")
    page.wait_for_selector("#bubble:not([hidden])", timeout=5000)
    results["bubble_sentence"] = page.text_content("#bubble")
    page.screenshot(path=f"{OUT}/{tag}-3-bubble.png")

    # C12: toggle a person chip off -> fewer rows
    before = page.eval_on_selector_all("#expanded text", "els => els.length")
    page.click("#lane-pick .chp >> nth=0")
    after = page.eval_on_selector_all("#expanded text", "els => els.length")
    results["picker_toggle_changed_render"] = after < before

    # shelf chip tap -> bubble
    page.click("#shelf .shelfchip >> nth=0")
    page.wait_for_selector("#bubble:not([hidden])", timeout=5000)
    results["shelf_sentence"] = page.text_content("#bubble")

    page.click("#overlay-close")

    # C2: real chat round-trip through the live pipeline
    page.fill("#chat-input", "Lately my sleep has been rough again, like back in the nineties.")
    n_before = page.eval_on_selector_all(".bub", "els => els.length")
    page.click("#chat-send")
    page.wait_for_function(
        f"document.querySelectorAll('.bub').length >= {n_before + 2}", timeout=90000
    )
    bubbles = page.eval_on_selector_all(
        ".bub", "els => els.map(e => ({cls: e.className, text: e.textContent}))"
    )
    results["chat_reply"] = bubbles[-1]
    page.screenshot(path=f"{OUT}/{tag}-4-chat.png")

    # C13 signal after chat: freshness note should say the picture is behind
    results["freshness_after_chat"] = page.text_content("#freshness")


def mobile(page, tag):
    # C14: input visible, strip on screen at 390px
    box = page.eval_on_selector(
        "#chat-input", "e => { const r = e.getBoundingClientRect(); return {top: r.top, bottom: r.bottom}; }"
    )
    vh = page.evaluate("window.innerHeight")
    results["mobile_input_visible"] = box["bottom"] <= vh
    strip_box = page.eval_on_selector(
        "#strip", "e => e.getBoundingClientRect().width"
    )
    results["mobile_strip_width"] = strip_box
    page.click("#strip-card")
    page.wait_for_selector("#expanded circle", timeout=5000)
    page.screenshot(path=f"{OUT}/{tag}-2-expanded.png", full_page=True)


with sync_playwright() as pw:
    run(pw, 1280, 800, "desktop", desktop)
    run(pw, 390, 844, "mobile390", mobile)

results["console_errors"] = console_errors
print(json.dumps(results, indent=2))
