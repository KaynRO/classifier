import requests
import dns.resolver
from helpers.logger import *
from helpers.credentials import *


class AbuseIpDB:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.api_key = abuseipdb_api_key
        self.url = "https://api.abuseipdb.com/api/v2/"


    def resolve_domain(self, domain: str) -> str:
        clean = domain.replace("https://", "").replace("http://", "").strip("/")
        try:
            answers = dns.resolver.resolve(clean, "A")
            ip = str(answers[0])
            self.logger.info(f"[*] Resolved {clean} -> {ip}")
            return ip
        except dns.resolver.NXDOMAIN:
            self.logger.error(f"[-] Domain not found: {clean}")
            return ""
        except dns.resolver.NoAnswer:
            self.logger.error(f"[-] No A record for: {clean}")
            return ""
        except Exception as e:
            self.logger.error(f"[-] DNS resolution failed: {e}")
            return ""


    def check(self, domain: str, maxAgeInDays: int = 30) -> None:
        try:
            self.logger.info(f" Targeting abuseipdb ".center(60, "="))

            ip = self.resolve_domain(domain)
            if not ip:
                return

            response = requests.get(
                f"{self.url}check",
                headers={"Accept": "application/json", "Key": self.api_key},
                params={"ipAddress": ip, "maxAgeInDays": maxAgeInDays},
            )
            response.raise_for_status()

            data = response.json().get("data", {})

            abuse_score = data.get("abuseConfidenceScore", 0)
            total_reports = data.get("totalReports", 0)
            isp = data.get("isp", "Unknown")
            country = data.get("countryCode", "Unknown")
            is_whitelisted = data.get("isWhitelisted", False)

            self.logger.debug(f"[*] IP: {ip}  ISP: {isp}  Country: {country}")
            self.logger.info(f"[*] Reports: {total_reports}  Abuse score: {abuse_score}%  Whitelisted: {is_whitelisted}")

            if abuse_score == 0 and total_reports == 0:
                self.logger.success("[+] Clean — no abuse reports")
            elif abuse_score > 50:
                self.logger.warning(f"[!] High abuse confidence score: {abuse_score}%")
            else:
                self.logger.info(f"[*] Low-moderate abuse score: {abuse_score}%")

        except requests.exceptions.RequestException as e:
            self.logger.error(f"[-] RequestException: {e}")
        except Exception as e:
            self.logger.error(f"[-] An unexpected error occurred: {e}")

