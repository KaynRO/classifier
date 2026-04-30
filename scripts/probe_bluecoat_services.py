"""
One-off probe: read the full list of options from the BlueCoat sitereview
"Filtering Service" dropdown (#selFilteringService) on the submission form.

Reuses the existing BlueCoat module to handle Cloudflare turnstile and lookup,
then opens the submit form and enumerates options.
"""
import sys
import time

sys.path.insert(0, "/app/classifier")

from modules.bluecoat import BlueCoat
from helpers.utils import (
    set_captcha_api_key,
    wait_for_selector,
    wait_and_click_on_element,
    safe_find_elements,
)
from helpers.credentials import twocaptcha_api_key
from seleniumbase import Driver

TEST_DOMAIN = "https://example.com"

set_captcha_api_key(twocaptcha_api_key)
driver = Driver(uc=True, headless=True)
b = BlueCoat()

try:
    print(f"[*] Running BlueCoat.check on {TEST_DOMAIN}")
    cat = b.check(driver, TEST_DOMAIN)
    print(f"[*] BlueCoat returned current category: {cat!r}")

    print("[*] Clicking #btn-cat-safe to open submission form")
    wait_and_click_on_element(driver, "#btn-cat-safe")
    time.sleep(2)

    print("[*] Waiting for #selFilteringService...")
    wait_for_selector(driver, "#selFilteringService", state="visible", timeout=20000)

    print("[*] Opening filtering-service dropdown")
    wait_and_click_on_element(driver, "#selFilteringService input")
    time.sleep(1.5)

    options = safe_find_elements(driver, ".ng-dropdown-panel .ng-option")
    if not options:
        options = safe_find_elements(driver, ".ng-option")

    print()
    print("=" * 60)
    print(f"FILTERING SERVICE OPTIONS  ({len(options)} found)")
    print("=" * 60)
    for i, o in enumerate(options, 1):
        text = (o.text or "").strip()
        print(f"  {i:2}. {text!r}")
    print("=" * 60)

except Exception as e:
    print(f"[X] Probe failed: {e}")
    import traceback
    traceback.print_exc()
    try:
        with open("/tmp/probe_dump.html", "w") as f:
            f.write(driver.page_source)
        print("[*] Saved page source to /tmp/probe_dump.html")
    except Exception:
        pass
    sys.exit(1)
finally:
    driver.quit()
