import argparse, os, sys, time, signal, re, traceback
from typing import Optional
from seleniumbase import Driver
from helpers.utils import *
from helpers.logger import *
from helpers.credentials import *
from helpers.constants import *
from modules.trendmicro import *
from modules.bluecoat import *
from modules.talosintelligence import *
from modules.brightcloud import *
from modules.intelixsophos import *
from modules.lightspeedsystems import *
from modules.mcafee import *
from modules.zvelo import *
from modules.watchguard import *
from modules.paloalto import *
from modules.virustotal import *
from modules.abusech import *
from modules.abuseipdb import *


def setup_signalhandlers(cleanup_func=None) -> None:
    def handler(signum, frame):
        try:
            if cleanup_func:
                cleanup_func()
        finally:
            sys.exit(0)

    signal.signal(signal.SIGINT, handler)
    try:
        signal.signal(signal.SIGTERM, handler)
    except Exception:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classifier")
    parser.add_argument("--domain", "-d", metavar="<domain>", dest="domain", required=True, help="Domain to validate")

    check_vendors = ["trendmicro", "mcafee", "lightspeedsystems", "brightcloud", "bluecoat", "paloalto", "zvelo", "watchguard", "talosintelligence"]
    submit_vendors = ["trendmicro", "mcafee", "brightcloud", "bluecoat", "paloalto", "zvelo", "watchguard", "talosintelligence"]
    vendor_choices = ["all"] + check_vendors
    parser.add_argument("--vendor", "-v", metavar="<vendor>", dest="vendor", choices=vendor_choices, default="all", help="Vendor to check: 'all' or use --list-vendors")
    parser.add_argument("--list-vendors", action="store_true", dest="list_vendors", help="List supported vendors and exit")
    parser.add_argument("--headless", action="store_true", help="Use browser in headless mode")

    # Sub-commands for check, reputation, and submit actions
    subparsers = parser.add_subparsers(title="Actions", dest="action", required=True)
    subparsers.add_parser("check", help="Perform check of the current category")
    subparsers.add_parser("reputation", help="Check reputation of domains")
    submit = subparsers.add_parser("submit", help="Submit new category after performing a check")


    def email_type(val: str) -> str:
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", val):
            raise argparse.ArgumentTypeError("The email address is invalid.")
        return val

    submit.add_argument("--email", metavar="<email>", required=True, type=email_type, help="Email address to submit")
    submit.add_argument("--category", metavar="<category>", required=True, choices=available_categories, help="Suggested category")

    args = parser.parse_args()

    # Handle --list-vendors flag
    if getattr(args, "list_vendors", False):
        vendors = submit_vendors if args.action == "submit" else check_vendors
        print("\n".join(vendors))
        sys.exit(0)

    # Validate vendor supports the requested action
    if args.action == "submit" and args.vendor != "all" and args.vendor not in submit_vendors:
        parser.error(f"Vendor '{args.vendor}' does not support submit. Supported vendors: {', '.join(submit_vendors)}")

    set_captcha_api_key(twocaptcha_api_key)
    return args


def check_headless_xvfb(headless: bool) -> None:
    if not headless:
        return

    import shutil
    if shutil.which("xvfb-run") is None:
        print("WARNING: --headless mode requires xvfb. Install it with:")
        print("  sudo apt-get install -y xvfb")
        sys.exit(1)

    # Check if we're already running under xvfb-run
    if os.environ.get("XAUTHORITY", "").startswith("/tmp/xvfb-run"):
        return

    print("WARNING: --headless mode requires xvfb. Please run with:")
    print(f"  xvfb-run --auto-servernum python3 classifier.py {' '.join(sys.argv[1:])}")
    sys.exit(1)


def create_browser(headless: bool, logger: Logger) -> Optional[Driver]:
    try:
        return Driver(uc=True, headless=headless)
    except Exception as e:
        logger.error(f"Failed to create browser: {e}")
        return None


def perform_vendor_operation(args: argparse.Namespace, vendor, driver, max_retries: int = 3) -> bool:
    start = time.time()
    email = getattr(args, "email", "")
    category = getattr(args, "category", "")

    for attempt in range(max_retries):
        try:
            if args.action == "submit":
                vendor.submit(driver, args.domain, email, category)
            else:
                domain = args.domain if args.domain.startswith(("http://", "https://")) else f"https://{args.domain}"
                vendor.check(driver, domain, return_reputation_only=(args.action == "reputation"))

            vendor.logger.info(f"[*] Completed in {time.time() - start:.2f} seconds")
            return True
        except Exception:
            vendor.logger.info(f"[*] Failed after {time.time() - start:.2f} seconds")
            vendor.logger.error(f"Error Traceback:\n{traceback.format_exc()}")

            if attempt < max_retries - 1:
                vendor.logger.error("[!] Caught an exception, retrying...")
            else:
                vendor.logger.info("[*] Max retries reached. Stopping retries.")

    return False


def init_vendors() -> dict:
    classes = [TrendMicro, McAfee, LightspeedSystems, Brightcloud, Zvelo, Watchguard, PaloAlto, BlueCoat, TalosIntelligence]
    instances = [c() for c in classes]
    mapping = {c.__name__.lower(): inst for c, inst in zip(classes, instances)}
    mapping["all"] = instances
    return mapping


def run_vendors(args: argparse.Namespace, vendors: list, logger: Logger) -> None:
    driver = None
    try:
        driver = create_browser(args.headless, logger)
        if not driver:
            logger.error("[-] Browser creation failed")
            return

        for vendor in vendors:
            if args.action == "submit" and not hasattr(vendor, "submit"):
                continue
            perform_vendor_operation(args, vendor, driver)
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def run_reputation_check(args: argparse.Namespace, logger: Logger) -> None:
    domain = args.domain

    # API-based checks (no browser needed)
    VirusTotal().check(domain)
    AbuseCH().check(domain)
    AbuseIpDB().check(domain)


def run_action_check(args: argparse.Namespace, logger: Logger) -> None:
    vendor_map = init_vendors()

    if args.vendor == "all":
        run_vendors(args, vendor_map["all"], logger)
    else:
        v = vendor_map.get(args.vendor)
        if v:
            run_vendors(args, [v], logger)
        else:
            logger.error(f"[-] Invalid vendor: '{args.vendor}'")
            logger.error("[-] Available vendors: " + ", ".join(sorted(k for k in vendor_map.keys() if k != "all")))
            sys.exit(1)


def main() -> None:
    setup_signalhandlers()
    args = parse_args()
    logger = Logger(__name__)

    # Validate headless/xvfb setup before proceeding
    check_headless_xvfb(args.headless)

    if args.action == "reputation":
        run_reputation_check(args, logger)
    else:
        run_action_check(args, logger)


if __name__ == "__main__":
    main()
