import traceback, time
from typing import Optional
from helpers.constants import *
from helpers.utils import *
from helpers.logger import *


def log_exception(logger: Logger) -> None:
    trace = traceback.format_exc()
    logger.error(trace)


class PaloAlto:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = "https://urlfiltering.paloaltonetworks.com/"

        # Element selectors for check flow
        self.url_input = "id_url"
        self.search_btn = "button[type='submit']"
        self.res_list = "ul.result-list"
        self.cat_el = "li:has-text('Categories: ')"
        self.rep_el = "li:has-text('Risk Level: ')"

        # Element selectors for submit flow (form at /single_cr/ page)
        self.req_btn = "a:has-text('Request Change')"
        self.ack_checkbox = "#acknowledge-checkbox"
        self.ack_close_btn = "#close-modal"
        self.add_cat_btn = "#add_category_btn"
        self.cat_search_input = "#dropdown #searchInput"
        self.cat_hidden_input = "#id_new_category"
        self.email_input = "#id_your_email"
        self.email_conf = "#id_confirm_email"
        self.comment_input = "#id_comment"
        self.submit_btn = "input[type='submit']"


    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Optional[str]:
        self.logger.info(f" Targeting paloalto ".center(60, "="))
        self.logger.info(f"[*] Using vendor endpoint at: {self.url}")

        load_url_and_wait_until_it_is_fully_loaded(driver, self.url)
        handle_cookie_consent(driver)
        handle_human_verification_checkbox(driver)

        # Wait for page to fully render
        try:
            wait_for_selector(driver, f"#{self.url_input}", timeout=global_wait_time * 1000)
        except Exception as e:
            self.logger.error(f"[-] Failed to find input element: {e}")
            raise

        # Solve reCAPTCHA first (before entering URL to minimize time between solve and submit)
        solve_google_recaptcha(driver)

        # Enter URL and immediately click search to avoid token expiry
        clear_element(driver, f"#{self.url_input}")
        wait_and_input_on_element(driver, f"#{self.url_input}", target_url)
        try:
            wait_and_click_on_element(driver, self.search_btn)
            wait_for_load_state(driver, "networkidle", timeout=30000)
        except Exception as e:
            self.logger.error(f"[-] Failed to click search button: {e}")
            raise

        # Wait for category result to appear
        try:
            wait_for_selector(driver, self.cat_el, state="visible", timeout=10000)
        except Exception:
            self.logger.warning("[!] Results did not appear or timed out")

        # Extract category
        cat_val = "UNKNOWN"
        if not return_reputation_only:
            try:
                raw_cat = get_text(driver, self.cat_el)
                cat_val = raw_cat.replace("Categories: ", "").strip()
                self.logger.success(f"[+] Category: {cat_val}")
            except Exception:
                self.logger.warning("[!] Could not extract category")
        else:
            cat_val = None

        # Extract reputation
        try:
            rep_val = get_text(driver, self.rep_el).replace("Risk Level: ", "").strip()
            self.logger.success(f"[+] Reputation: {rep_val.upper()}")
        except Exception:
            pass

        return cat_val


    def submit(self, driver, url: str, email: str, category: str) -> None:
        for protocol_url in prepare_urls_for_submission(url):
            self.submit_single_url(driver, protocol_url, email, category)


    def submit_single_url(self, driver, url: str, email: str, category: str) -> None:
        try:
            cat_val = self.check(driver, url)

            if str(category).lower() in str(cat_val).lower():
                self.logger.info("[*] Proposed category is the same. Returning.")
                return

            # Click "Request Change" which navigates to /single_cr/ page
            self.logger.info("[*] Starting new category submission process on PaloAlto")
            wait_and_click_on_element(driver, self.req_btn)
            time.sleep(3)

            # Dismiss the acknowledgement modal if present
            try:
                if count_elements(driver, self.ack_checkbox) > 0:
                    wait_and_click_on_element(driver, self.ack_checkbox)
                    time.sleep(1)
                    wait_and_click_on_element(driver, self.ack_close_btn)
                    time.sleep(1)
            except Exception:
                pass

            # Wait for the change request form to load
            wait_for_selector(driver, self.email_input, state="visible", timeout=15000)
            self.logger.info("[*] Change request form loaded")

            # Select category via jQuery pillbox widget
            vendor_category = categories_map[category]["PaloAlto"]
            try:
                wait_and_click_on_element(driver, self.add_cat_btn)
                time.sleep(1)

                # Use jQuery to trigger click on the correct category item
                # Native clicks don't fire jQuery event handlers on this page
                driver.execute_script(f"""
                    $('#cate_list li.enable').filter(function() {{
                        return $(this).find('.results-title').text() === '{vendor_category}';
                    }}).trigger('click');
                """)
                time.sleep(1)
                self.logger.info(f"[*] Selected category: {vendor_category}")
            except Exception as e:
                self.logger.warning(f"[!] Could not select category: {e}")

            wait_and_input_on_element(driver, self.email_input, email)
            wait_and_input_on_element(driver, self.email_conf, email)
            wait_and_input_on_element(driver, self.comment_input, construct_reason_for_review_comment(url, category))

            solve_google_recaptcha(driver)

            wait_and_click_on_element(driver, self.submit_btn)
            time.sleep(5)

            # Verify submission - check for validation errors or success indicators
            body_text = get_text(driver, "body")
            if "category field is required" in body_text.lower():
                self.logger.warning("[!] Submission failed - category was not selected properly.")
            elif "thank" in body_text.lower() or "received" in body_text.lower() or "change request" not in body_text.lower():
                self.logger.success("[+] Submission successful - you will receive an email confirmation.")
            else:
                self.logger.info("[*] Submission attempted - check email for confirmation.")
        except Exception as e:
            log_exception(self.logger)
            raise e
