import time
from typing import Optional
from urllib.parse import quote
from selenium.webdriver.common.by import By
from helpers.constants import *
from helpers.utils import *
from helpers.logger import *
from helpers.credentials import *


class TalosIntelligence:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = "https://talosintelligence.com/reputation_center/"
        self.tickets_path = "https://talosintelligence.com/tickets"

        # Element selectors for check flow
        self.url_input_sel = "#rep-lookup"
        self.analyze_btn = "/html/body/div/div/div[1]/div/div/div/nav/div[1]/form/button"
        self.cat_res = ".content-category"
        self.rep_res = ".new-legacy-label.capitalize"

        # Element selectors for submit flow (web categorization ticket form)
        self.web_cat_url = "https://talosintelligence.com/reputation_center/web_categorization"
        self.url_textarea = "#cat-textarea"
        self.get_cat_btn = "button.category-data-btn"
        self.cat_selectize = "#webcat-bulk-change-selectized"
        self.comments_textarea = "#webcat_summary_description"
        self.submit_disputes_btn = "#submit_disputes_webcat"

        # Element selectors for login flow (Cisco SAML SSO via id.cisco.com)
        self.saml_login_url = "https://talosintelligence.com/users/auth/saml"
        self.log_in_btn = "a.login-button"
        self.cisco_user = 'input[name="identifier"]'
        self.cisco_pass = 'input[name="credentials.passcode"]'
        self.cisco_submit = ".button-primary"
        self.account_el = "a.login-button"

        self.username = talos_username
        self.password = talos_password


    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Optional[str]:
        self.logger.info(f" Targeting talosintelligence ".center(60, "="))
        self.logger.info(f"[*] Using vendor endpoint at: {self.url}")

        try:
            # Navigate using UC reconnect to bypass Cloudflare
            lookup_url = f"https://talosintelligence.com/reputation_center/lookup?search={quote(target_url, safe='')}"
            driver.uc_open_with_reconnect(lookup_url, reconnect_time=10)
            time.sleep(5)

            # Retry with longer reconnect if Cloudflare challenge persists
            if "just a moment" in driver.title.lower():
                self.logger.debug("[*] Cloudflare challenge, retrying with longer reconnect...")
                driver.uc_open_with_reconnect(lookup_url, reconnect_time=14)
                time.sleep(5)

        except Exception as e:
            self.logger.error(f"[-] Failed during input/submit phase: {e}")
            raise e

        # Extract category
        if not return_reputation_only:
            try:
                wait_for_selector(driver, self.cat_res, timeout=5000)
                category = get_text(driver, self.cat_res)
                self.logger.success(f"[+] Category: {category}")
            except Exception:
                self.logger.error(f"[-] Could not find category for {target_url}")
                category = "UNKNOWN"
        else:
            category = None

        # Extract reputation
        try:
            wait_for_selector(driver, self.rep_res, timeout=10000)
            reputation = get_text(driver, self.rep_res)
            self.logger.success(f"[+] Reputation: {reputation}")
        except Exception:
            self.logger.error(f"[-] Could not find reputation for {target_url}")

        return category


    def check_if_already_logged_in(self, driver) -> bool:
        self.logger.info("[*] Checking if already logged in to Cisco TalosIntelligence")
        try:
            body_text = get_text(driver, "body")
            # If "Sign Out" or "Log Out" appears, user is logged in
            if "sign out" in body_text.lower() or "log out" in body_text.lower():
                self.logger.info("[*] Was already logged in")
                return True
            # If "Login" or "Sign In" link visible, not logged in
            if count_elements(driver, self.log_in_btn) > 0:
                link_text = get_text(driver, self.log_in_btn)
                if "login" in link_text.lower() or "sign in" in link_text.lower():
                    return False
        except Exception:
            pass
        return False


    def log_in(self, driver) -> None:
        # Initiate SAML login flow - redirects to id.cisco.com (Okta)
        load_url_and_wait_until_it_is_fully_loaded(driver, self.saml_login_url)
        time.sleep(3)

        # Wait for Cisco SSO identifier field
        try:
            wait_for_selector(driver, self.cisco_user, state="visible", timeout=15000)
        except Exception:
            # May already be logged in or redirected back
            if "talosintelligence.com" in driver.current_url and "sign_in" not in driver.current_url:
                self.logger.info("[*] Already logged in, redirected back to Talos")
                return
            raise

        # Enter username and proceed
        wait_and_input_on_element(driver, self.cisco_user, self.username)
        wait_and_click_on_element(driver, self.cisco_submit)
        time.sleep(3)

        # Wait for password field (Okta shows it on next step)
        try:
            wait_for_selector(driver, self.cisco_pass, state="visible", timeout=15000)
        except Exception:
            # Try alternate password selector
            alt_pass = 'input[name="password"]'
            wait_for_selector(driver, alt_pass, state="visible", timeout=5000)
            self.cisco_pass = alt_pass

        wait_and_input_on_element(driver, self.cisco_pass, self.password)
        wait_and_click_on_element(driver, self.cisco_submit)

        # Wait for redirect back to talosintelligence.com
        self.logger.info("[*] Cisco SSO login submitted, waiting for redirect...")
        try:
            wait_for_url(driver, lambda u: "talosintelligence.com" in u and "id.cisco.com" not in u, timeout=30000)
        except Exception:
            self.logger.warning("[!] Login redirect timed out - may need MFA approval")

        time.sleep(5)
        self.logger.info("[*] Login complete")


    def login_if_not_logged_in(self, driver) -> None:
        try:
            if not self.check_if_already_logged_in(driver):
                self.log_in(driver)
            else:
                self.logger.info("[*] User logged in successfully")
        except Exception as e:
            self.logger.error(f"[-] Login failed: {str(e)}")


    def submit(self, driver, url: str, email: str, category: str) -> None:
        for protocol_url in prepare_urls_for_submission(url):
            self.submit_single_url(driver, protocol_url, email, category)


    def submit_single_url(self, driver, url: str, email: str, category: str) -> None:
        self.log_in(driver)
        category_result_value = self.check(driver, url)

        if str(category) in str(category_result_value):
            self.logger.info("The proposed category is the same as the one previously found. Returning.")
            return

        self.logger.info("[*] Starting new category submission process on TalosIntelligence")
        vendor_category = categories_map[category]["Talos"]

        # Navigate to the web categorization ticket form
        load_url_and_wait_until_it_is_fully_loaded(driver, self.web_cat_url)
        time.sleep(3)

        # Check if login wall is shown
        body_text = get_text(driver, "body")
        if "you must be logged in" in body_text.lower():
            self.logger.info("[*] Login required, attempting login...")
            self.log_in(driver)
            load_url_and_wait_until_it_is_fully_loaded(driver, self.web_cat_url)
            time.sleep(3)

        try:
            # Enter URL in the dispute textarea
            wait_for_selector(driver, self.url_textarea, state="visible", timeout=10000)
            clear_element(driver, self.url_textarea)
            wait_and_input_on_element(driver, self.url_textarea, url)
            self.logger.info(f"[*] Entered URL: {url}")

            # Click "Get Category Data" to load current categories
            wait_and_click_on_element(driver, self.get_cat_btn)
            time.sleep(5)

            # Select suggested category via selectize.js input
            wait_for_selector(driver, self.cat_selectize, timeout=10000)
            wait_and_click_on_element(driver, self.cat_selectize)
            fill_element(driver, self.cat_selectize, vendor_category)
            time.sleep(2)

            # Click the matching selectize option
            try:
                wait_and_click_on_element(driver, ".selectize-dropdown-content .option", timeout=5000)
                self.logger.info(f"[*] Selected category: {vendor_category}")
            except Exception:
                # Try pressing Enter to confirm selection
                from selenium.webdriver.common.keys import Keys
                driver.find_element(By.CSS_SELECTOR, self.cat_selectize).send_keys(Keys.ENTER)
                self.logger.info(f"[*] Entered category: {vendor_category}")

            # Fill comments
            wait_and_input_on_element(driver, self.comments_textarea, construct_reason_for_review_comment(url, vendor_category))

            # Enable and click submit button
            driver.execute_script(f"document.querySelector('{self.submit_disputes_btn}').disabled = false; document.querySelector('{self.submit_disputes_btn}').classList.remove('disabled');")
            wait_and_click_on_element(driver, self.submit_disputes_btn)
            time.sleep(5)

            body_text = get_text(driver, "body")
            if "thank" in body_text.lower() or "submitted" in body_text.lower() or "ticket" in body_text.lower():
                self.logger.success("[+] Ticket submitted successfully on TalosIntelligence.")
            else:
                self.logger.info("[*] Submission attempted - check TalosIntelligence tickets page for confirmation.")
        except Exception as e:
            self.logger.error(f"[-] Error during ticket submission: {e}")
