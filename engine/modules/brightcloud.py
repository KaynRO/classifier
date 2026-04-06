import traceback, time
from typing import Optional
from helpers.constants import *
from helpers.utils import *
from helpers.logger import *


def log_exception(logger: Logger) -> None:
    trace = traceback.format_exc()
    logger.error(trace)


class Brightcloud:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = "https://www.brightcloud.com/tools/url-ip-lookup.php"

        # Element selectors for check flow
        self.url_input = "searchBox"
        self.submit_btn = ".btn.btn-base"
        self.cat_el = "div:has(h4:has-text('Web Category:'))"
        self.rep_el = "#threatScore"

        # Element selectors for submit flow
        self.submission_form = "#submissionForm"
        self.suggest_cat_link = 'a[data-target="#suggestCategory"]'
        self.cat_modal = "#suggestCategory"
        self.cat_modal_done_btn = '#suggestCategory button[data-dismiss="modal"]'
        self.req_email_input = "#email"
        self.req_comments_input = "#concern"
        self.req_submit_btn = 'a.btn-base[onclick*="submit"]'
        self.change_request_status = "#changeRequestStatus"


    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Optional[str]:
        self.logger.info(f" Targeting brightcloud ".center(60, "="))
        self.logger.info(f"[*] Using vendor endpoint at: {self.url}")

        load_url_and_wait_until_it_is_fully_loaded(driver, self.url)
        handle_cookie_consent(driver)
        handle_human_verification_checkbox(driver)

        # Enter URL into the search input
        try:
            wait_for_selector(driver, f"#{self.url_input}", timeout=global_wait_time * 1000)
            clear_element(driver, f"#{self.url_input}")
            wait_and_input_on_element(driver, f"#{self.url_input}", target_url)
        except Exception as e:
            self.logger.error(f"[-] Failed to find input element: {e}")
            raise

        solve_google_recaptcha(driver)

        # Submit lookup request
        try:
            wait_and_click_on_element(driver, self.submit_btn)
        except Exception as e:
            self.logger.error(f"[-] Failed to click submit button: {e}")
            raise

        # Wait for results
        try:
            wait_for_selector(driver, self.rep_el, state="visible", timeout=10000)
        except Exception:
            self.logger.warning("[!] Results did not appear or timed out")

        # Extract category from the result text
        cat_val = "UNKNOWN"
        if not return_reputation_only:
            try:
                raw_text = get_text(driver, self.cat_el)
                if "Web Category:" in raw_text:
                    cat_val = raw_text.split("Web Category:")[1].split("Request")[0].strip().strip("- ")
                self.logger.success(f"[+] Category: {cat_val}")
            except Exception:
                self.logger.warning("[!] Could not extract category")
        else:
            cat_val = None

        # Extract reputation score
        try:
            rep_val = get_text(driver, self.rep_el).strip("- ")
            self.logger.success(f"[+] Reputation: {rep_val.upper()}")
        except Exception:
            self.logger.warning("[!] Could not extract reputation")

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

            self.logger.info("[*] Starting new category submission process on Brightcloud")

            # Wait for the submission form to become visible after check
            wait_for_selector(driver, self.submission_form, state="visible", timeout=10000)

            # Ensure the URL field in the submission form is populated
            fill_element(driver, "#urlIP", url)

            # Open category selection modal
            wait_and_click_on_element(driver, self.suggest_cat_link)
            time.sleep(1)
            wait_for_selector(driver, self.cat_modal, state="visible", timeout=5000)

            # Select the desired category checkbox
            vendor_category = categories_map[category]["BrightCloud"]
            cat_checkbox = f'input[name="category[]"][data-category-name="{vendor_category}"]'
            wait_and_click_on_element(driver, cat_checkbox)
            self.logger.info(f"[*] Selected category: {vendor_category}")

            # Close the category modal
            wait_and_click_on_element(driver, self.cat_modal_done_btn)
            time.sleep(1)

            # Fill email field
            wait_and_input_on_element(driver, self.req_email_input, email)

            # Fill comments
            wait_and_input_on_element(driver, self.req_comments_input, construct_reason_for_review_comment(url, vendor_category, simple_message=True))

            # Solve the change request reCAPTCHA
            solve_google_recaptcha(driver)

            # Click Submit button
            wait_and_click_on_element(driver, self.req_submit_btn)
            time.sleep(3)

            # Verify success/error in status div
            try:
                status_text = get_text(driver, self.change_request_status)
                if "success" in status_text.lower() or "ok" in status_text.lower() or "thank" in status_text.lower():
                    self.logger.success(f"[+] Submission successful: {status_text}")
                else:
                    self.logger.warning(f"[!] Submission result: {status_text}")
            except Exception:
                body_text = get_text(driver, "body")
                if "success" in body_text.lower() or "thank" in body_text.lower():
                    self.logger.success("[+] Submission appears successful.")
                else:
                    self.logger.warning("[!] Could not verify submission success message")
        except Exception as e:
            log_exception(self.logger)
            raise e
