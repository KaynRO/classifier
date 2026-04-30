import traceback, time
from typing import Optional
from helpers.constants import *
from helpers.utils import *
from helpers.logger import *


def log_exception(logger: Logger) -> None:
    trace = traceback.format_exc()
    logger.error(trace)


class Zvelo:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = "https://tools.zvelo.com/"
        self.url_input = "zvelo-search-input"
        self.submit_btn = "zvelo-search-button"

        # Element selectors for submit flow
        self.cat_sel = "miscat-select"
        self.miscat_btn = "miscat-submit"

        # Element selectors for results
        self.res_container = "#zvelo-search-results"
        self.cat_res = "#v4-content .result-categories li"
        self.brand_res = "#brand-safe .result-categories li"
        self.phish_res = "#phishing .result-categories li"
        self.conf_msg = "#zvelo-miscat-status span"


    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Optional[str]:
        self.logger.info(f" Targeting zvelo ".center(60, "="))
        self.logger.info(f"[*] Using vendor endpoint at: {self.url}")

        load_url_and_wait_until_it_is_fully_loaded(driver, self.url)
        handle_cookie_consent(driver)
        handle_human_verification_checkbox(driver)

        # Enter URL into the search input
        try:
            wait_for_selector(driver, f"#{self.url_input}", timeout=global_wait_time * 1000)
            clear_element(driver, f"#{self.url_input}")
            wait_and_input_on_element(driver, f"#{self.url_input}", target_url)
            time.sleep(2)
        except Exception as e:
            self.logger.error(f"[-] Failed to find input element: {e}")
            raise

        solve_google_recaptcha(driver)

        # Ensure submit button is enabled before clicking
        try:
            wait_for_function(driver, f"document.querySelector('#{self.submit_btn}').disabled === false", timeout=5000)
        except Exception:
            self.logger.debug("[!] Submit button not enabled, forcing via JS...")
            driver.execute_script(f"document.getElementById('{self.submit_btn}').disabled = false")

        try:
            wait_and_click_on_element(driver, f"#{self.submit_btn}")
        except Exception as e:
            self.logger.error(f"[-] Failed to click submit button: {e}")
            raise

        # Wait for results container to populate
        try:
            wait_for_selector(driver, f"{self.res_container} h4", state="visible", timeout=10000)
        except Exception:
            self.logger.warning("[!] Results did not appear or timed out")

        # Read each result section by id; text-walking once parsed the
        # heading "CONTENT CATEGORIES" as the category itself.
        def collect(selector: str) -> str:
            els = safe_find_elements(driver, selector)
            parts = [el.text.strip() for el in els if el.text and el.text.strip()]
            return ", ".join(parts)

        if return_reputation_only:
            return None

        content_cat = collect(self.cat_res) or "UNKNOWN"
        brand_raw = collect(self.brand_res).lower()
        phish_raw = collect(self.phish_res).lower()

        if brand_raw == "yes":
            brand_label = "Safe"
        elif brand_raw == "no":
            brand_label = "Not Safe"
        else:
            brand_label = brand_raw.title() if brand_raw else ""

        if phish_raw:
            phish_label = "No Phishing Detected" if "not" in phish_raw else "Phishing Detected"
        else:
            phish_label = ""

        parts = [content_cat]
        if brand_label:
            parts.append(brand_label)
        if phish_label:
            parts.append(phish_label)
        res_cat = " | ".join(parts)

        self.logger.success(f"[+] Category: {res_cat}")
        return res_cat


    def submit(self, driver, url: str, email: str, category: str) -> None:
        for protocol_url in prepare_urls_for_submission(url):
            self.submit_single_url(driver, protocol_url, email, category)


    def submit_single_url(self, driver, url: str, email: str, category: str) -> None:
        res = self.check(driver, url)

        if str(category).lower() in str(res).lower():
            self.logger.info("The proposed category is the same. Returning.")
            return

        # Select new category and submit
        self.logger.info("[*] Starting new category submission process on Zvelo")
        category = categories_map[category]["Zvelo"]
        select_option(driver, f"#{self.cat_sel}", label=category)

        try:
            wait_and_click_on_element(driver, f"#{self.miscat_btn}")
            wait_for_selector(driver, self.conf_msg, state="visible", timeout=10000)
            conf = get_text(driver, self.conf_msg)

            if "report has been sent" in conf.lower():
                self.logger.success("[+] Successfully submitted for review.")
            else:
                self.logger.info(f"[*] Something went wrong with the reclassification request. Response: {conf}")
        except Exception as e:
            self.logger.error(f"[-] An error occurred during the submission process: {str(e)}")
