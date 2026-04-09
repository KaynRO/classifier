import requests, json
from helpers.logger import *
from helpers.credentials import *


class GoogleSafeBrowsing:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.api_url = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
        self.api_key = google_safebrowsing_api_key


    def check(self, domain: str) -> str:
        try:
            self.logger.info(f" Targeting google safe browsing ".center(60, "="))

            clean_domain = domain.replace("https://", "").replace("http://", "").strip("/")
            url_to_check = f"https://{clean_domain}/"

            payload = {
                "client": {"clientId": "classifier", "clientVersion": "1.0"},
                "threatInfo": {
                    "threatTypes": [
                        "MALWARE",
                        "SOCIAL_ENGINEERING",
                        "UNWANTED_SOFTWARE",
                        "POTENTIALLY_HARMFUL_APPLICATION",
                    ],
                    "platformTypes": ["ANY_PLATFORM"],
                    "threatEntryTypes": ["URL"],
                    "threatEntries": [
                        {"url": url_to_check},
                        {"url": f"http://{clean_domain}/"},
                    ],
                },
            }

            response = requests.post(
                self.api_url,
                params={"key": self.api_key},
                headers={"Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()

            try:
                data = response.json()
            except json.JSONDecodeError as e:
                self.logger.error(f"[-] Error decoding JSON response: {e}")
                return "Error"

            matches = data.get("matches", [])
            # Google Safe Browsing checks against 4 threat categories per URL (2 URLs = 8 checks)
            total_checks = 8

            if not matches:
                self.logger.success("[+] Clean — no threats detected")
                return f"Clean (0/{total_checks} threats)"

            self.logger.warning(f"[!] Flagged with {len(matches)} threat(s):")
            for match in matches:
                threat_type = match.get("threatType", "UNKNOWN")
                platform = match.get("platformType", "UNKNOWN")
                threat_url = match.get("threat", {}).get("url", "N/A")
                self.logger.warning(f"    Threat: {threat_type}  Platform: {platform}  URL: {threat_url}")

            return f"Malicious ({len(matches)}/{total_checks} threats)"

        except requests.exceptions.RequestException as e:
            self.logger.error(f"[-] RequestException: {e}")
            return "Error"
        except Exception as e:
            self.logger.error(f"[-] An unexpected error occurred: {e}")
            return "Error"
