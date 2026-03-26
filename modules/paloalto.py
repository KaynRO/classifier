import traceback, time
from typing import Optional
from helpers.constants import *
from helpers.utils import *
from helpers.logger import *
from helpers.credentials import *
from helpers.email_fetcher import fetch_paloalto_verification_code


def log_exception(logger: Logger) -> None:
    trace = traceback.format_exc()
    logger.error(trace)


class PaloAlto:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        try:
            self.username = paloalto_username
            self.password = paloalto_password
        except NameError:
            self.username = ""
            self.password = ""
        self.login_url = "https://identity.paloaltonetworks.com/"
        self.url = "https://urlfiltering.paloaltonetworks.com/"

        # Element selectors for login flow
        self.login_email_input = "input[name='email'], input[type='email'], #email"
        self.login_pass_input = "input[name='password'], input[type='password'], #password"
        self.login_submit_btn = "button[type='submit'], input[type='submit']"
        self.login_next_btn = "button:has-text('Next'), button:has-text('Sign In'), button:has-text('Log In')"

        # Element selectors for check flow
        self.url_input = "id_url"
        self.search_btn = "button[type='submit']"
        self.res_list = "ul.result-list"
        self.cat_el = "li:has-text('Categories: ')"
        self.rep_el = "li:has-text('Risk Level: ')"

        # Element selectors for submit flow (form at /single_cr/ page)
        self.req_btn = "a:has-text('Request Change')"
        self.ack_checkbox = "#acknowledge-checkbox"
        self.ack_close_btn = "#close-modal"
        self.add_cat_btn = "#add_category_btn"
        self.cat_search_input = "#dropdown #searchInput"
        self.cat_hidden_input = "#id_new_category"
        self.email_input = "#id_your_email"
        self.email_conf = "#id_confirm_email"
        self.comment_input = "#id_comment"
        self.submit_btn = "input[type='submit']"


    def login(self, driver) -> None:
        """Login to Palo Alto URL Filtering portal via Okta SSO."""
        if not self.username or not self.password:
            self.logger.debug("[*] No Palo Alto credentials configured, skipping login")
            return

        self.logger.info("[*] Logging in to Palo Alto via Okta SSO...")

        # Navigate directly to the Okta login endpoint
        okta_login_url = "https://urlfiltering.paloaltonetworks.com/oktalogin"
        load_url_and_wait_until_it_is_fully_loaded(driver, okta_login_url)
        time.sleep(3)

        # Okta login form selectors (discovered from test)
        okta_email_input = "input[name='identifier']"
        okta_pass_input = "input[name='credentials.passcode']"
        okta_next_btn = "input[value='Next']"
        okta_submit_btn = "input[type='submit']"

        # Wait for Okta login form
        try:
            wait_for_selector(driver, okta_email_input, state="visible", timeout=20000)
        except Exception:
            # May already be logged in
            if "urlfiltering" in driver.current_url and "oktalogin" not in driver.current_url:
                self.logger.info("[*] Already logged in")
                return
            self.logger.warning("[!] Okta login form not found")
            return

        try:
            # Enter email/username
            wait_and_input_on_element(driver, okta_email_input, self.username)
            self.logger.debug(f"[*] Entered username: {self.username}")
            time.sleep(1)

            # Click Next button (required for Okta multi-step flow)
            try:
                wait_and_click_on_element(driver, okta_next_btn)
                self.logger.debug("[*] Clicked Next button")
                time.sleep(2)
            except Exception as e:
                self.logger.debug(f"[!] Next button click failed: {e}")

            # Wait for password field to appear
            wait_for_selector(driver, okta_pass_input, state="visible", timeout=10000)

            # Enter password
            wait_and_input_on_element(driver, okta_pass_input, self.password)
            self.logger.debug("[*] Entered password")
            time.sleep(1)

            # Submit login
            wait_and_click_on_element(driver, okta_submit_btn)
            self.logger.debug("[*] Okta login submitted, waiting for redirect...")

            # Wait longer for redirect back to URL filtering (SAML can be slow)
            time.sleep(5)
            try:
                wait_for_url(driver, lambda u: "urlfiltering.paloaltonetworks.com" in u, timeout=30000)
                self.logger.info("[*] Login successful - redirected to URL filtering")
            except Exception:
                # Check if we're on SSO page still (might need more time)
                if "sso.paloaltonetworks.com" in driver.current_url:
                    self.logger.debug("[*] Still on SSO page, waiting longer...")
                    time.sleep(10)

            wait_for_load_state(driver, "networkidle")
            time.sleep(3)
            self.logger.info(f"[*] Final URL after login: {driver.current_url}")
        except Exception as e:
            self.logger.warning(f"[!] Okta login attempt failed: {e}")


    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Optional[str]:
        self.logger.info(f" Targeting paloalto ".center(60, "="))
        self.logger.info(f"[*] Using vendor endpoint at: {self.url}")

        self.login(driver)
        load_url_and_wait_until_it_is_fully_loaded(driver, self.url)
        handle_cookie_consent(driver)
        handle_human_verification_checkbox(driver)

        # Wait for page to fully render
        try:
            wait_for_selector(driver, f"#{self.url_input}", timeout=global_wait_time * 1000)
        except Exception as e:
            self.logger.error(f"[-] Failed to find input element: {e}")
            raise

        # Solve reCAPTCHA first (before entering URL to minimize time between solve and submit)
        solve_google_recaptcha(driver)

        # Enter URL and immediately click search to avoid token expiry
        clear_element(driver, f"#{self.url_input}")
        wait_and_input_on_element(driver, f"#{self.url_input}", target_url)
        try:
            wait_and_click_on_element(driver, self.search_btn)
            wait_for_load_state(driver, "networkidle", timeout=30000)
        except Exception as e:
            self.logger.error(f"[-] Failed to click search button: {e}")
            raise

        # Wait for category result to appear
        try:
            wait_for_selector(driver, self.cat_el, state="visible", timeout=10000)
        except Exception:
            self.logger.warning("[!] Results did not appear or timed out")

        # Extract category
        cat_val = "UNKNOWN"
        if not return_reputation_only:
            try:
                raw_cat = get_text(driver, self.cat_el)
                cat_val = raw_cat.replace("Categories: ", "").strip()
                self.logger.success(f"[+] Category: {cat_val}")
            except Exception:
                self.logger.warning("[!] Could not extract category")
        else:
            cat_val = None

        # Extract reputation
        try:
            rep_val = get_text(driver, self.rep_el).replace("Risk Level: ", "").strip()
            self.logger.success(f"[+] Reputation: {rep_val.upper()}")
        except Exception:
            pass

        return cat_val


    def submit(self, driver, url: str, email: str, category: str) -> None:
        for protocol_url in prepare_urls_for_submission(url):
            self.submit_single_url(driver, protocol_url, email, category)


    def submit_single_url(self, driver, url: str, email: str, category: str) -> None:
        try:
            cat_val = self.check(driver, url)

            if str(category).lower() in str(cat_val).lower():
                self.logger.info("[*] Proposed category is the same. Returning.")
                return

            # Click "Request Change" which navigates to /single_cr/ page
            self.logger.info("[*] Starting new category submission process on PaloAlto")
            wait_and_click_on_element(driver, self.req_btn)
            time.sleep(3)

            # Check for "Login Required" modal and handle SSO login with email verification
            login_modal = ".modal"
            login_btns = ["a:has-text('LOGIN')", "a:has-text('Log in')", ".modal a"]

            try:
                if count_elements(driver, login_modal) > 0:
                    modal_text = get_text(driver, login_modal)
                    if "login required" in modal_text.lower():
                        self.logger.info("[*] Login modal detected, clicking LOGIN...")

                        # Click the LOGIN button in modal
                        for login_btn in login_btns:
                            try:
                                if count_elements(driver, login_btn) > 0:
                                    wait_and_click_on_element(driver, login_btn)
                                    break
                            except:
                                pass

                        time.sleep(5)

                        # SSO login is a multi-step flow with email verification
                        self.logger.info("[*] Handling SSO multi-step login...")
                        username_field = "input[type='text']"
                        password_field = "input[type='password']"
                        submit_btn = "input[type='submit']"

                        try:
                            # Step 1: Enter username
                            wait_for_selector(driver, username_field, state="visible", timeout=10000)
                            wait_and_input_on_element(driver, username_field, self.username)
                            self.logger.debug(f"[*] SSO Step 1: Entered username")
                            time.sleep(1)
                            wait_and_click_on_element(driver, submit_btn)
                            time.sleep(3)

                            # Step 2: Enter password
                            wait_for_selector(driver, password_field, state="visible", timeout=10000)
                            wait_and_input_on_element(driver, password_field, self.password)
                            self.logger.debug("[*] SSO Step 2: Entered password")
                            time.sleep(1)
                            wait_and_click_on_element(driver, submit_btn)
                            time.sleep(5)

                            # Step 3: Handle email verification
                            body_text = get_text(driver, "body")
                            if "verification email" in body_text.lower() or "verify with your email" in body_text.lower():
                                self.logger.info("[*] Email verification required - fetching code via IMAP...")

                                # Trigger verification email
                                try:
                                    wait_and_click_on_element(driver, submit_btn)
                                    self.logger.debug("[*] Triggered verification email")
                                except:
                                    pass

                                time.sleep(3)

                                # Fetch verification code from Gmail
                                verification_code = fetch_paloalto_verification_code(
                                    max_wait_seconds=60,
                                    poll_interval=5
                                )

                                if verification_code:
                                    self.logger.success(f"[+] Got verification code: {verification_code}")

                                    # Enter the code
                                    code_input = "input[type='text']"
                                    wait_for_selector(driver, code_input, state="visible", timeout=5000)
                                    wait_and_input_on_element(driver, code_input, verification_code)
                                    time.sleep(1)

                                    # Submit the code
                                    wait_and_click_on_element(driver, submit_btn)
                                    self.logger.info("[*] Submitted verification code, waiting for redirect...")
                                    time.sleep(8)
                                else:
                                    self.logger.error("[!] Failed to get verification code from email")
                                    raise Exception("Email verification failed - could not get code")

                            # Navigate to the change request form
                            form_url = f"https://urlfiltering.paloaltonetworks.com/single_cr/?url={url}"
                            self.logger.info(f"[*] Navigating to change request form...")
                            load_url_and_wait_until_it_is_fully_loaded(driver, form_url)
                            time.sleep(3)

                        except Exception as e:
                            self.logger.warning(f"[!] SSO login failed: {e}")
                            raise
            except Exception as e:
                self.logger.warning(f"[!] Login modal handling failed: {e}")

            # Dismiss the acknowledgement modal if present (old flow)
            try:
                if count_elements(driver, self.ack_checkbox) > 0:
                    wait_and_click_on_element(driver, self.ack_checkbox)
                    time.sleep(1)
                    wait_and_click_on_element(driver, self.ack_close_btn)
                    time.sleep(1)
            except Exception:
                pass

            # Wait for the change request form to load
            # When logged in, email fields may not be present - check for comment field instead
            try:
                wait_for_selector(driver, self.comment_input, state="visible", timeout=15000)
                self.logger.info("[*] Change request form loaded")
            except Exception:
                # Fallback to email input for non-logged-in flow
                wait_for_selector(driver, self.email_input, state="visible", timeout=15000)
                self.logger.info("[*] Change request form loaded (guest mode)")

            # Select category via category picker
            vendor_category = categories_map[category]["PaloAlto"]
            try:
                wait_and_click_on_element(driver, self.add_cat_btn)
                time.sleep(2)

                # Debug: Check what elements are present
                self.logger.debug(f"[*] Looking for category list elements...")
                cate_list_count = count_elements(driver, "#cate_list")
                dropdown_count = count_elements(driver, "#dropdown")
                self.logger.debug(f"[*] #cate_list: {cate_list_count}, #dropdown: {dropdown_count}")

                # Try multiple methods to select the category
                category_selected = False

                # Method 1: jQuery trigger (for guest mode)
                try:
                    result = driver.execute_script(f"""
                        var items = $('#cate_list li.enable').filter(function() {{
                            return $(this).find('.results-title').text().trim() === '{vendor_category}';
                        }});
                        console.log('jQuery found', items.length, 'items for', '{vendor_category}');
                        if (items.length > 0) {{
                            items.trigger('click');
                            return true;
                        }}
                        return false;
                    """)
                    if result:
                        self.logger.debug(f"[*] jQuery method selected category")
                        category_selected = True
                except Exception as e:
                    self.logger.debug(f"[*] jQuery method failed: {e}")

                # Method 2: Direct click via Selenium (for logged-in mode)
                if not category_selected:
                    try:
                        # Find all category items and click the matching one
                        cat_items = driver.find_elements("css selector", "#cate_list li.enable")
                        self.logger.debug(f"[*] Found {len(cat_items)} enabled category items")

                        # Palo Alto uses hyphenated category names (e.g., "Financial-Services")
                        # Try both original and hyphenated versions
                        vendor_category_hyphenated = vendor_category.replace(" ", "-")

                        # Look for items matching or containing the category name
                        matching_items = []
                        for i, item in enumerate(cat_items):
                            try:
                                item_text = item.find_element("css selector", ".results-title").text.strip()
                                # Check for exact match (original or hyphenated)
                                if item_text.lower() == vendor_category.lower() or item_text.lower() == vendor_category_hyphenated.lower():
                                    matching_items.append((i, item, item_text, "exact"))
                                # Check for partial match
                                elif vendor_category.lower() in item_text.lower() or item_text.lower() in vendor_category.lower():
                                    matching_items.append((i, item, item_text, "partial"))
                                elif vendor_category_hyphenated.lower() in item_text.lower() or item_text.lower() in vendor_category_hyphenated.lower():
                                    matching_items.append((i, item, item_text, "partial"))
                            except:
                                pass

                        self.logger.debug(f"[*] Found {len(matching_items)} matching items for '{vendor_category}' (or '{vendor_category_hyphenated}')")

                        if matching_items:
                            # Use the best match (exact match preferred)
                            matching_items.sort(key=lambda x: 0 if x[3] == "exact" else 1)
                            idx, item, item_text, match_type = matching_items[0]

                            self.logger.debug(f"[*] Using {match_type} match: '{item_text}' at index {idx}")
                            item.click()
                            category_selected = True
                        else:
                            self.logger.debug(f"[*] No matches found for '{vendor_category}' or '{vendor_category_hyphenated}'")
                    except Exception as e:
                        self.logger.debug(f"[*] Selenium method failed: {e}")

                # Method 3: Try all li elements (not just .enable)
                if not category_selected:
                    try:
                        all_items = driver.find_elements("css selector", "#cate_list li")
                        self.logger.debug(f"[*] Found {len(all_items)} total category items (incl. disabled)")

                        for i, item in enumerate(all_items):
                            try:
                                item_text = item.text.strip()
                                if vendor_category.lower() in item_text.lower():
                                    self.logger.debug(f"[*] Found matching item at {i}: {item_text}")
                                    item.click()
                                    category_selected = True
                                    break
                            except:
                                pass
                    except Exception as e:
                        self.logger.debug(f"[*] All items method failed: {e}")

                time.sleep(1)

                if category_selected:
                    self.logger.info(f"[*] Selected category: {vendor_category}")

                    # Verify category was actually set in hidden input
                    try:
                        hidden_value = driver.find_element("css selector", self.cat_hidden_input).get_attribute("value")
                        if hidden_value:
                            self.logger.success(f"[+] Category confirmed: {hidden_value}")
                        else:
                            self.logger.warning(f"[!] Category not set in hidden field")
                    except:
                        pass
                else:
                    self.logger.warning(f"[!] Could not select category: {vendor_category}")

            except Exception as e:
                self.logger.warning(f"[!] Could not select category: {e}")
                import traceback
                self.logger.debug(traceback.format_exc())

            # Fill email fields only if present (not needed when logged in)
            try:
                if count_elements(driver, self.email_input) > 0:
                    wait_and_input_on_element(driver, self.email_input, email)
                    wait_and_input_on_element(driver, self.email_conf, email)
            except Exception:
                self.logger.debug("[*] Email fields not present (logged in mode)")

            wait_and_input_on_element(driver, self.comment_input, construct_reason_for_review_comment(url, category))

            solve_google_recaptcha(driver)

            wait_and_click_on_element(driver, self.submit_btn)
            time.sleep(5)

            # Verify submission - check for validation errors or success indicators
            body_text = get_text(driver, "body")
            if "category field is required" in body_text.lower():
                self.logger.warning("[!] Submission failed - category was not selected properly.")
            elif "thank" in body_text.lower() or "received" in body_text.lower() or "change request" not in body_text.lower():
                self.logger.success("[+] Submission successful - you will receive an email confirmation.")
            else:
                self.logger.info("[*] Submission attempted - check email for confirmation.")
        except Exception as e:
            log_exception(self.logger)
            raise e
