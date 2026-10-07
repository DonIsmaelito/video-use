"""Exercise real preview playback against a running site with Python Playwright."""

import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


async def moving(video):
    """A loaded poster or video element does not prove that frames are advancing."""
    await video.wait_for()
    await video.evaluate("""video => new Promise((resolve, reject) => {
      const start = video.currentTime;
      const timer = setInterval(() => {
        if (!video.paused && video.readyState >= 2 &&
            video.currentTime !== start && getComputedStyle(video).opacity === '1') {
          clearInterval(timer);
          clearTimeout(limit);
          resolve();
        }
      }, 100);
      const limit = setTimeout(() => {
        clearInterval(timer);
        reject(new Error(JSON.stringify({
          time: video.currentTime, paused: video.paused, ready: video.readyState,
          error: video.error?.message, muted: video.muted, autoplay: video.autoplay
        })));
      }, 20000);
    })""")
    assert await video.evaluate(
        "v => v.muted && v.defaultMuted && v.playsInline && v.autoplay"
    )


async def all_paused(page):
    await page.wait_for_function(
        "[...document.querySelectorAll('.preview-media video')].every(v => v.paused)"
    )


async def check_viewport(browser, engine, width, origin, report):
    context = await browser.new_context(
        viewport={"width": width, "height": 900 if width > 768 else 844},
        is_mobile=width < 768,
        has_touch=width < 768,
        reduced_motion="no-preference",
    )
    try:
        page = await context.new_page()
        page.on("pageerror", lambda error: report["errors"].append(str(error)))
        await page.goto(origin, wait_until="domcontentloaded")
        hero = page.locator(".featured-card .preview-media video").first
        await moving(hero)
        for sector in ["video-editing", "video-creation", "3d-visuals"]:
            section = page.locator(f'[data-sector="{sector}"]')
            await section.evaluate(
                "e => e.scrollIntoView({block: 'start', behavior: 'instant'})"
            )
            await moving(section.locator("video").first)
            assert await hero.evaluate("v => v.paused")
            report["checks"].append(
                {"engine": engine, "width": width, "autoplay": sector}
            )

        await page.evaluate("scrollTo(0, 0)")
        await moving(hero)
        await page.get_by_role("button", name="Pause video previews", exact=True).click()
        await all_paused(page)
        await page.get_by_role("button", name="Play video previews", exact=True).click()
        await moving(hero)

        await page.get_by_role("button", name="Connect MCP", exact=True).click()
        await page.get_by_role("dialog").wait_for()
        await all_paused(page)
        await page.keyboard.press("Escape")
        await page.get_by_role("dialog").wait_for(state="detached")
        await moving(hero)

        # Explicitly exercise the page-restoration event handler.
        await hero.evaluate("v => v.pause()")
        await page.evaluate("dispatchEvent(new PageTransitionEvent('pageshow'))")
        await moving(hero)

        await page.get_by_role("button", name="Pause video previews", exact=True).click()
        await page.get_by_role("link", name="3D Visuals", exact=True).first.click()
        await page.wait_for_url("**/3d-visuals")
        await page.locator(".video-card").first.scroll_into_view_if_needed()
        await page.wait_for_timeout(300)
        await all_paused(page)
        await page.get_by_role("button", name="Play video previews", exact=True).click()
        await page.locator(".video-card").first.scroll_into_view_if_needed()
        await moving(page.locator(".video-card video").first)
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        report["checks"].append({
            "engine": engine,
            "width": width,
            "passed": ["scroll return", "pause and play", "modal pause and resume",
                       "pageshow recovery", "choice across route navigation"],
        })
    finally:
        await context.close()


async def check_motion_and_policy(browser, engine, origin, report):
    context = await browser.new_context(
        viewport={"width": 390, "height": 844}, reduced_motion="reduce"
    )
    try:
        page = await context.new_page()
        page.on("pageerror", lambda error: report["errors"].append(str(error)))
        await page.goto(origin, wait_until="domcontentloaded")
        await page.locator(".preview-media video").first.wait_for()
        await page.wait_for_timeout(300)
        await all_paused(page)
        await page.get_by_role("button", name="Play video previews", exact=True).click()
        await moving(page.locator(".featured-card video").first)
        report["checks"].append({
            "engine": engine,
            "reducedMotion": "paused by default and explicit play succeeds",
        })
    finally:
        await context.close()

    context = await browser.new_context(
        viewport={"width": 1440, "height": 900}, reduced_motion="no-preference"
    )
    try:
        # Simulate a policy rejection independently of machine-specific settings.
        await context.add_init_script("""
          window.allowPreview = false;
          const play = HTMLMediaElement.prototype.play;
          HTMLMediaElement.prototype.play = function(...args) {
            if (!window.allowPreview)
              return Promise.reject(new DOMException('Test autoplay policy', 'NotAllowedError'));
            return play.apply(this, args);
          };
          document.addEventListener('play', event => {
            if (!window.allowPreview) event.target.pause();
          }, true);
          document.addEventListener('pointerdown', () => {
            window.allowPreview = true;
          }, {capture: true, once: true});
        """)
        page = await context.new_page()
        page.on("pageerror", lambda error: report["errors"].append(str(error)))
        await page.goto(origin, wait_until="domcontentloaded")
        await page.locator(".preview-media video").first.wait_for()
        await page.wait_for_timeout(400)
        await page.get_by_role("button", name="Play video previews", exact=True).click()
        await moving(page.locator(".featured-card video").first)
        await page.get_by_role("button", name="Pause video previews", exact=True).wait_for()
        report["checks"].append({
            "engine": engine,
            "blockedAutoplay": "trusted play control recovers without toggling back off",
        })
    finally:
        await context.close()


async def main(args, report):
    async with async_playwright() as playwright:
        for engine in args.browser or ["chromium", "webkit"]:
            options = {"headless": True}
            if engine == "chromium" and args.chromium_executable:
                options["executable_path"] = args.chromium_executable
            browser = await getattr(playwright, engine).launch(**options)
            try:
                for width in [1440, 390]:
                    await check_viewport(browser, engine, width, args.origin, report)
                await check_motion_and_policy(browser, engine, args.origin, report)
                print(f"{engine}: all playback checks passed", flush=True)
            finally:
                await browser.close()
    assert not report["errors"], report["errors"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin", nargs="?", default="http://localhost:3000")
    parser.add_argument("--browser", action="append", choices=["chromium", "webkit"])
    parser.add_argument("--chromium-executable", help="Optional installed Chromium path")
    parser.add_argument("--output", type=Path, help="Optional JSON evidence file")
    args = parser.parse_args()
    report = {"origin": args.origin, "checks": [], "errors": []}
    try:
        asyncio.run(main(args, report))
        report["passed"] = True
    except Exception as error:
        report["passed"] = False
        report["failure"] = repr(error)
        raise
    finally:
        result = json.dumps(report, indent=2)
        if args.output:
            args.output.write_text(result + "\n")
        print(result)
