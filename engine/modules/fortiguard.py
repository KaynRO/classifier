import os, time, base64, traceback
from typing import Optional
from helpers.constants import *
from helpers.utils import *
from helpers.logger import *
from helpers.captcha_dual_solver import get_dual_solver


SBR_WS = os.environ.get(
    "BRIGHTDATA_BROWSER_WS",
    "wss://brd-customer-hl_f2aa9202-zone-browser:v6hzqppm9838@brd.superproxy.io:9222",
)
TARGET_URL = "https://www.fortiguard.com/webfilter"


def ocr_captcha(image_path: str, logger: Logger) -> Optional[str]:
    # Multi-strategy preprocessing: threshold sweep across R/G/B/L channels,
    # then majority-vote the Tesseract results.
    try:
        import pytesseract
        from PIL import Image, ImageFilter, ImageEnhance
        import numpy as np
        from collections import Counter
    except ImportError as e:
        logger.error(f"[-] Missing OCR dependencies: {e}")
        return None

    try:
        img = Image.open(image_path).convert("RGB")
    except Exception as e:
        logger.error(f"[-] Cannot open captcha image: {e}")
        return None

    results = []
    whitelist = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"

    # Strategy 1: Per-channel thresholding
    r, g, b = img.split()
    for channel in [r, g, b, img.convert("L")]:
        enhanced = ImageEnhance.Contrast(channel).enhance(5.0)
        for thresh in [80, 100, 120, 140, 160]:
            binary = enhanced.point(lambda x: 0 if x < thresh else 255)
            scaled = binary.resize((binary.width * 3, binary.height * 3), Image.NEAREST)
            for psm in [7, 8, 13, 6]:
                cfg = f"--psm {psm} -c tessedit_char_whitelist={whitelist}"
                try:
                    text = pytesseract.image_to_string(scaled, config=cfg).strip()
                    text = text.replace(" ", "").replace("\n", "")
                    if 3 <= len(text) <= 8:
                        results.append(text)
                except Exception:
                    pass

    # Strategy 2: Saturation-based text isolation
    try:
        arr = np.array(img)
        max_c = arr.max(axis=2)
        min_c = arr.min(axis=2)
        saturation = max_c.astype(int) - min_c.astype(int)
        brightness = arr.mean(axis=2)
        text_mask = ((saturation > 30) & (brightness < 200)).astype(np.uint8) * 255
        mask_img = Image.fromarray(text_mask).filter(ImageFilter.MaxFilter(3))
        mask_scaled = mask_img.resize((mask_img.width * 3, mask_img.height * 3), Image.NEAREST)
        for psm in [7, 8, 13, 6]:
            cfg = f"--psm {psm} -c tessedit_char_whitelist={whitelist}"
            try:
                text = pytesseract.image_to_string(mask_scaled, config=cfg).strip()
                text = text.replace(" ", "").replace("\n", "")
                if 3 <= len(text) <= 8:
                    results.append(text)
            except Exception:
                pass
    except Exception:
        pass

    if results:
        counter = Counter(results)
        best = counter.most_common(1)[0][0]
        logger.debug(f"[*] OCR candidates: {counter.most_common(5)}")
        return best.upper()
    return None


def _solve_captcha_with_chain(captcha_path: str, logger: Logger) -> Optional[str]:
    # Provider chain: 2Captcha → CapSolver → local Tesseract OCR.
    try:
        with open(captcha_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        logger.error(f"[-] Cannot read captcha file: {e}")
        return None

    solver = get_dual_solver()
    code = solver.solve_image_captcha(img_b64)
    if code:
        logger.success(f"[+] Captcha solved via cloud: {code}")
        return code

    # Priority 3: local Tesseract OCR as last resort
    logger.info("[*] Cloud solvers exhausted, falling back to local OCR")
    return ocr_captcha(captcha_path, logger)


def _extract_captcha_image(page) -> Optional[str]:
    img_src = page.evaluate("""() => {
        const cw = document.querySelector('captcha-widget, #captcha_widget');
        if (!cw || !cw.shadowRoot) return null;
        const img = cw.shadowRoot.querySelector('img');
        if (!img) return null;
        return img.src;
    }""")
    if img_src and img_src.startswith("data:image"):
        b64_data = img_src.split(",")[1]
        path = "/tmp/fortiguard_captcha.png"
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64_data))
        return path
    return None


def _enter_captcha_and_submit(page, code: str) -> str:
    return page.evaluate("""(code) => {
        const cw = document.querySelector('captcha-widget, #captcha_widget');
        if (!cw || !cw.shadowRoot) return 'no shadow root';
        const input = cw.shadowRoot.querySelector('.captcha-input, input[type="text"], input:not([type="hidden"])');
        if (!input) return 'no input found';
        input.value = '';
        input.focus();
        input.value = code;
        input.dispatchEvent(new Event('input', {bubbles: true}));
        input.dispatchEvent(new Event('change', {bubbles: true}));
        const hiddenCode = document.querySelector('#captcha_code');
        if (hiddenCode) hiddenCode.value = code;
        const buttons = cw.shadowRoot.querySelectorAll('button');
        for (const btn of buttons) {
            if (btn.textContent.toLowerCase().includes('submit') || btn.classList.contains('captcha-submit')) {
                btn.click();
                return 'submitted: ' + code;
            }
        }
        if (buttons.length > 0) { buttons[buttons.length - 1].click(); return 'submitted (last): ' + code; }
        return 'no submit button';
    }""", code)


def _extract_category(body_text: str) -> str:
    # Returns "Category | Risk Level" when both are present, just the category otherwise.
    category = None
    risk_level = None

    lines = body_text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        lower = stripped.lower()

        # Extract Category
        if category is None and (lower.startswith("category:") or lower.startswith("category :")):
            val = stripped.split(":", 1)[1].strip()
            if val and val.lower() not in ["", "category"]:
                category = val

        # Extract Risk Level
        if risk_level is None and (lower.startswith("risk level:") or lower.startswith("risk level :")):
            val = stripped.split(":", 1)[1].strip()
            if val and val.lower() not in ["", "risk level"]:
                risk_level = val

    # Fallback: Newly Registered Domain
    if not category and "newly registered" in body_text.lower():
        category = "Newly Registered Domain"

    if not category:
        return "Not Found"

    if risk_level:
        return f"{category} | {risk_level}"
    return category


def _fill_form(page, domain: str, logger: Logger) -> bool:
    url_input = page.query_selector('input[name="url"]')
    if not url_input:
        logger.error("[-] URL input not found")
        return False
    url_input.click()
    url_input.fill(domain)
    logger.info(f"[*] Entered domain: {domain}")

    altcha = page.query_selector('input[id*="altcha_checkbox"]')
    if altcha:
        altcha.click(force=True)
        logger.info("[*] Clicked ALTCHA checkbox")

    # Wait up to 30s for ALTCHA proof-of-work
    for i in range(30):
        time.sleep(1)
        plen = page.evaluate('() => { const h = document.querySelector(\'input[name="altcha"]\'); return h ? h.value.length : 0; }')
        if plen > 10:
            logger.info(f"[*] ALTCHA verified after {i+1}s")
            return True
    logger.warning("[!] ALTCHA did not verify in 30s")
    return False


class FortiGuard:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = TARGET_URL

    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Optional[str]:
        # driver is ignored — we use Playwright + BrightData Scraping Browser.
        self.logger.info(f" Targeting fortiguard ".center(60, "="))
        self.logger.info(f"[*] Using BrightData Scraping Browser")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.logger.error("[-] playwright not installed")
            return "Playwright Missing"

        clean_domain = target_url.replace("https://", "").replace("http://", "").strip("/")

        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(SBR_WS)
                page = browser.new_page()
                page.set_default_timeout(60000)

                self.logger.info(f"[*] Navigating to {self.url}")
                page.goto(self.url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(4)

                if not _fill_form(page, clean_domain, self.logger):
                    browser.close()
                    return "ALTCHA Failed"

                # First submit — triggers image captcha
                page.evaluate('() => { var b = document.querySelectorAll("#webfilter_search_form_submit"); if(b.length>0) b[b.length-1].click(); }')
                self.logger.info("[*] First submit clicked")
                time.sleep(4)

                # Quick check — maybe results appeared immediately
                body = page.inner_text("body")
                if "category:" in body.lower():
                    category = _extract_category(body)
                    self.logger.success(f"[+] Category: {category}")
                    browser.close()
                    return category

                # Captcha solving loop — 3 attempts
                for attempt in range(1, 6):
                    self.logger.info(f"[*] Captcha attempt {attempt}/5")

                    # If on failure page, restart
                    body = page.inner_text("body")
                    if "security check failed" in body.lower():
                        self.logger.info("[*] On failure page, restarting...")
                        page.goto(self.url, wait_until="domcontentloaded", timeout=60000)
                        time.sleep(4)
                        if not _fill_form(page, clean_domain, self.logger):
                            continue
                        page.evaluate('() => { var b = document.querySelectorAll("#webfilter_search_form_submit"); if(b.length>0) b[b.length-1].click(); }')
                        time.sleep(4)

                    captcha_path = _extract_captcha_image(page)
                    if not captcha_path:
                        self.logger.warning("[!] No captcha image found")
                        continue

                    code = _solve_captcha_with_chain(captcha_path, self.logger)
                    if not code:
                        self.logger.warning("[!] All solvers failed")
                        continue

                    _enter_captcha_and_submit(page, code)
                    time.sleep(5)

                    body = page.inner_text("body")
                    if "category:" in body.lower():
                        category = _extract_category(body)
                        self.logger.success(f"[+] Category: {category}")
                        browser.close()
                        return category
                    elif "security check failed" in body.lower():
                        self.logger.warning(f"[!] Wrong captcha code on attempt {attempt}")
                    else:
                        self.logger.debug(f"[*] Unknown state after attempt {attempt}")

                browser.close()
                self.logger.error("[-] All captcha attempts failed")
                return "Captcha Failed"

        except Exception as e:
            self.logger.error(f"[-] FortiGuard check failed: {e}")
            self.logger.error(traceback.format_exc())
            return "Error"

    def _fill_submit_form(self, page, clean_url: str, vendor_category: str, email: str, reason: str) -> bool:
        # Fill the submit form and run ALTCHA proof-of-work.
        # Returns True if ALTCHA verified within 60s.
        try:
            page.evaluate('document.querySelector("altcha-widget")?.scrollIntoView()')
            time.sleep(2)

            page.fill("#web_filter_rating_info_form_url", clean_url)
            self.logger.info(f"[*] Entered URL: {clean_url}")

            page.select_option("#web_filter_rating_info_form_categorysuggestion", label=vendor_category)
            self.logger.info(f"[*] Selected category: {vendor_category}")

            page.fill("#web_filter_rating_info_form_name", "URL Classifier")
            page.fill("#web_filter_rating_info_form_email", email or "admin@example.com")
            page.fill("#web_filter_rating_info_form_companyname", "URL Classifier")
            page.fill("#web_filter_rating_info_form_comment", reason)
            self.logger.info("[*] Filled contact fields")
        except Exception as e:
            self.logger.error(f"[-] Form fill failed: {e}")
            return False

        try:
            altcha = page.query_selector("altcha-widget")
            if altcha:
                box = altcha.bounding_box()
                if box:
                    page.mouse.click(box["x"] + 20, box["y"] + box["height"] / 2)
                    self.logger.info("[*] Clicked ALTCHA widget")
        except Exception as e:
            self.logger.debug(f"[*] ALTCHA click failed: {e}")

        self.logger.info("[*] Waiting for ALTCHA proof-of-work...")
        for i in range(60):
            time.sleep(1)
            state = page.evaluate(
                '() => { const w = document.querySelector("altcha-widget"); if(!w) return null; const m = w.outerHTML.match(/data-state="([^"]+)"/); return m ? m[1] : null; }'
            )
            if state == "verified":
                self.logger.success(f"[+] ALTCHA verified after {i+1}s")
                return True
        self.logger.warning("[!] ALTCHA did not verify in 60s")
        return False


    def submit(self, driver, url: str, email: str, category: str) -> None:
        # Submit URL recategorization request via FortiGuard's form.
        # Retries up to 5 times (matching the check flow): each attempt re-navigates,
        # re-fills the form, re-runs ALTCHA PoW, and drives the image-captcha loop.
        self.logger.info(f" Targeting fortiguard (submit) ".center(60, "="))

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise Exception("playwright not installed")

        submit_url = "https://www.fortiguard.com/faq/wfratingsubmit"
        clean_url = url if url.startswith(("http://", "https://")) else f"https://{url}"
        vendor_category = categories_map.get(category, {}).get("FortiGuard", category)
        reason = construct_reason_for_review_comment(clean_url, vendor_category, simple_message=True)

        success_markers = ("success", "thank", "received", "submitted")
        last_error: Optional[str] = None

        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(SBR_WS)

                for attempt in range(1, 6):
                    self.logger.info(f"[*] Submit attempt {attempt}/5")
                    page = browser.new_page()
                    page.set_default_timeout(60000)

                    try:
                        self.logger.info(f"[*] Navigating to {submit_url}")
                        page.goto(submit_url, wait_until="domcontentloaded", timeout=60000)
                        time.sleep(8)

                        if not self._fill_submit_form(page, clean_url, vendor_category, email, reason):
                            last_error = "ALTCHA/form setup failed"
                            continue

                        try:
                            page.click("#web_filter_rating_info_form_submit")
                            self.logger.info("[*] Clicked submit (will trigger image captcha)")
                            time.sleep(5)
                        except Exception as e:
                            last_error = f"Submit click failed: {e}"
                            self.logger.error(f"[-] {last_error}")
                            continue

                        # Immediate confirmation (no captcha shown)
                        body = page.inner_text("body").lower()
                        if any(m in body for m in success_markers) and "security check" not in body:
                            self.logger.success(f"[+] FortiGuard submission accepted (attempt {attempt})")
                            browser.close()
                            return

                        # Drive the image-captcha loop (up to 5 sub-attempts per outer attempt)
                        for cap_attempt in range(1, 6):
                            self.logger.info(f"[*] Image captcha sub-attempt {cap_attempt}/5")
                            captcha_path = _extract_captcha_image(page)
                            if not captcha_path:
                                body = page.inner_text("body").lower()
                                if any(m in body for m in success_markers) and "security check" not in body:
                                    self.logger.success(f"[+] FortiGuard submission accepted (attempt {attempt})")
                                    browser.close()
                                    return
                                self.logger.warning("[!] No captcha image and no confirmation — retrying")
                                break

                            code = _solve_captcha_with_chain(captcha_path, self.logger)
                            if not code:
                                self.logger.warning("[!] All solvers failed, refreshing captcha")
                                continue

                            _enter_captcha_and_submit(page, code)
                            time.sleep(5)

                            body = page.inner_text("body").lower()
                            if any(m in body for m in success_markers) and "security check" not in body:
                                self.logger.success(f"[+] FortiGuard submission accepted (attempt {attempt})")
                                browser.close()
                                return
                            if "security check failed" in body:
                                self.logger.warning(f"[!] Security check failed on sub-attempt {cap_attempt}")
                                last_error = "Security check failed"
                                break

                        last_error = last_error or "No confirmation received"

                    except Exception as e:
                        last_error = str(e)
                        self.logger.warning(f"[!] Attempt {attempt} errored: {e}")
                    finally:
                        try:
                            page.close()
                        except Exception:
                            pass

                browser.close()

        except Exception as e:
            self.logger.error(f"[-] FortiGuard submit failed: {e}")
            raise

        raise Exception(f"FortiGuard submit failed after 5 attempts: {last_error or 'no confirmation'}")
