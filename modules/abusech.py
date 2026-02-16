import requests
from collections import Counter
from helpers.logger import *
from helpers.credentials import *


class AbuseCH:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = "https://urlhaus-api.abuse.ch/v1/host/"
        self.api_key = urlhaus_api_key


    def check(self, domain: str) -> None:
        try:
            self.logger.info(f" Targeting urlhaus ".center(60, "="))

            if not self.api_key:
                self.logger.error("[-] No URLhaus API key configured")
                return

            # Strip protocol prefix — API expects bare host
            clean_host = domain.replace("https://", "").replace("http://", "").strip("/")

            response = requests.post(self.url, data={"host": clean_host}, headers={"Auth-Key": self.api_key})
            response_data = response.json()

            if response_data.get("query_status") == "no_results":
                self.logger.success("[+] No results found — host is clean")
                return

            if response_data.get("query_status") != "ok":
                self.logger.error(f"[-] Query failed: {response_data.get('query_status')}")
                return

            # Log blacklist status
            blacklists = response_data.get("blacklists", {})
            listed = {k: v for k, v in blacklists.items() if v and v != "not listed"}
            if listed:
                self.logger.warning(f"[!] Blacklisted on: {', '.join(f'{k} ({v})' for k, v in listed.items())}")
            else:
                self.logger.success("[+] Not listed on any blacklist")

            # Aggregate and log threat statistics
            urls = response_data.get("urls", [])
            if urls:
                threat_counter = Counter(url.get("threat") for url in urls)
                self.logger.info(f"[*] {len(urls)} URL(s) reported: " + ", ".join(f"{count} {threat}" for threat, count in threat_counter.items()))
            else:
                self.logger.success("[+] No malicious URLs reported")

        except requests.exceptions.RequestException as e:
            self.logger.error(f"[-] RequestException: {e}")
        except Exception as e:
            self.logger.error(f"[-] An unexpected error occurred: {e}")

