import requests
from collections import Counter
from helpers.logger import *
from helpers.credentials import *


class AbuseCH:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = "https://urlhaus-api.abuse.ch/v1/host/"
        self.api_key = urlhaus_api_key


    def check(self, domain: str) -> str:
        try:
            self.logger.info(f" Targeting urlhaus ".center(60, "="))

            if not self.api_key:
                self.logger.error("[-] No URLhaus API key configured")
                return "Error (no key)"

            clean_host = domain.replace("https://", "").replace("http://", "").strip("/")

            response = requests.post(self.url, data={"host": clean_host}, headers={"Auth-Key": self.api_key})
            response_data = response.json()

            if response_data.get("query_status") == "no_results":
                self.logger.success("[+] No results found — host is clean")
                return "Clean (0 URLs, not listed)"

            if response_data.get("query_status") != "ok":
                self.logger.error(f"[-] Query failed: {response_data.get('query_status')}")
                return "Error"

            blacklists = response_data.get("blacklists", {})
            listed_count = sum(1 for v in blacklists.values() if v and v != "not listed")
            blacklist_total = len(blacklists) or 0

            if listed_count:
                listed_names = [f"{k} ({v})" for k, v in blacklists.items() if v and v != "not listed"]
                self.logger.warning(f"[!] Blacklisted on: {', '.join(listed_names)}")
            else:
                self.logger.success("[+] Not listed on any blacklist")

            urls = response_data.get("urls", [])
            if urls:
                threat_counter = Counter(url.get("threat") for url in urls)
                self.logger.info(
                    f"[*] {len(urls)} URL(s) reported: "
                    + ", ".join(f"{count} {threat}" for threat, count in threat_counter.items())
                )
            else:
                self.logger.success("[+] No malicious URLs reported")

            if urls or listed_count:
                parts = []
                if urls:
                    parts.append(f"{len(urls)} URLs")
                if blacklist_total:
                    parts.append(f"{listed_count}/{blacklist_total} blacklists")
                return "Malicious (" + ", ".join(parts) + ")"
            if blacklist_total:
                return f"Clean (0/{blacklist_total} blacklists)"
            return "Clean (not listed)"

        except requests.exceptions.RequestException as e:
            self.logger.error(f"[-] RequestException: {e}")
            return "Error"
        except Exception as e:
            self.logger.error(f"[-] An unexpected error occurred: {e}")
            return "Error"

