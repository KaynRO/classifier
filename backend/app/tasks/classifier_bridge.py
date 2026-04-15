import sys, os, time, traceback, io
from typing import Optional

# Add classifier root to path so we can import modules
CLASSIFIER_ROOT = os.environ.get("CLASSIFIER_ROOT", "/app/classifier")
if CLASSIFIER_ROOT not in sys.path:
    sys.path.insert(0, CLASSIFIER_ROOT)


def load_db_config() -> dict:
    try:
        import psycopg2
        db_url = os.environ.get("DATABASE_URL_SYNC", "")
        if not db_url:
            return {}
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM app_config WHERE value IS NOT NULL AND value != ''")
        result = {row[0]: row[1] for row in cur.fetchall()}
        cur.close()
        conn.close()
        return result
    except Exception:
        return {}


def setup_credentials() -> None:
    try:
        import helpers.credentials as creds

        db_config = load_db_config()

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
            "CAPSOLVER_API_KEY": "capsolver_api_key",
            "BRIGHTDATA_API_KEY": "brightdata_api_key",
            "BRIGHTDATA_BROWSER_WS": "brightdata_browser_ws",
            "CHECKPOINT_USERNAME": "checkpoint_username",
            "CHECKPOINT_PASSWORD": "checkpoint_password",
            "CHECKPOINT_TOTP_SECRET": "checkpoint_totp_secret",
        }
        for env_key, attr_name in env_map.items():
            val = db_config.get(attr_name) or os.environ.get(env_key)
            if val:
                setattr(creds, attr_name, val)
        # Reset dual solver singleton so it picks up updated keys
        try:
            import helpers.captcha_dual_solver as ds
            ds._solver_instance = None
        except ImportError:
            pass
    except ImportError:
        pass


def get_vendor_class(vendor_name: str):

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
        "intelixsophos": ("modules.intelixsophos", "Intelixsophos"),
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

# Vendors that use Playwright + BrightData (no local driver needed)
PLAYWRIGHT_VENDORS = {"intelixsophos", "fortiguard"}


def run_vendor_operation(
    vendor_name: str,
    domain: str,
    action: str,
    email: str = None,
    category: str = None,
) -> dict:
    setup_credentials()
    os.makedirs("logs", exist_ok=True)

    VendorClass = get_vendor_class(vendor_name)
    vendor = VendorClass()

    result = {"vendor": vendor_name, "domain": domain, "action": action}

    if vendor_name in API_VENDORS:
        import io, logging
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.DEBUG)
        if hasattr(vendor, 'logger') and hasattr(vendor.logger, 'logger'):
            vendor.logger.logger.addHandler(handler)

        try:
            check_result = vendor.check(domain)
        except TypeError:
            check_result = None

        log_output = log_capture.getvalue()
        if hasattr(vendor, 'logger') and hasattr(vendor.logger, 'logger'):
            vendor.logger.logger.removeHandler(handler)

        result["raw_log"] = log_output

        aggregate: Optional[str] = None
        if isinstance(check_result, str) and check_result:
            aggregate = check_result
        elif isinstance(check_result, tuple) and len(check_result) > 0:
            aggregate = str(check_result[0])

        if aggregate:
            # Reputation vendors populate the `reputation` column; `category` stays empty
            # because a reputation vendor has no content category.
            result["reputation"] = aggregate
            first = aggregate.split()[0].lower().rstrip("(:,")
            if first.startswith("error"):
                result["status"] = "failed"
                result["error"] = aggregate
                return result

        result["status"] = "completed"
        return result

    # Playwright + BrightData vendors (no local driver needed)
    if vendor_name in PLAYWRIGHT_VENDORS:
        try:
            url = domain if domain.startswith(("http://", "https://")) else f"https://{domain}"
            if action == "submit" and hasattr(vendor, "submit"):
                vendor.submit(None, domain, email or "", category or "")
                result["status"] = "submitted"
            else:
                check_result = vendor.check(None, url, return_reputation_only=(action == "reputation"))
                if isinstance(check_result, str) and check_result:
                    result["category"] = check_result
                elif isinstance(check_result, tuple):
                    result["reputation"] = str(check_result[0]) if check_result[0] else None
                    result["category"] = str(check_result[1]) if len(check_result) > 1 and check_result[1] else None
            result["status"] = "completed"
            return result
        except Exception as e:
            result["error"] = str(e)
            result["status"] = "failed"
            raise

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
