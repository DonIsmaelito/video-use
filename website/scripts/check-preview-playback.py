"""Exercise real preview playback against a running site with Python Playwright."""

import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


class CheckLog(list):
    def append(self, check):
        super().append(check)
        print(json.dumps(check), flush=True)


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
          error: video.error?.message, muted: video.muted, autoplay: video.autoplay,
          src: video.currentSrc
        })));
      }, 20000);
    })""")
    assert await video.evaluate(
        "v => v.muted && v.defaultMuted && v.playsInline && v.autoplay && v.loop && !v.controls"
    )


async def visible_previews(scope):
    """Check every visible container, including clips partly revealed at an edge."""
    frames = scope.locator(".preview-media")
    indices = await frames.evaluate_all("""frames => new Promise(resolve => {
      if (!frames.length) return resolve([]);
      const seen = new Set();
      const visible = [];
      const observer = new IntersectionObserver(entries => {
        for (const entry of entries) {
          seen.add(entry.target);
          if (entry.isIntersecting && entry.intersectionRect.width > 16 &&
              entry.intersectionRect.height > 16)
            visible.push(frames.indexOf(entry.target));
        }
        if (seen.size === frames.length) {
          observer.disconnect();
          resolve(visible);
        }
      });
      frames.forEach(frame => observer.observe(frame));
    })""")
    assert indices, "No visible preview containers found"
    await asyncio.gather(*(moving(frames.nth(index).locator("video")) for index in indices))
    return len(indices)


async def looping(video):
    """Watch two uninterrupted loops without changing the native playback clock."""
    await moving(video)
    await video.evaluate("""video => new Promise((resolve, reject) => {
          let previous = video.currentTime;
          let loops = 0;
          const timer = setInterval(() => {
            const time = video.currentTime;
            if (previous > video.duration - 1 && time < 1) loops++;
            previous = time;
            if (loops >= 2 && !video.paused && time > 0 && video.readyState >= 2) {
              clearInterval(timer);
              clearTimeout(limit);
              resolve();
            }
          }, 100);
          const limit = setTimeout(() => {
            clearInterval(timer);
            reject(new Error(JSON.stringify({
              message: 'Preview did not complete two natural loops', loops, src: video.currentSrc,
              time: video.currentTime, duration: video.duration, paused: video.paused,
              ended: video.ended, seeking: video.seeking, ready: video.readyState,
              buffered: Array.from({length: video.buffered.length}, (_, i) =>
                [video.buffered.start(i), video.buffered.end(i)])
            })));
          }, Math.max(60000, video.duration * 4000));
        })""")
    await moving(video)


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
        assert await page.locator(".preview-playback-toggle").count() == 0
        hero = page.locator(".featured-card .preview-media video").first
        cards = page.locator(".featured-card")
        for index in range(await cards.count()):
            card = cards.nth(index)
            await card.evaluate(
                "e => e.scrollIntoView({block: 'nearest', inline: 'center', behavior: 'instant'})"
            )
            await moving(card.locator(".preview-media video"))
        await cards.first.evaluate(
            "e => e.scrollIntoView({block: 'nearest', inline: 'start', behavior: 'instant'})"
        )
        await moving(hero)
        report["checks"].append({
            "engine": engine, "width": width, "featuredClips": await cards.count(),
            "previewControls": False,
        })
        for sector in ["video-editing", "video-creation", "3d-visuals"]:
            section = page.locator(f'[data-sector="{sector}"]')
            await section.evaluate(
                "e => e.scrollIntoView({block: 'start', behavior: 'instant'})"
            )
            count = await visible_previews(section)
            assert await hero.evaluate("v => v.paused")
            if sector == "3d-visuals" and width == 1440:
                await looping(section.locator("video").first)
                report["checks"].append({"engine": engine, "uninterruptedNativeLoops": 2})
            await section.evaluate(
                "e => e.scrollIntoView({block: 'end', behavior: 'instant'})"
            )
            lower_count = await visible_previews(section)
            report["checks"].append(
                {"engine": engine, "width": width, "autoplay": sector,
                 "visibleClipsAtTop": count, "visibleClipsAtBottom": lower_count}
            )

        await page.evaluate("scrollTo(0, 0)")
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

        for label, route in [("Video Editing", "/video-editing"),
                             ("Video Creation", "/video-creation"),
                             ("3D Visuals", "/3d-visuals")]:
            await page.get_by_role("link", name=label, exact=True).first.click()
            await page.wait_for_url(f"**{route}")
            await page.locator(".video-card").first.scroll_into_view_if_needed()
            count = await visible_previews(page)
            assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            report["checks"].append({"engine": engine, "width": width,
                                     "route": route, "visibleClips": count})
        await page.goto(origin + "/library", wait_until="domcontentloaded")
        await page.locator(".video-card").first.scroll_into_view_if_needed()
        await visible_previews(page)
        await page.goto(origin + "/mcp", wait_until="domcontentloaded")
        await page.locator(".preview-media").first.scroll_into_view_if_needed()
        await visible_previews(page)
        report["checks"].append({
            "engine": engine,
            "width": width,
            "passed": ["scroll return", "modal pause and resume", "pageshow recovery",
                       "autoplay across collection routes", "library and MCP previews"],
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
        await moving(page.locator(".featured-card video").first)
        for sector in ["video-editing", "video-creation", "3d-visuals"]:
            section = page.locator(f'[data-sector="{sector}"]')
            await section.evaluate(
                "e => e.scrollIntoView({block: 'start', behavior: 'instant'})"
            )
            await visible_previews(section)
        assert await page.locator(".preview-playback-toggle").count() == 0
        report["checks"].append({
            "engine": engine,
            "reducedMotion": "all clip sectors autoplay without interaction or controls",
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
        await page.locator(".featured-caption span").first.click()
        await moving(page.locator(".featured-card video").first)
        assert await page.locator(".preview-playback-toggle").count() == 0
        report["checks"].append({
            "engine": engine,
            "blockedAutoplay": "normal interaction recovers playback without a play button",
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
    report = {"origin": args.origin, "checks": CheckLog(), "errors": []}
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
