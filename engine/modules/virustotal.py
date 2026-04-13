import requests, json
from helpers.logger import *
from helpers.credentials import *
from helpers.rate_limit import rate_limit_wait


# Public VirusTotal free tier = 4 lookups/min, 500/day. The rate limiter is
# enforced across workers via Redis so two Celery prefork workers don't
# accidentally blow the quota. If the quota is tight, the limiter blocks for
# up to ~60s; after that it gives up waiting and lets VT return its own 429.
VT_MAX_CALLS_PER_WINDOW = 4
VT_WINDOW_SECONDS = 60


class VirusTotal:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.api_address = "https://www.virustotal.com/api/v3/domains/"
        self.api_key = virustotal_api_key


    def check(self, domain: str) -> str:
        try:
            self.logger.info(f" Targeting virustotal ".center(60, "="))

            if not self.api_key:
                self.logger.error("[-] No VirusTotal API key configured")
                return "Error (no key)"

            clean_domain = domain.replace("https://", "").replace("http://", "").strip("/")

            # Block until the shared 4/min quota has a free slot
            rate_limit_wait(
                key="virustotal",
                max_calls=VT_MAX_CALLS_PER_WINDOW,
                window_seconds=VT_WINDOW_SECONDS,
                logger=self.logger,
            )

            url = f"{self.api_address}{clean_domain}"
            headers = {"accept": "application/json", "x-apikey": self.api_key}
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code == 429:
                self.logger.warning("[!] VirusTotal returned 429 Too Many Requests despite rate limiter")
                return "Error (rate limited)"
            response.raise_for_status()

            try:
                data = response.json()
            except json.JSONDecodeError as e:
                self.logger.error(f"[-] Error decoding JSON response: {e}")
                return "Error"

            attrs = data["data"]["attributes"]
            stats = attrs["last_analysis_stats"]
            harmless = stats.get("harmless", 0)
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            undetected = stats.get("undetected", 0)
            timeout_count = stats.get("timeout", 0)
            total = harmless + malicious + suspicious + undetected + timeout_count

            self.logger.info(
                f"[*] Harmless: {harmless}  Malicious: {malicious}  Suspicious: {suspicious}  "
                f"Undetected: {undetected}  Timeout: {timeout_count}"
            )

            votes = attrs.get("total_votes", {})
            self.logger.success(
                f"[+] Community votes — Harmless: {votes.get('harmless', 0)}  Malicious: {votes.get('malicious', 0)}"
            )

            flagged = {
                checker: result["result"]
                for checker, result in attrs.get("last_analysis_results", {}).items()
                if result["category"] in ("malicious", "suspicious")
            }
            if flagged:
                self.logger.warning(f"[!] Flagged by {len(flagged)} engine(s):")
                for checker, result in flagged.items():
                    self.logger.warning(f"    {checker}: {result}")
            else:
                self.logger.success("[+] Not flagged by any engine")

            # VirusTotal aggregates ~94 engines. On clean results we show the
            # breakdown of explicit harmless vs undetected (engines that simply
            # don't have data on the domain — common for brand-new sites). On
            # a flagged result we show the count of engines that raised a flag.
            flagged_count = malicious + suspicious
            if flagged_count == 0:
                return f"Clean ({harmless}/{total} clean · {undetected}/{total} not rated)"
            if malicious > 0:
                return f"Malicious ({flagged_count}/{total} flagged)"
            return f"Suspicious ({flagged_count}/{total} flagged)"

        except requests.exceptions.RequestException as e:
            self.logger.error(f"[-] RequestException: {e}")
            return "Error"
        except Exception as e:
            self.logger.error(f"[-] An unexpected error occurred: {e}")
            return "Error"
