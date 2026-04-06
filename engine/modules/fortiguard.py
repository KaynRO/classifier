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

            # Load the main webfilter page (not ?q= which gets WAF blocked)
            load_url_and_wait_until_it_is_fully_loaded(driver, self.url)
            time.sleep(3)

            body_text = get_text(driver, "body")

            # Check for WAF block
            if "access" in body_text.lower() and "denied" in body_text.lower():
                self.logger.warning("[!] FortiGuard denied access — trying UC reconnect")
                driver.uc_open_with_reconnect(self.url, reconnect_time=5)
                time.sleep(3)
                body_text = get_text(driver, "body")
                if "denied" in body_text.lower():
                    self.logger.error("[-] FortiGuard still blocking access")
                    return "Blocked By WAF"

            # Enter URL in the search field
            url_input = "input[name='url']"
            try:
                wait_for_selector(driver, url_input, timeout=5000)
                clear_element(driver, url_input)
                wait_and_input_on_element(driver, url_input, clean_domain)
                self.logger.info(f"[*] Entered domain: {clean_domain}")
            except Exception:
                self.logger.error("[-] Could not find URL input field")
                return "Not Found"

            time.sleep(1)

            # Solve ALTCHA captcha — click the checkbox
            self.logger.info("[*] Looking for ALTCHA captcha checkbox...")
            try:
                altcha_cb = driver.find_elements("css selector", "input[id*='altcha_checkbox']")
                if altcha_cb:
                    driver.execute_script("arguments[0].click()", altcha_cb[0])
                    self.logger.info("[*] Clicked ALTCHA checkbox")
                    # Wait for proof-of-work to complete
                    time.sleep(3)

                    # Verify checkbox is checked
                    is_checked = altcha_cb[0].is_selected()
                    self.logger.info(f"[*] ALTCHA checked: {is_checked}")
                else:
                    self.logger.debug("[*] No ALTCHA checkbox found, proceeding anyway")
            except Exception as e:
                self.logger.warning(f"[!] ALTCHA handling failed: {e}")

            # Handle secondary image captcha ("Please enter the code")
            try:
                code_input = driver.find_elements("css selector", "input[name='code']")
                if code_input and code_input[0].is_displayed():
                    self.logger.info("[*] Secondary image captcha detected — solving with 2Captcha...")
                    # Find the captcha image
                    captcha_img = driver.find_elements("css selector", "#captcha_img, img[src*='captcha']")
                    if captcha_img:
                        img_src = captcha_img[0].get_attribute("src")
                        if img_src:
                            solver = get_captcha_solver()
                            if solver and solver.solver:
                                # Download and solve the image captcha
                                import base64
                                img_data = driver.execute_script("""
                                    var img = arguments[0];
                                    var canvas = document.createElement('canvas');
                                    canvas.width = img.naturalWidth;
                                    canvas.height = img.naturalHeight;
                                    canvas.getContext('2d').drawImage(img, 0, 0);
                                    return canvas.toDataURL('image/png').split(',')[1];
                                """, captcha_img[0])
                                if img_data:
                                    result = solver.solver.normal(img_data, numeric=0, minLen=4, maxLen=8)
                                    code = result.get("code") if isinstance(result, dict) else str(result)
                                    code_input[0].clear()
                                    code_input[0].send_keys(code)
                                    self.logger.info(f"[*] Entered captcha code: {code}")
                                    time.sleep(1)
                    else:
                        self.logger.warning("[!] Could not find captcha image")
            except Exception as e:
                self.logger.warning(f"[!] Image captcha handling failed: {e}")

            # Click submit via JS (two overlapping buttons with same ID)
            try:
                driver.execute_script("""
                    var btns = document.querySelectorAll('#webfilter_search_form_submit');
                    if (btns.length > 0) btns[btns.length - 1].click();
                """)
                self.logger.info("[*] Clicked submit via JS")
            except Exception:
                press_key(driver, url_input, "Enter")
                self.logger.info("[*] Pressed Enter to submit")

            # Wait for results
            self.logger.info("[*] Waiting for results...")
            time.sleep(5)

            body_text = get_text(driver, "body")
            category = self.extract_category(body_text)

            if not return_reputation_only:
                self.logger.success(f"[+] Category: {category}")
            else:
                category = None

            return category

        except Exception as e:
            self.logger.error(f"[-] FortiGuard check failed: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise e


    def extract_category(self, body_text: str) -> str:
        category = "Not Found"

        try:
            lines = body_text.split("\n")

            for i, line in enumerate(lines):
                stripped = line.strip()
                lower = stripped.lower()

                # Look for "Category:" label
                if "category:" in lower:
                    parts = stripped.split(":", 1)
                    if len(parts) > 1 and parts[1].strip():
                        val = parts[1].strip()
                        if val.lower() not in ["", "category"]:
                            category = val
                            break
                    if i + 1 < len(lines) and lines[i + 1].strip():
                        category = lines[i + 1].strip()
                        break

                # FortiGuard result format sometimes shows category directly
                if "web rating" in lower or "web filter" in lower:
                    parts = stripped.split(":", 1)
                    if len(parts) > 1 and parts[1].strip():
                        category = parts[1].strip()
                        break

        except Exception:
            pass

        return category
