from dataclasses import dataclass
import os
import random
import re
import threading
from typing import Callable

from playwright.sync_api import sync_playwright


@dataclass
class AppSettings:
    pizza_hut_url: str = "https://pizzahut.co.nz"
    coupons_url: str = "https://www.pizzahut.co.nz/order/coupons"
    required_codes_count: int = 250
    user_data_dir: str = "pizza_profile"
    browser_width: int = 1280
    browser_height: int = 900
    headless: bool = False


def generate_randomized_client_side_codes(
    required_codes_count: int, report: Callable[[str], None]
) -> list[str]:
    """Compile a randomized pool of mathematically valid codes."""
    report(f"Compiling {required_codes_count} automatic coupon codes...")
    valid_baseline_pool = [num for num in range(10000, 100000) if num % 3 == 0]
    random_sample = random.sample(valid_baseline_pool, required_codes_count)
    return [str(code) for code in random_sample]


def run(
    settings: AppSettings | None = None,
    report: Callable[[str], None] = print,
    ready_event: threading.Event | None = None,
    close_event: threading.Event | None = None,
    pause_event: threading.Event | None = None,
) -> None:
    settings = settings or AppSettings()
    ready_event = ready_event or threading.Event()
    close_event = close_event or threading.Event()
    pause_event = pause_event or threading.Event()
    pause_event.set()
    with sync_playwright() as p:
        user_data_dir = os.path.join(os.getcwd(), settings.user_data_dir)
        report(f"Launching browser with data persistence profile inside: {user_data_dir}")
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=settings.headless,
                viewport={"width": settings.browser_width, "height": settings.browser_height},
            )
        except Exception as error:
            if "existing browser session" in str(error).lower() or "profile" in str(error).lower():
                raise RuntimeError(
                    "The browser profile is already in use. Close the other browser session and try again."
                ) from error
            raise
        page = context.pages[0] if context.pages else context.new_page()

        try:
            report("Opening Pizza Hut New Zealand...")
            page.goto(settings.pizza_hut_url, wait_until="domcontentloaded")
            if settings.headless and settings.coupons_url:
                report(f"Opening coupons page: {settings.coupons_url}")
                page.goto(settings.coupons_url, wait_until="domcontentloaded")

            report("Confirm your location and add your items to the cart.")
            report("When the coupon field is visible, click Start Testing in the app.")
            while not ready_event.wait(0.1):
                if close_event.is_set():
                    report("Stopped before testing started.")
                    return

            coupon_pool = generate_randomized_client_side_codes(
                settings.required_codes_count, report
            )
            report(f"Starting automatic code check across {len(coupon_pool)} codes...")
            accepted_code = None

            page.wait_for_selector("input", state="visible", timeout=5000)
            inputs = page.locator("input:visible")
            coupon_input = None
            for i in range(inputs.count()):
                inp = inputs.nth(i)
                input_type = inp.get_attribute("type")
                if input_type in (None, "text", "search"):
                    coupon_input = inp
                    break

            if coupon_input is None:
                raise Exception("Fatal: Could not locate the coupon entry layout element.")

            add_coupon_btn = page.get_by_role(
                "button", name=re.compile("Add Coupon", re.IGNORECASE)
            ).first
            pizza_modal_container = page.locator("#container-modal-pizza")
            modal_submit_btn = page.locator('[data-tag="add-item-modal-btn"]')
            text_success_criteria = page.get_by_text(
                "coupon needs $8 or more to activate", exact=False
            )
            success_indicator_race = pizza_modal_container.or_(text_success_criteria)

            for idx, code in enumerate(coupon_pool, start=1):
                if close_event.is_set():
                    report("Stop requested. Ending the test loop.")
                    break
                while not pause_event.wait(0.1):
                    if close_event.is_set():
                        report("Stop requested. Ending the test loop.")
                        break
                if close_event.is_set():
                    break
                report(f"[{idx}/{len(coupon_pool)}] Fast-Testing Code: {code}")
                try:
                    coupon_input.fill(code)
                    if add_coupon_btn.is_visible():
                        add_coupon_btn.click(force=True, no_wait_after=True)
                    else:
                        page.locator(
                            "input:visible + button, button:has-text('Add')"
                        ).first.click(force=True, no_wait_after=True)

                    try:
                        success_indicator_race.wait_for(state="visible", timeout=850)
                    except Exception:
                        pass

                    if pizza_modal_container.is_visible() or modal_submit_btn.is_visible():
                        report(f"!!! SUCCESS !!! Functional coupon code found: [{code}]")
                        report("Modal container detected. Clicking exact [data-tag='add-item-modal-btn'] button...")
                        modal_submit_btn.click(force=True)
                        page.wait_for_timeout(2000)
                        accepted_code = code
                        break
                    if text_success_criteria.is_visible():
                        report(f"!!! SUCCESS !!! Functional conditional text criteria matched: [{code}]")
                        accepted_code = code
                        break
                except Exception:
                    pass

            report("================================================")
            if accepted_code:
                report(f"RUN TERMINATED: Valid working code added and claimed: {accepted_code}")
            else:
                report("RUN TERMINATED: Exhausted entire generated pool without structural acceptance match.")
            report("Browser remains open. Click Close Browser in the app when finished.")
            close_event.wait()
            report("Closing browser session.")
        finally:
            context.close()


if __name__ == "__main__":
    from app import SettingsApp

    SettingsApp().mainloop()
