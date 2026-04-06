import sys
import os
import time
import traceback
import io
from typing import Optional

# Add classifier root to path so we can import modules
CLASSIFIER_ROOT = os.environ.get("CLASSIFIER_ROOT", "/app/classifier")
if CLASSIFIER_ROOT not in sys.path:
    sys.path.insert(0, CLASSIFIER_ROOT)


def _setup_credentials():
    """Override credential module values from environment variables."""
    try:
        import helpers.credentials as creds
        env_map = {
            "TWOCAPTCHA_API_KEY": "twocaptcha_api_key",
            "VIRUSTOTAL_API_KEY": "virustotal_api_key",
            "ABUSEIPDB_API_KEY": "abuseipdb_api_key",
            "URLHAUS_API_KEY": "urlhaus_api_key",
            "GOOGLE_SAFEBROWSING_API_KEY": "google_safebrowsing_api_key",
            "TALOS_USERNAME": "talos_username",
            "TALOS_PASSWORD": "talos_password",
            "WATCHGUARD_USERNAME": "watchguard_username",
            "WATCHGUARD_PASSWORD": "watchguard_password",
            "PALOALTO_USERNAME": "paloalto_username",
            "PALOALTO_PASSWORD": "paloalto_password",
            "GMAIL_EMAIL": "gmail_email",
            "GMAIL_APP_PASSWORD": "gmail_app_password",
        }
        for env_key, attr_name in env_map.items():
            val = os.environ.get(env_key)
            if val:
                setattr(creds, attr_name, val)
    except ImportError:
        pass


def _get_vendor_class(vendor_name: str):
    """Import and return the vendor class by name."""
    vendor_map = {
        "trendmicro": ("modules.trendmicro", "TrendMicro"),
        "mcafee": ("modules.mcafee", "McAfee"),
        "bluecoat": ("modules.bluecoat", "BlueCoat"),
        "brightcloud": ("modules.brightcloud", "Brightcloud"),
        "paloalto": ("modules.paloalto", "PaloAlto"),
        "zvelo": ("modules.zvelo", "Zvelo"),
        "watchguard": ("modules.watchguard", "Watchguard"),
        "talosintelligence": ("modules.talosintelligence", "TalosIntelligence"),
        "lightspeedsystems": ("modules.lightspeedsystems", "LightspeedSystems"),
        "intelixsophos": ("modules.intelixsophos", "IntelixSophos"),
        "fortiguard": ("modules.fortiguard", "FortiGuard"),
        "checkpoint": ("modules.checkpoint", "CheckPoint"),
        "virustotal": ("modules.virustotal", "VirusTotal"),
        "abusech": ("modules.abusech", "AbuseCH"),
        "abuseipdb": ("modules.abuseipdb", "AbuseIpDB"),
        "googlesafebrowsing": ("modules.google_safebrowsing", "GoogleSafeBrowsing"),
    }

    if vendor_name not in vendor_map:
        raise ValueError(f"Unknown vendor: {vendor_name}")

    module_path, class_name = vendor_map[vendor_name]
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


# Vendors that are API-based (no browser needed)
API_VENDORS = {"virustotal", "abusech", "abuseipdb", "googlesafebrowsing"}


def run_vendor_operation(
    vendor_name: str,
    domain: str,
    action: str,
    email: str = None,
    category: str = None,
) -> dict:
    """
    Run a vendor check/submit operation.
    Returns dict with category, reputation, and/or raw data.
    """
    _setup_credentials()

    VendorClass = _get_vendor_class(vendor_name)
    vendor = VendorClass()

    result = {"vendor": vendor_name, "domain": domain, "action": action}

    if vendor_name in API_VENDORS:
        # API-based vendors: no browser needed, single-arg check(domain)
        import io, logging

        # Capture log output to extract results
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.DEBUG)
        if hasattr(vendor, 'logger') and hasattr(vendor.logger, 'logger'):
            vendor.logger.logger.addHandler(handler)

        try:
            check_result = vendor.check(domain)
        except TypeError:
            check_result = None

        # Extract info from captured logs
        log_output = log_capture.getvalue()
        if hasattr(vendor, 'logger') and hasattr(vendor.logger, 'logger'):
            vendor.logger.logger.removeHandler(handler)

        # Parse log output for results
        result["raw_log"] = log_output
        if "clean" in log_output.lower() or "no threats" in log_output.lower() or "no abuse" in log_output.lower():
            result["reputation"] = "clean"
        elif "flagged" in log_output.lower() or "malicious" in log_output.lower():
            result["reputation"] = "flagged"
        elif "abuse" in log_output.lower():
            result["reputation"] = "suspicious"

        # Try to extract category from return value
        if isinstance(check_result, str):
            result["category"] = check_result
        elif isinstance(check_result, tuple) and len(check_result) > 0:
            result["category"] = str(check_result[0])

        result["status"] = "completed"
        return result

    # Browser-based vendors
    from seleniumbase import Driver
    from helpers.utils import set_captcha_api_key
    from helpers.credentials import twocaptcha_api_key

    set_captcha_api_key(twocaptcha_api_key)

    driver = None
    max_retries = 3

    try:
        driver = Driver(uc=True, headless=True)

        for attempt in range(max_retries):
            try:
                url = domain if domain.startswith(("http://", "https://")) else f"https://{domain}"

                if action == "submit" and hasattr(vendor, "submit"):
                    vendor.submit(driver, domain, email or "", category or "")
                    result["status"] = "submitted"
                else:
                    check_result = vendor.check(driver, url, return_reputation_only=(action == "reputation"))
                    if isinstance(check_result, tuple):
                        result["reputation"] = str(check_result[0]) if check_result[0] else None
                        result["category"] = str(check_result[1]) if len(check_result) > 1 and check_result[1] else None
                    elif check_result:
                        result["category"] = str(check_result)

                result["status"] = "completed"
                return result

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                raise

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return result
