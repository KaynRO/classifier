import traceback
from typing import Optional
from helpers.utils import *
from helpers.logger import *


def log_exception(logger: Logger) -> None:
    trace = traceback.format_exc()
    logger.error(trace)


class Intelixsophos:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = "https://intelix.sophos.com/url"

        # Element selectors for the check flow
        self.url_input = "/html/body/div[1]/div/div[4]/div/div/div/div/div[1]/div[2]/div[2]/div/div[2]/div/form/div/div/span/div/input"
        self.submit_btn = "/html/body/div[1]/div/div[4]/div/div/div/div/div[1]/div[2]/div[2]/div/div[4]/button"
        self.agree_btn = "/html/body/div[2]/div[2]/button[1]"
        self.cat_res = "/html/body/div[3]/div/div[2]/div[2]/div/div[1]/div/div[2]/div/div[1]"
        self.sec_res = "/html/body/div[3]/div/div[2]/div[2]/div/div[1]/div/div[1]/div/div[1]"
        self.analysis_res = "/html/body/div[3]/div/div[2]/div[2]/div/div[2]/div/div[1]/div/div[1]/div"
        self.risk_res = "/html/body/div[3]/div/div[2]/div[2]/div/div[2]/div/div[2]/div/div[2]"


    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Optional[str]:
        self.logger.info(f" Targeting intelixsophos ".center(60, "="))
        self.logger.info(f"[*] Using vendor endpoint at: {self.url}")

        load_url_and_wait_until_it_is_fully_loaded(driver, self.url)

        # Enter URL and submit (CAPTCHA not supported for this vendor)
        wait_and_input_on_element(driver, self.url_input, target_url)
        self.logger.warning("[!] Captcha solver not available for this module")
        wait_and_click_on_element(driver, self.submit_btn)
        wait_and_click_on_element(driver, self.agree_btn)

        # Wait for results to load
        try:
            wait_for_selector(driver, self.cat_res, timeout=10000)
        except Exception:
            self.logger.warning("[!] Results did not appear or timed out")

        # Extract all result fields
        cat = wait_for_element_and_fetch_value(driver, self.cat_res)
        sec = wait_for_element_and_fetch_value(driver, self.sec_res)
        analysis = wait_for_element_and_fetch_value(driver, self.analysis_res)
        risk = wait_for_element_and_fetch_value(driver, self.risk_res)

        self.logger.success(f"[+] Category: {cat}")
        self.logger.success(f"[+] Security: {sec}")
        self.logger.success(f"[+] Overall Analysis: {analysis}")
        self.logger.success(f"[+] Risk level: {risk}")

        return cat
