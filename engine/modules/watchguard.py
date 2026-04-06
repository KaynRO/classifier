import traceback, time
from helpers.constants import *
from helpers.utils import *
from helpers.logger import *
from helpers.credentials import *


def log_exception(logger: Logger) -> None:
    trace = traceback.format_exc()
    logger.error(trace)


class Watchguard:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.username = watchguard_username
        self.password = watchguard_password
        self.login_page = "https://usermanager.watchguard.com/"
        self.url = "https://securityportal.watchguard.com/UrlCategory"

        # Element selectors for login flow (Azure AD B2C)
        self.user_field = "#signInName"
        self.pass_field = "#password"
        self.login_btn = "#continue"

        # Element selectors for check flow
        self.url_input = "#urlList"
        self.search_btn = "#searchUrlCategories"
        self.results_div = "#resultsDiv"

        # Element selectors for submit flow
        self.comment_field = "#suggestionList"
        self.sub_btn = "#submitSuggestions"
        self.success_msg = "#submitConfirm"


    def login(self, driver) -> None:
        # Skip login if already on the security portal
        current_url = driver.current_url or ""
        if "securityportal.watchguard.com" in current_url:
            self.logger.debug("[*] Already on security portal, skipping login")
            return

        load_url_and_wait_until_it_is_fully_loaded(driver, self.login_page)
        time.sleep(3)

        # Wait for the Azure AD B2C login form to render
        try:
            wait_for_selector(driver, self.user_field, state="visible", timeout=15000)
        except Exception:
            # May already be logged in or redirected
            if "securityportal" in driver.current_url:
                self.logger.debug("[*] Already logged in, redirected to portal")
                return
            raise

        wait_and_input_on_element(driver, self.user_field, self.username)
        wait_and_input_on_element(driver, self.pass_field, self.password)
        wait_and_click_on_element(driver, self.login_btn)

        # Wait for redirect from login page to security portal
        self.logger.debug("[*] Waiting for login to complete...")
        try:
            wait_for_url(driver, lambda u: "securityportal" in u, timeout=30000)
            self.logger.debug("[*] Login redirect detected, waiting 5s for session stabilization...")
        except Exception:
            self.logger.debug("[!] Login redirect wait timed out, proceeding anyway")

        wait_for_load_state(driver, "networkidle")
        time.sleep(5)


    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> str:
        self.logger.info(f" Targeting watchguard ".center(60, "="))
        self.logger.info(f"[*] Using vendor endpoint at: {self.url}")

        self.login(driver)
        load_url_and_wait_until_it_is_fully_loaded(driver, self.url)
        handle_cookie_consent(driver)
        handle_human_verification_checkbox(driver)

        # Enter URL, solve CAPTCHA, and submit
        wait_for_selector(driver, self.url_input, state="visible", timeout=15000)
        clear_element(driver, self.url_input)
        wait_and_input_on_element(driver, self.url_input, target_url)
        solve_google_recaptcha(driver)
        handle_cookie_consent(driver)
        wait_and_click_on_element(driver, self.search_btn)

        # Wait for results to appear
        try:
            wait_for_selector(driver, self.results_div, state="visible", timeout=15000)
            time.sleep(2)
        except Exception as e:
            self.logger.error(f"[-] Result container did not appear: {str(e)}")

        # Extract category from results div text (format: "URL is categorized as <category>")
        results_text = get_text(driver, self.results_div)
        cat_val = "UNKNOWN"
        if "categorized as" in results_text.lower():
            cat_val = results_text.split("categorized as")[-1].strip().rstrip(".")
        elif "not categorized" in results_text.lower():
            cat_val = "NONE"

        self.logger.success(f"[+] Category: {cat_val.upper()}")
        return cat_val


    def submit(self, driver, url: str, email: str, category: str) -> None:
        for protocol_url in prepare_urls_for_submission(url):
            self.submit_single_url(driver, protocol_url, email, category)


    def submit_single_url(self, driver, url: str, email: str, category: str) -> None:
        cat_val = self.check(driver, url)

        if str(category) in str(cat_val):
            self.logger.info("The proposed category is the same as the one previously found. Returning.")
            return

        self.logger.info("[*] Starting new category submission process on Watchguard")

        # Fill suggestion and solve second CAPTCHA
        wait_for_selector(driver, self.comment_field, state="visible", timeout=10000)
        wait_and_input_on_element(driver, self.comment_field, f"{url}, {category}")
        solve_google_recaptcha(driver)
        handle_cookie_consent(driver)

        # Submit and verify confirmation
        try:
            wait_and_click_on_element(driver, self.sub_btn)
            wait_for_selector(driver, self.success_msg, state="visible", timeout=15000)
            conf = get_text(driver, self.success_msg)

            if "thank you" in conf.lower() or "submission" in conf.lower():
                self.logger.success("[+] Successfully submitted for review. The category is typically updated within 24 to 48 hours.")
            else:
                self.logger.info(f"[*] Something went wrong with the reclassification request. Response: {conf}")
        except Exception as e:
            self.logger.error(f"[-] An error occurred during the submission process: {str(e)}")
