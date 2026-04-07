"""
Multi-solver captcha system: 2Captcha → CapSolver → BrightData Web Unlocker.

Strategy per vendor per captcha type:
- Try 2Captcha up to 3 times
- If all 3 fail, switch to CapSolver and try up to 3 times
- BrightData Web Unlocker used as page-level proxy (fetches page with captcha auto-solved)
"""

import time
import json
import base64
import requests
from helpers.logger import Logger

logger = Logger(__name__)


class DualCaptchaSolver:
    def __init__(self, twocaptcha_key: str = "", capsolver_key: str = "", brightdata_key: str = ""):
        self.twocaptcha_key = twocaptcha_key
        self.capsolver_key = capsolver_key
        self.brightdata_key = brightdata_key

    def solve_hcaptcha(self, sitekey: str, page_url: str) -> str | None:
        """Solve hCaptcha. Tries 2Captcha first, falls back to CapSolver."""

        # Try 2Captcha (3 attempts)
        if self.twocaptcha_key:
            for attempt in range(3):
                logger.info(f"[*] hCaptcha: 2Captcha attempt {attempt + 1}/3")
                token = self._twocaptcha_hcaptcha(sitekey, page_url)
                if token:
                    return token
                logger.warning(f"[!] 2Captcha attempt {attempt + 1} failed")

        # Fallback to CapSolver (3 attempts)
        if self.capsolver_key:
            for attempt in range(3):
                logger.info(f"[*] hCaptcha: CapSolver attempt {attempt + 1}/3")
                token = self._capsolver_hcaptcha(sitekey, page_url)
                if token:
                    return token
                logger.warning(f"[!] CapSolver attempt {attempt + 1} failed")

        logger.error("[-] hCaptcha: All solvers exhausted")
        return None

    def solve_recaptcha_v2(self, sitekey: str, page_url: str) -> str | None:
        """Solve reCAPTCHA v2. Tries 2Captcha first, falls back to CapSolver."""

        if self.twocaptcha_key:
            for attempt in range(3):
                logger.info(f"[*] reCAPTCHA v2: 2Captcha attempt {attempt + 1}/3")
                token = self._twocaptcha_recaptcha(sitekey, page_url)
                if token:
                    return token
                logger.warning(f"[!] 2Captcha attempt {attempt + 1} failed")

        if self.capsolver_key:
            for attempt in range(3):
                logger.info(f"[*] reCAPTCHA v2: CapSolver attempt {attempt + 1}/3")
                token = self._capsolver_recaptcha(sitekey, page_url)
                if token:
                    return token
                logger.warning(f"[!] CapSolver attempt {attempt + 1} failed")

        logger.error("[-] reCAPTCHA v2: All solvers exhausted")
        return None

    def solve_image_captcha(self, image_base64: str) -> str | None:
        """Solve image/text captcha. Tries 2Captcha first, falls back to CapSolver."""

        if self.twocaptcha_key:
            for attempt in range(3):
                logger.info(f"[*] Image captcha: 2Captcha attempt {attempt + 1}/3")
                code = self._twocaptcha_image(image_base64)
                if code:
                    return code
                logger.warning(f"[!] 2Captcha attempt {attempt + 1} failed")

        if self.capsolver_key:
            for attempt in range(3):
                logger.info(f"[*] Image captcha: CapSolver attempt {attempt + 1}/3")
                code = self._capsolver_image(image_base64)
                if code:
                    return code
                logger.warning(f"[!] CapSolver attempt {attempt + 1} failed")

        logger.error("[-] Image captcha: All solvers exhausted")
        return None

    # ──── 2Captcha implementations ────

    def _twocaptcha_hcaptcha(self, sitekey: str, page_url: str) -> str | None:
        try:
            r = requests.post("https://2captcha.com/in.php", data={
                "key": self.twocaptcha_key, "method": "hcaptcha",
                "sitekey": sitekey, "pageurl": page_url, "json": 1,
            }, timeout=15)
            resp = r.json()
            if resp.get("status") != 1:
                logger.debug(f"[*] 2Captcha hcaptcha submit failed: {resp}")
                return None
            return self._twocaptcha_poll(resp["request"])
        except Exception as e:
            logger.debug(f"[*] 2Captcha hcaptcha error: {e}")
            return None

    def _twocaptcha_recaptcha(self, sitekey: str, page_url: str) -> str | None:
        try:
            r = requests.post("https://2captcha.com/in.php", data={
                "key": self.twocaptcha_key, "method": "userrecaptcha",
                "googlekey": sitekey, "pageurl": page_url, "json": 1,
            }, timeout=15)
            resp = r.json()
            if resp.get("status") != 1:
                logger.debug(f"[*] 2Captcha recaptcha submit failed: {resp}")
                return None
            return self._twocaptcha_poll(resp["request"])
        except Exception as e:
            logger.debug(f"[*] 2Captcha recaptcha error: {e}")
            return None

    def _twocaptcha_image(self, image_b64: str) -> str | None:
        try:
            r = requests.post("https://2captcha.com/in.php", data={
                "key": self.twocaptcha_key, "method": "base64",
                "body": image_b64, "json": 1,
            }, timeout=15)
            resp = r.json()
            if resp.get("status") != 1:
                logger.debug(f"[*] 2Captcha image submit failed: {resp}")
                return None
            return self._twocaptcha_poll(resp["request"])
        except Exception as e:
            logger.debug(f"[*] 2Captcha image error: {e}")
            return None

    def _twocaptcha_poll(self, task_id: str, timeout: int = 180) -> str | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(5)
            try:
                r = requests.get(f"https://2captcha.com/res.php", params={
                    "key": self.twocaptcha_key, "action": "get",
                    "id": task_id, "json": 1,
                }, timeout=10)
                resp = r.json()
                if resp.get("status") == 1:
                    logger.success(f"[+] 2Captcha solved ({len(resp['request'])} chars)")
                    return resp["request"]
                if "NOT_READY" not in r.text:
                    logger.debug(f"[*] 2Captcha poll error: {resp}")
                    return None
            except Exception:
                pass
        logger.warning("[!] 2Captcha poll timed out")
        return None

    # ──── CapSolver implementations ────

    def _capsolver_hcaptcha(self, sitekey: str, page_url: str) -> str | None:
        return self._capsolver_task({
            "type": "HCaptchaTaskProxyLess",
            "websiteURL": page_url,
            "websiteKey": sitekey,
        })

    def _capsolver_recaptcha(self, sitekey: str, page_url: str) -> str | None:
        return self._capsolver_task({
            "type": "ReCaptchaV2TaskProxyLess",
            "websiteURL": page_url,
            "websiteKey": sitekey,
        })

    def _capsolver_image(self, image_b64: str) -> str | None:
        return self._capsolver_task({
            "type": "ImageToTextTask",
            "body": image_b64,
        })

    def _capsolver_task(self, task: dict, timeout: int = 180) -> str | None:
        try:
            r = requests.post("https://api.capsolver.com/createTask", json={
                "appId": "0E11C799-F498-4E66-B663-29B787B21499",
                "clientKey": self.capsolver_key,
                "task": task,
            }, timeout=15)
            resp = r.json()

            # Some tasks return solution immediately
            if resp.get("solution"):
                token = resp["solution"].get("gRecaptchaResponse") or resp["solution"].get("token") or resp["solution"].get("text")
                if token:
                    logger.success(f"[+] CapSolver instant solve ({len(token)} chars)")
                    return token

            task_id = resp.get("taskId")
            if not task_id:
                logger.debug(f"[*] CapSolver create failed: {resp}")
                return None

            # Poll for result
            deadline = time.time() + timeout
            while time.time() < deadline:
                time.sleep(3)
                r2 = requests.post("https://api.capsolver.com/getTaskResult", json={
                    "clientKey": self.capsolver_key,
                    "taskId": task_id,
                }, timeout=10)
                result = r2.json()
                if result.get("status") == "ready":
                    sol = result.get("solution", {})
                    token = sol.get("gRecaptchaResponse") or sol.get("token") or sol.get("text")
                    if token:
                        logger.success(f"[+] CapSolver solved ({len(token)} chars)")
                        return token
                    logger.debug(f"[*] CapSolver ready but no token: {sol}")
                    return None
                elif result.get("status") != "processing":
                    logger.debug(f"[*] CapSolver poll error: {result}")
                    return None

            logger.warning("[!] CapSolver poll timed out")
            return None
        except Exception as e:
            logger.debug(f"[*] CapSolver error: {e}")
            return None


    # ──── BrightData Web Unlocker ────
    # Fetches a page through BrightData proxy with CAPTCHAs auto-solved
    # Returns the full page HTML, not just a token

    def fetch_page_via_brightdata(self, url: str, zone: str = "captcha_solver", timeout: int = 60) -> str | None:
        """Fetch a URL through BrightData Web Unlocker with auto CAPTCHA solving.
        Returns the page HTML content, or None on failure.

        Requires a Web Unlocker zone to be created in BrightData dashboard.
        The brightdata_key is used as the Bearer token for the REST API.
        """
        if not self.brightdata_key:
            return None

        logger.info(f"[*] BrightData: Fetching {url} via Web Unlocker (zone={zone})...")
        try:
            # Try REST API approach
            r = requests.post(
                "https://api.brightdata.com/request",
                headers={
                    "Authorization": f"Bearer {self.brightdata_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "zone": zone,
                    "url": url,
                    "format": "raw",
                },
                timeout=timeout,
            )
            if r.status_code == 200 and len(r.text) > 500:
                logger.success(f"[+] BrightData: Got page ({len(r.text)} chars)")
                return r.text
            elif r.status_code == 400 and "not found" in r.text.lower():
                logger.warning(f"[!] BrightData: Zone '{zone}' not configured. Create it at brightdata.com/cp")
                return None
            else:
                logger.warning(f"[!] BrightData: HTTP {r.status_code} - {r.text[:100]}")
                return None
        except Exception as e:
            logger.warning(f"[!] BrightData fetch failed: {e}")
            return None

    def fetch_fortiguard_category(self, domain: str) -> str | None:
        """Use BrightData to fetch FortiGuard results directly (bypasses ALTCHA + image captcha)."""
        html = self.fetch_page_via_brightdata(f"https://www.fortiguard.com/webfilter?q={domain}")
        if not html:
            return None
        return self._extract_from_html(html, ["category:"])

    def fetch_sophos_category(self, domain: str) -> str | None:
        """Use BrightData to fetch Sophos Intelix results (bypasses hCaptcha)."""
        # Sophos is a SPA — Web Unlocker may not execute JS
        # Try the direct URL approach
        html = self.fetch_page_via_brightdata(f"https://intelix.sophos.com/url")
        if not html:
            return None
        # SPA won't have results in static HTML — return None to fall back to browser
        return None

    def _extract_from_html(self, html: str, labels: list) -> str | None:
        """Extract a value from HTML by label matching."""
        import re
        text = re.sub(r'<[^>]+>', '\n', html)  # Strip HTML tags
        for line in text.split('\n'):
            stripped = line.strip()
            for label in labels:
                if label in stripped.lower():
                    parts = stripped.split(":", 1)
                    if len(parts) > 1 and parts[1].strip():
                        val = parts[1].strip()
                        if val.lower() not in ["", "category"]:
                            return val
        return None


# Singleton — initialized when first imported
_solver_instance = None

def get_dual_solver() -> DualCaptchaSolver:
    global _solver_instance
    if _solver_instance is None:
        try:
            from helpers.credentials import twocaptcha_api_key, capsolver_api_key
        except ImportError:
            twocaptcha_api_key = ""
            capsolver_api_key = ""
        try:
            from helpers.credentials import brightdata_api_key
        except (ImportError, AttributeError):
            brightdata_api_key = ""
        _solver_instance = DualCaptchaSolver(
            twocaptcha_key=twocaptcha_api_key or "",
            capsolver_key=capsolver_api_key or "",
            brightdata_key=brightdata_api_key or "",
        )
    return _solver_instance
