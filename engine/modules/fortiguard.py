import traceback, time, re
from typing import Optional
from helpers.constants import *
from helpers.utils import *
from helpers.logger import *


class FortiGuard:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = "https://www.fortiguard.com/webfilter"


    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Optional[str]:
        self.logger.info(f" Targeting fortiguard ".center(60, "="))
        self.logger.info(f"[*] Using vendor endpoint at: {self.url}")

        try:
            clean_domain = target_url.replace("https://", "").replace("http://", "").strip("/")

            # Use query parameter approach to bypass CAPTCHA form
            query_url = f"{self.url}?q={clean_domain}"
            self.logger.info(f"[*] Loading: {query_url}")

            driver.uc_open_with_reconnect(query_url, reconnect_time=5)
            time.sleep(3)

            body_text = get_text(driver, "body")

            # Check if we're blocked by WAF
            if "Web Page Blocked" in body_text or "Attack ID" in body_text:
                self.logger.warning("[!] Blocked by FortiGuard WAF — trying form-based approach")
                category = self.check_via_form(driver, clean_domain)
            else:
                category = self.extract_category(body_text)

            if not return_reputation_only:
                self.logger.success(f"[+] Category: {category.upper()}")
            else:
                category = None

            return category

        except Exception as e:
            self.logger.error(f"[-] FortiGuard check failed: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise e


    def check_via_form(self, driver, domain: str) -> str:
        try:
            load_url_and_wait_until_it_is_fully_loaded(driver, self.url)
            time.sleep(3)

            body_text = get_text(driver, "body")
            if "Web Page Blocked" in body_text or "Attack ID" in body_text:
                self.logger.warning("[!] FortiGuard WAF is blocking access from this IP")
                return "BLOCKED BY WAF"

            # Try to find and interact with the form
            input_selectors = [
                "input#query",
                "input[name='q']",
                "input[name='url']",
                "input[type='text']",
                "input[placeholder*='URL']",
                "input[placeholder*='url']"
            ]

            for selector in input_selectors:
                try:
                    if count_elements(driver, selector) > 0:
                        wait_and_input_on_element(driver, selector, domain)

                        submit_selectors = [
                            "button[type='submit']",
                            "input[type='submit']",
                            "button:has-text('Search')",
                            "button:has-text('Lookup')"
                        ]
                        for btn in submit_selectors:
                            try:
                                if count_elements(driver, btn) > 0:
                                    wait_and_click_on_element(driver, btn)
                                    break
                            except Exception:
                                continue
                        else:
                            press_key(driver, selector, "Enter")

                        time.sleep(5)
                        body_text = get_text(driver, "body")
                        return self.extract_category(body_text)
                except Exception:
                    continue

            return "NOT FOUND"

        except Exception as e:
            self.logger.debug(f"[*] Form-based approach failed: {e}")
            return "NOT FOUND"


    def extract_category(self, body_text: str) -> str:
        category = "NOT FOUND"

        try:
            lines = body_text.split("\n")

            for i, line in enumerate(lines):
                line_stripped = line.strip()

                # Look for "Category:" label followed by category name
                if "category:" in line_stripped.lower():
                    parts = line_stripped.split(":", 1)
                    if len(parts) > 1 and parts[1].strip():
                        category = parts[1].strip()
                        break
                    if i + 1 < len(lines) and lines[i + 1].strip():
                        category = lines[i + 1].strip()
                        break

                # FortiGuard often shows category after "Web Rating:" or similar
                if "web rating" in line_stripped.lower() or "web filter" in line_stripped.lower():
                    parts = line_stripped.split(":", 1)
                    if len(parts) > 1 and parts[1].strip():
                        category = parts[1].strip()
                        break

        except Exception:
            pass

        return category
