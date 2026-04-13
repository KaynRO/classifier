from typing import Optional
from helpers.utils import *
from helpers.logger import *


class LightspeedSystems:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = "https://archive.lightspeedsystems.com/"

        # Element selectors for check flow
        self.url_input = ".Input_wrapper input"
        self.submit_button = ".Input_wrapper button"
        self.domain_not_found = ".no-found-container"
        self.category_result_element = ".table_single tbody tr:first-child"


    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Optional[str]:
        self.logger.info(f" Targeting lightspeedsystems ".center(60, "="))
        self.logger.info(f"[*] Using vendor endpoint at: {self.url}")

        load_url_and_wait_until_it_is_fully_loaded(driver, self.url)

        # Enter URL and submit lookup
        wait_and_input_on_element(driver, self.url_input, target_url)
        wait_and_click_on_element(driver, self.submit_button)

        # Wait for either the result or "not found" message
        try:
            wait_for_selector(driver, f"{self.category_result_element},{self.domain_not_found}", timeout=30000)
        except Exception:
            pass

        # Check if domain was not found
        if count_elements(driver, self.domain_not_found) > 0:
            not_found_text = get_text(driver, self.domain_not_found)
            if "not found" in not_found_text.lower():
                self.logger.success("[+] Category: NONE")
                return None

        # Extract category from result table
        try:
            category_text = get_text(driver, self.category_result_element)
            cat_val = category_text.splitlines()[-1].strip() if category_text else "UNKNOWN"
            self.logger.success(f"[+] Category: {cat_val.upper()}")
            return cat_val
        except Exception:
            self.logger.warning("[!] Could not extract category")
            return "UNKNOWN"
