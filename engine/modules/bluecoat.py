import traceback, time
from helpers.utils import *
from helpers.constants import *
from helpers.logger import *


def log_exception(logger: Logger) -> None:
    trace = traceback.format_exc()
    logger.error(trace)


class BlueCoat:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = "https://sitereview.bluecoat.com/#/"
        self.url_input = "txtUrl"
        self.submit_btn = "btnLookup"
        self.turnstile_sitekey = "0x4AAAAAAAh1PLCympf5Log4"

        # Element selectors for submit flow (ng-select dropdowns use input inside)
        self.sub_cat1_input = "#txtCat1 input"
        self.sub_filter_input = "#selFilteringService input"
        self.sub_email = "#email"
        self.sub_comment = "#txtComments"
        self.sub_btn = "#submit2"
        self.ng_select_option = ".ng-option:not(.ng-option-disabled)"


    def solve_turnstile_and_validate(self, driver) -> bool:
        from helpers.captcha_solver import CaptchaSolver

        solver = CaptchaSolver(get_captcha_api_key())

        captcha_info = {
            "type": "turnstile",
            "sitekey": self.turnstile_sitekey,
            "url": driver.current_url,
        }

        self.logger.info("[*] Captcha detected (turnstile). Attempting to solve...")
        solution = solver.solve_captcha(captcha_info)
        if not solution:
            self.logger.error("[-] Failed to solve BlueCoat Turnstile")
            return False

        # Inject token and send validation request to BlueCoat
        token = solution["token"]
        driver.execute_script("""
            var token = arguments[0];
            document.querySelectorAll('input[name="cf-turnstile-response"]').forEach(function(i) { i.value = token; });
            document.querySelectorAll('.cf-turnstile input[type="hidden"]').forEach(function(i) { i.value = token; });

            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/resource/are-you-human', false);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.send(JSON.stringify({token: token}));
            return xhr.status;
        """, token)
        time.sleep(2)

        self.logger.info("[+] BlueCoat Turnstile validated")
        return True


    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> str:
        self.logger.info(f" Targeting bluecoat ".center(60, "="))
        self.logger.info(f"[*] Using vendor endpoint at: {self.url}")

        load_url_and_wait_until_it_is_fully_loaded(driver, self.url)
        handle_cookie_consent(driver)
        solve_cloudflare_turnstile(driver)

        # Enter URL and submit lookup
        wait_for_selector(driver, f"#{self.url_input}", timeout=global_wait_time * 1000)
        clear_element(driver, f"#{self.url_input}")
        wait_and_input_on_element(driver, f"#{self.url_input}", target_url)
        wait_and_click_on_element(driver, f"#{self.submit_btn}")
        time.sleep(3)

        # Handle human verification if prompted
        body_text = get_text(driver, "body")
        if "verify" in body_text.lower() and "human" in body_text.lower():
            self.solve_turnstile_and_validate(driver)
            time.sleep(2)

            # Reload and re-submit after verification
            load_url_and_wait_until_it_is_fully_loaded(driver, self.url)
            time.sleep(2)

            wait_for_selector(driver, f"#{self.url_input}", timeout=global_wait_time * 1000)
            clear_element(driver, f"#{self.url_input}")
            wait_and_input_on_element(driver, f"#{self.url_input}", target_url)
            wait_and_click_on_element(driver, f"#{self.submit_btn}")
            time.sleep(3)

        # Wait for results page to load (Angular route change)
        time.sleep(5)

        # Extract category from page body text
        body_text = get_text(driver, "body")
        cat_val = "UNKNOWN"

        if "not yet been rated" in body_text.lower():
            cat_val = "NONE"
        else:
            # Look for categorization text in the page
            for line in body_text.split("\n"):
                line = line.strip()
                # Skip common non-category lines
                if not line or len(line) > 100:
                    continue
                if any(skip in line.lower() for skip in ["submit", "email", "comment", "filter", "review"]):
                    continue
                # Categorization result appears as a standalone category name
                if line in bluecoat_website_categories:
                    cat_val = line
                    break

            # Fallback: check for category-like patterns
            if cat_val == "UNKNOWN":
                for line in body_text.split("\n"):
                    stripped = line.strip()
                    if stripped and "Categorization:" in stripped:
                        cat_val = stripped.split("Categorization:")[-1].strip()
                        break

        self.logger.success(f"[+] Category: {cat_val.upper()}")
        return cat_val


    def submit(self, driver, url: str, email: str, category: str) -> None:
        for protocol_url in prepare_urls_for_submission(url):
            self.submit_single_url(driver, protocol_url, email, category)


    def submit_single_url(self, driver, url: str, email: str, category: str) -> None:
        try:
            cat_val = self.check(driver, url)

            if str(category).lower() in str(cat_val).lower():
                self.logger.info("The proposed category is the same. Returning.")
                return

            self.logger.info("[*] Starting new category submission process on BlueCoat")

            # Click "safe category" button to reveal the submission form
            wait_and_click_on_element(driver, "#btn-cat-safe")
            time.sleep(2)
            wait_for_selector(driver, self.sub_cat1_input, state="visible", timeout=10000)

            # Select category via ng-select: click input, type, select option
            vendor_category = categories_map[category]["Bluecoat"]
            wait_and_click_on_element(driver, self.sub_cat1_input)
            fill_element(driver, self.sub_cat1_input, vendor_category)
            time.sleep(1)
            wait_and_click_on_element(driver, self.ng_select_option)
            self.logger.info(f"[*] Selected category: {vendor_category}")

            # Select filtering service via ng-select
            wait_and_click_on_element(driver, self.sub_filter_input)
            fill_element(driver, self.sub_filter_input, "Other")
            time.sleep(1)
            wait_and_click_on_element(driver, self.ng_select_option)

            # Fill email and comments
            wait_and_input_on_element(driver, self.sub_email, email)
            wait_and_input_on_element(driver, self.sub_comment, construct_reason_for_review_comment(url, category))

            # Submit
            wait_and_click_on_element(driver, self.sub_btn)
            time.sleep(5)

            # Dismiss "Unresolvable Host" dialog if present
            try:
                if count_elements(driver, "#btnOk") > 0:
                    wait_and_click_on_element(driver, "#btnOk")
                    time.sleep(2)
            except Exception:
                pass

            # Verify submission success - page navigates to /#/submission route
            current_url = driver.current_url or ""
            body_text = get_text(driver, "body")
            if "submission" in current_url or "already submitted" in body_text.lower() or "has been reviewed" in body_text.lower() or "received" in body_text.lower():
                self.logger.success("[+] Successfully submitted for review. You will receive an email when the category is updated.")
            else:
                self.logger.info(f"[*] Something went wrong submitting the request")
        except Exception:
            log_exception(self.logger)
            raise
