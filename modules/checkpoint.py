import traceback, time, base64, requests, json
from typing import Optional
from helpers.constants import *
from helpers.utils import *
from helpers.logger import *


class CheckPoint:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = "https://usercenter.checkpoint.com/ucapps/urlcat/"
        self.api_url = "https://usercenter.checkpoint.com/api/url-cat-mms/api/query"


    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Optional[str]:
        self.logger.info(f" Targeting checkpoint ".center(60, "="))
        self.logger.info(f"[*] Using vendor endpoint at: {self.url}")

        try:
            clean_domain = target_url.replace("https://", "").replace("http://", "").strip("/")

            # Try API-based approach first (no reCAPTCHA needed for queries)
            category = self.check_via_api(clean_domain)

            # Fallback to browser if API fails
            if category == "NOT FOUND":
                category = self.check_via_browser(driver, clean_domain)

            if not return_reputation_only:
                self.logger.success(f"[+] Category: {category.upper()}")
            else:
                category = None

            return category

        except Exception as e:
            self.logger.error(f"[-] Check Point check failed: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise e


    def check_via_api(self, domain: str) -> str:
        try:
            encoded = base64.b64encode(domain.encode()).decode()
            response = requests.post(
                self.api_url,
                headers={"Content-Type": "application/json"},
                json={"urlEncoded": encoded},
                timeout=15
            )

            if response.status_code != 200:
                self.logger.debug(f"[*] API returned status {response.status_code}")
                return "NOT FOUND"

            data = response.json()
            categories = data.get("categories", [])
            if categories:
                return ", ".join(categories)

            return "NOT FOUND"

        except Exception as e:
            self.logger.debug(f"[*] API approach failed: {e}")
            return "NOT FOUND"


    def check_via_browser(self, driver, domain: str) -> str:
        try:
            self.logger.info("[*] Trying browser-based approach")
            driver.uc_open_with_reconnect(self.url, reconnect_time=5)
            time.sleep(5)

            # Try to find the input field — the SPA renders a React app
            input_selectors = [
                "input[type='text']",
                "input[placeholder*='URL']",
                "input[placeholder*='url']",
                "input[aria-label*='URL']",
                "input"
            ]

            for selector in input_selectors:
                try:
                    if count_elements(driver, selector) > 0:
                        wait_and_input_on_element(driver, selector, domain)

                        # Try submit
                        submit_selectors = [
                            "button[type='submit']",
                            "button:has-text('Look')",
                            "button:has-text('Submit')",
                            "button:has-text('Check')"
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
                        break
                except Exception:
                    continue

            body_text = get_text(driver, "body")
            return self.extract_category(body_text)

        except Exception as e:
            self.logger.debug(f"[*] Browser approach failed: {e}")
            return "NOT FOUND"


    def extract_category(self, body_text: str) -> str:
        category = "NOT FOUND"

        try:
            lines = body_text.split("\n")

            for i, line in enumerate(lines):
                line_stripped = line.strip()

                if "category" in line_stripped.lower() and ":" in line_stripped:
                    parts = line_stripped.split(":", 1)
                    if len(parts) > 1 and parts[1].strip():
                        val = parts[1].strip()
                        if val.lower() not in ["", "n/a", "category"]:
                            category = val
                            break

                if "classification" in line_stripped.lower() and ":" in line_stripped:
                    parts = line_stripped.split(":", 1)
                    if len(parts) > 1 and parts[1].strip():
                        category = parts[1].strip()
                        break

        except Exception:
            pass

        return category
