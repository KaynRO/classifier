import requests, json
from helpers.logger import *
from helpers.credentials import *


class VirusTotal:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.api_address = "https://www.virustotal.com/api/v3/domains/"
        self.api_key = virustotal_api_key


    def check(self, domain: str) -> None:
        try:
            self.logger.info(f" Targeting virustotal ".center(60, "="))

            # Strip protocol prefix — API expects bare domain
            clean_domain = domain.replace("https://", "").replace("http://", "").strip("/")

            url = f"{self.api_address}{clean_domain}"
            headers = {"accept": "application/json", "x-apikey": self.api_key}
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            try:
                data = response.json()
            except json.JSONDecodeError as e:
                self.logger.error(f"[-] Error decoding JSON response: {e}")
                return

            attrs = data["data"]["attributes"]

            # Log analysis statistics
            stats = attrs["last_analysis_stats"]
            self.logger.info(f"[*] Harmless: {stats['harmless']}  Malicious: {stats['malicious']}  Suspicious: {stats['suspicious']}  Undetected: {stats['undetected']}  Timeout: {stats['timeout']}")

            # Log reputation votes
            votes = attrs["total_votes"]
            self.logger.success(f"[+] Community votes — Harmless: {votes['harmless']}  Malicious: {votes['malicious']}")

            # Log flagged engines (only malicious/suspicious)
            flagged = {
                checker: result["result"]
                for checker, result in attrs["last_analysis_results"].items()
                if result["category"] in ("malicious", "suspicious")
            }
            if flagged:
                self.logger.warning(f"[!] Flagged by {len(flagged)} engine(s):")
                for checker, result in flagged.items():
                    self.logger.warning(f"    {checker}: {result}")
            else:
                self.logger.success("[+] Not flagged by any engine")

        except requests.exceptions.RequestException as e:
            self.logger.error(f"[-] RequestException: {e}")
        except Exception as e:
            self.logger.error(f"[-] An unexpected error occurred: {e}")
