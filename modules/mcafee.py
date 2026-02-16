import traceback, re, time
from typing import Optional
from helpers.constants import *
from helpers.utils import *
from helpers.logger import *


def log_exception(logger: Logger) -> None:
    trace = traceback.format_exc()
    logger.error(trace)


class McAfee:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = "https://sitelookup.mcafee.com/"
        self.feedback_url = "https://sitelookup.mcafee.com/en/feedback/url"

        # Element selectors for check flow
        self.url_input = "input[name='url']"
        self.submit_btn = "input[type='submit']"
        self.cat_res = ".category"
        self.rep_res = ".reputation"

        # Element selectors for submit flow
        self.cat_select_1 = "select[name='cat_1']"
        self.cat_select_2 = "select[name='cat_2']"
        self.cat_select_3 = "select[name='cat_3']"
        self.comment_input = "textarea[name='comment']"
        self.submit_review_btn = "input[value='Submit URL for Review']"


    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Optional[str]:
        self.logger.info(f" Targeting mcafee ".center(60, "="))
        self.logger.info(f"[*] Using vendor endpoint at: {self.url}")

        try:
            load_url_and_wait_until_it_is_fully_loaded(driver, self.url)
            wait_for_selector(driver, self.url_input, timeout=30000)
            wait_and_input_on_element(driver, self.url_input, target_url)

            # Try multiple submit button selectors
            submit_selectors = [self.submit_btn, "button[type='submit']", "button:has-text('Check')", "a:has-text('Check')"]
            submitted = False

            for selector in submit_selectors:
                if count_elements(driver, selector) > 0:
                    wait_and_click_on_element(driver, selector)
                    submitted = True
                    break

            # Fallback: press Enter if no submit button found
            if not submitted:
                self.logger.debug("[*] No submit found, trying Enter key")
                press_key(driver, self.url_input, "Enter")
                submitted = True

            # Wait for results to load
            if submitted:
                try:
                    wait_for_selector(driver, ".result-container, .reputation, .category, body:has-text('risk')", timeout=10000)
                except Exception:
                    pass
            else:
                raise Exception("Could not find submit mechanism")

            # Parse results from the page body text
            body_text = get_text(driver, "body")
            category = "NOT FOUND"
            reputation = "NOT FOUND"

            if not return_reputation_only:
                category = self.extract_category(body_text, target_url)
                self.logger.success(f"[+] Category: {category.upper()}")
            else:
                category = None

            reputation = self.extract_reputation(body_text)
            self.logger.success(f"[+] Reputation: {reputation.upper()}")

            return category

        except Exception as e:
            self.logger.error(f"[-] McAfee check failed: {str(e)}")
            log_exception(self.logger)
            raise e


    def extract_category(self, body_text: str, target_url: str) -> str:
        category = "NOT FOUND"
        skip_values = {"Categorized URL", "Uncategorized URL", "URL", "Status", "Categorization", "Trust"}
        try:
            lines = body_text.split("\n")

            for line in lines:
                if target_url in line and "Categorized URL" in line:
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        # Tab-separated table row
                        for part in parts:
                            part = part.strip().lstrip("- ").strip()
                            if (part and part not in skip_values
                                    and "://" not in part
                                    and "risk" not in part.lower()):
                                category = part
                                break
                    else:
                        # No tabs — extract text after "Categorized URL"
                        after = line.split("Categorized URL")[-1].strip().lstrip("- ").strip()
                        after = re.split(r'\s+(?:Minimal|Low|Medium|High|Unverified)\s+Risk', after, flags=re.IGNORECASE)[0].strip()
                        if after:
                            category = after.rstrip("- ").strip()

                    if category and category != "NOT FOUND":
                        break

            # Fallback: regex search for "Category:" label
            if category == "NOT FOUND" or category == "":
                cat_match = re.search(r"Category:\s*([^\n\r]+)", body_text, re.IGNORECASE)
                if cat_match:
                    category = cat_match.group(1).strip()
        except Exception as e:
            self.logger.debug(f"[*] Could not extract category: {e}")

        return category


    def extract_reputation(self, body_text: str) -> str:
        reputation = "NOT FOUND"
        try:
            lines = body_text.split("\n")

            for line in lines:
                line_lower = line.lower().strip()
                if "risk" in line_lower:
                    parts = line.split("\t")
                    for part in parts:
                        part = part.strip()
                        if part and part not in ["URL", "Status", "Categorization", "Trust", "-"]:
                            if "risk" in part.lower():
                                reputation = part
                                break
                    if reputation != "NOT FOUND":
                        break
        except Exception as e:
            self.logger.debug(f"[*] Could not extract reputation: {e}")

        return reputation


    def submit(self, driver, url: str, email: str, category: str) -> None:
        for protocol_url in prepare_urls_for_submission(url):
            self.submit_single_url(driver, protocol_url, email, category)


    def submit_single_url(self, driver, url: str, email: str, category: str) -> None:
        try:
            self.logger.info(f" Targeting mcafee ".center(60, "="))
            self.logger.info("[*] Starting submission process on McAfee feedback page")
            load_url_and_wait_until_it_is_fully_loaded(driver, self.feedback_url)

            # Enter URL and check it first
            wait_for_selector(driver, self.url_input, timeout=30000)
            wait_and_input_on_element(driver, self.url_input, url)
            wait_and_click_on_element(driver, "input[value='Check URL']")
            time.sleep(3)

            # Wait for the result table and category dropdowns to appear
            try:
                wait_for_selector(driver, self.cat_select_1, state="visible", timeout=15000)
            except Exception:
                self.logger.warning("[!] Category dropdowns did not appear - check may have failed")
                raise

            # Extract current category from results
            try:
                body_text = get_text(driver, "body")
                current_cat = self.extract_category(body_text, url)
                self.logger.info(f"[*] Current category: {current_cat}")

                if str(category).lower() in str(current_cat).lower():
                    self.logger.info("[*] Proposed category is the same. Returning.")
                    return
            except Exception:
                self.logger.warning("[!] Could not extract current category, proceeding with submission")

            # Select the suggested category from dropdown
            vendor_category = categories_map[category]["McAfee"]
            select_option(driver, self.cat_select_1, label=vendor_category)
            self.logger.info(f"[*] Selected category 1: {vendor_category}")

            # Fill optional comment
            wait_and_input_on_element(driver, self.comment_input, construct_reason_for_review_comment(url, vendor_category, simple_message=True))

            # Click "Submit URL for Review"
            wait_and_click_on_element(driver, self.submit_review_btn)
            time.sleep(3)

            # Check for success
            body_text = get_text(driver, "body")
            if "thank" in body_text.lower() or "submitted" in body_text.lower() or "received" in body_text.lower():
                self.logger.success("[+] Successfully submitted URL for review on McAfee.")
            else:
                self.logger.info("[*] Submission attempted - check page for confirmation.")
        except Exception as e:
            log_exception(self.logger)
            raise e
