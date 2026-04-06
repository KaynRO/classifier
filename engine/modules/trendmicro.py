import traceback
from typing import Optional, Tuple
from helpers.constants import *
from helpers.utils import *
from helpers.logger import *


def log_exception(logger: Logger) -> None:
    trace = traceback.format_exc()
    logger.error(trace)


class TrendMicro:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = "https://global.sitesafety.trendmicro.com"

        # Element selectors for the check flow
        self.url_input = "/html/body/main/div/section/div/div/section[1]/div/div[1]/form/input[1]"
        self.submit_btn = "/html/body/main/div/section/div/div/section[1]/div/div[1]/form/input[2]"
        self.safety_res = "/html/body/main/div/section/div/div/section[1]/div/div[5]/div[2]/div/div[2]/div"
        self.cat_res = "/html/body/main/div/section/div/div/section[1]/div/div[6]/div[2]/div/div[2]/div"

        # Element selectors for the submit flow
        self.reclass_btn = "/html/body/main/div/section/div/div/section[1]/div/div[7]/a"
        self.proceed_btn = "/html/body/main/div/section/div/div/section[3]/div/div/div[2]/div/div[2]/div"
        self.diff_cat_radio = "/html/body/main/div/section/div/div/div/div/form/section[2]/div[4]/span"
        self.diff_cat_input = "/html/body/main/div/section/div/div/div/div/form/section[2]/div[4]/input"
        self.email_input = "/html/body/main/div/section/div/div/div/div/form/section[3]/div[3]/div[1]/p[3]/input"
        self.final_ok_btn = "/html/body/main/div/section/div/div/div/div/form/section[3]/div[3]/div[1]/input[3]"
        self.conf_msg = "/html/body/main/div/section/div/div/div/section/div/p"


    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Tuple[str, Optional[str]]:
        self.logger.info(f" Targeting trendmicro ".center(60, "="))
        self.logger.info(f"[*] Using vendor endpoint at: {self.url}")

        load_url_and_wait_until_it_is_fully_loaded(driver, self.url)
        handle_cookie_consent(driver)
        handle_human_verification_checkbox(driver)

        # Enter URL and submit the lookup form
        wait_and_input_on_element(driver, self.url_input, target_url)
        wait_and_click_on_element(driver, self.submit_btn)

        # Extract category result
        cat_val = None
        if not return_reputation_only:
            try:
                cat_val = wait_for_element_and_fetch_value(driver, self.cat_res)
                self.logger.success(f"[+] Category: {cat_val.upper()}")
            except Exception as e:
                self.logger.error(f"[-] An error occurred while fetching category: {str(e)}")

        # Extract safety reputation result
        safety_val = "Unknown"
        try:
            safety_val = wait_for_element_and_fetch_value(driver, self.safety_res)
            self.logger.success(f"[+] Reputation: {safety_val.upper()}")
        except Exception as e:
            self.logger.error(f"[-] An error occurred while fetching safety reputation: {str(e)}")

        return safety_val, cat_val


    def submit(self, driver, url: str, email: str, category: str) -> None:
        for protocol_url in prepare_urls_for_submission(url):
            self.submit_single_url(driver, protocol_url, email, category)


    def submit_single_url(self, driver, url: str, email: str, category: str) -> None:
        safety_val, cat_val = self.check(driver, url)

        if str(category) in str(cat_val):
            self.logger.info("The proposed category is the same as the one previously found. Returning.")
            return

        self.logger.info("[*] Starting new category and safety reputation submission process on TrendMicro")

        # Navigate to reclassification form
        try:
            wait_and_click_on_element(driver, self.reclass_btn)
            wait_and_click_on_element(driver, self.proceed_btn)
        except Exception as e:
            self.logger.error(f"[-] An error occurred while proceeding with reclassification request: {str(e)}")

        # Handle "Newly Observed Domain" special case
        if "Newly Observed Domain" in (cat_val or ""):
            wait_and_click_on_element(driver, "/html/body/main/div/section/div/div/div/div/form/section[1]/div[4]/span/input")

        # Fill in the new category
        wait_and_click_on_element(driver, self.diff_cat_radio)
        new_cat = categories_map[category]["TrendMicro"]
        evaluate_on_element(driver, self.diff_cat_input, "el => el.removeAttribute('readonly')")
        clear_element(driver, self.diff_cat_input)
        fill_element(driver, self.diff_cat_input, str(new_cat))

        wait_and_input_on_element(driver, self.email_input, str(email))
        solve_google_recaptcha(driver)

        # Submit and verify confirmation
        try:
            wait_and_click_on_element(driver, self.final_ok_btn)
            conf = wait_for_element_and_fetch_value(driver, self.conf_msg)

            if "Please check your inbox for a confirmation message" in conf:
                self.logger.success("[+] Successfully submitted for review. Please check your inbox for a confirmation message.")
            else:
                self.logger.info("[*] Something went wrong with the reclassification request.")
        except Exception as e:
            self.logger.error(f"[-] An error occurred during the submission process: {str(e)}")
