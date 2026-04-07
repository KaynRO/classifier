import traceback, time, re
from typing import Optional
from helpers.constants import *
from helpers.utils import *
from helpers.logger import *
from helpers.captcha_dual_solver import get_dual_solver


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

            # First submit — triggers the image captcha to appear
            try:
                driver.execute_script("""
                    var btns = document.querySelectorAll('#webfilter_search_form_submit');
                    if (btns.length > 0) btns[btns.length - 1].click();
                """)
                self.logger.info("[*] First submit clicked — checking for image captcha...")
            except Exception:
                press_key(driver, url_input, "Enter")

            time.sleep(4)

            # Check if image captcha appeared after submit
            body_after_submit = get_text(driver, "body")
            code_input = driver.find_elements("css selector", "input[name='code'], input#captcha_code")
            code_visible = any(c.is_displayed() for c in code_input) if code_input else False

            if "enter the code" in body_after_submit.lower() or code_visible:
                self.logger.info("[*] Image captcha appeared — solving...")

                # Screenshot the captcha widget element (it's not a regular <img>)
                import base64
                widget = driver.find_elements("css selector", "#captcha_widget, .captcha-widget")
                img_data = None
                if widget and widget[0].is_displayed():
                    try:
                        png_bytes = widget[0].screenshot_as_png
                        img_data = base64.b64encode(png_bytes).decode()
                        self.logger.info(f"[*] Captured captcha widget screenshot ({len(img_data)} b64 bytes)")
                    except Exception as e:
                        self.logger.warning(f"[!] Widget screenshot failed: {e}")

                if img_data:
                    solver = get_dual_solver()
                    code = solver.solve_image_captcha(img_data)
                    if code:
                        # Make the code input visible and enter the code
                        driver.execute_script("""
                            var el = document.querySelector('input[name="code"], input#captcha_code');
                            if (el) { el.type = 'text'; el.style.display = 'block'; }
                        """)
                        time.sleep(0.5)
                        code_els = driver.find_elements("css selector", "input[name='code'], input#captcha_code")
                        for c in code_els:
                            try:
                                c.clear()
                                driver.execute_script("arguments[0].value = arguments[1]", c, code)
                                self.logger.info(f"[*] Entered captcha code: {code}")
                                break
                            except Exception:
                                continue
                        time.sleep(1)

                        # Submit again with the code
                        driver.execute_script("""
                            var btns = document.querySelectorAll('#webfilter_search_form_submit');
                            if (btns.length > 0) btns[btns.length - 1].click();
                        """)
                        self.logger.info("[*] Second submit with captcha code")
                    else:
                        self.logger.warning("[!] Image captcha could not be solved")
                else:
                    self.logger.warning("[!] Could not capture captcha widget")
            else:
                self.logger.info("[*] No image captcha detected — checking for results...")

            # Wait for results
            self.logger.info("[*] Waiting for results...")
            time.sleep(5)

            body_text = get_text(driver, "body")

            # Debug: log lines containing "category" or "rated"
            for line in body_text.split("\n"):
                if "category" in line.lower() or "rated" in line.lower() or "risk" in line.lower():
                    self.logger.debug(f"[*] Page line: {line.strip()[:120]}")

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

                # Match "Category: <value>" anywhere in the text
                if lower.startswith("category:") or lower.startswith("category :"):
                    val = stripped.split(":", 1)[1].strip()
                    if val and val.lower() not in ["", "category"]:
                        category = val
                        break
                    if i + 1 < len(lines) and lines[i + 1].strip():
                        category = lines[i + 1].strip()
                        break

                # Also check for "Newly Registered Domain" or similar in history
                if "newly registered" in lower:
                    category = "Newly Registered Domain"
                    break
                if "risk level:" in lower:
                    val = stripped.split(":", 1)[1].strip()
                    if val and category == "Not Found":
                        # Use risk level as supplementary info
                        self.logger.info(f"[*] Risk Level: {val}")

        except Exception:
            pass

        return category
