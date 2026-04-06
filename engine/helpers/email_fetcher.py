import imaplib, email, re, time
from email.header import decode_header
from typing import Optional
from helpers.credentials import gmail_email, gmail_app_password
from helpers.logger import Logger

logger = Logger("email_fetcher")


def fetch_paloalto_verification_code(max_wait_seconds: int = 60, poll_interval: int = 5, max_age_seconds: int = 120) -> Optional[str]:
    # Fetch the latest Palo Alto verification code from Gmail. (2FA)
    logger.info("[*] Connecting to Gmail IMAP...")

    start_time = time.time()

    while time.time() - start_time < max_wait_seconds:
        try:
            # Connect to Gmail IMAP
            imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            imap.login(gmail_email, gmail_app_password)
            imap.select("INBOX")

            # Search for recent emails from Palo Alto
            # Search criteria: from Palo Alto, recent (last few minutes)
            search_criteria = '(FROM "paloaltonetworks" UNSEEN)'

            status, messages = imap.search(None, search_criteria)

            if status != "OK":
                logger.warning(f"[!] IMAP search failed: {status}")
                imap.logout()
                time.sleep(poll_interval)
                continue

            email_ids = messages[0].split()

            if not email_ids:
                logger.debug(f"[*] No new Palo Alto emails found, waiting {poll_interval}s...")
                imap.logout()
                time.sleep(poll_interval)
                continue

            # Get the latest email
            latest_id = email_ids[-1]
            status, msg_data = imap.fetch(latest_id, "(RFC822)")

            if status != "OK":
                logger.warning(f"[!] Failed to fetch email: {status}")
                imap.logout()
                time.sleep(poll_interval)
                continue

            # Parse the email
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Get subject
            subject, encoding = decode_header(msg["Subject"])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding or "utf-8")

            logger.info(f"[*] Found email: {subject}")

            # Extract the body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="ignore")
                            break
                    elif content_type == "text/html" and not body:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="ignore")
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="ignore")

            # Look for verification code patterns
            # Common patterns: 6-digit code, or "code: XXXXXX", "verification code: XXXXXX"
            code_patterns = [
                r'verification code[:\s]+(\d{6})',
                r'code[:\s]+(\d{6})',
                r'one-time code[:\s]+(\d{6})',
                r'OTP[:\s]+(\d{6})',
                r'\b(\d{6})\b',  # Any 6-digit number as fallback
            ]

            for pattern in code_patterns:
                match = re.search(pattern, body, re.IGNORECASE)
                if match:
                    code = match.group(1)
                    logger.success(f"[+] Found verification code: {code}")

                    # Mark email as read
                    imap.store(latest_id, '+FLAGS', '\\Seen')
                    imap.logout()
                    return code

            # If no code found in body, check subject
            for pattern in code_patterns:
                match = re.search(pattern, subject, re.IGNORECASE)
                if match:
                    code = match.group(1)
                    logger.success(f"[+] Found verification code in subject: {code}")
                    imap.store(latest_id, '+FLAGS', '\\Seen')
                    imap.logout()
                    return code

            logger.warning(f"[!] No verification code found in email body")
            logger.debug(f"[*] Body preview: {body[:500]}")
            imap.logout()
            time.sleep(poll_interval)

        except imaplib.IMAP4.error as e:
            logger.error(f"[!] IMAP error: {e}")
            time.sleep(poll_interval)
        except Exception as e:
            logger.error(f"[!] Error fetching email: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(poll_interval)

    logger.error(f"[!] Timeout waiting for verification email ({max_wait_seconds}s)")
    return None


def test_gmail_connection() -> bool:
    # Test if Gmail IMAP connection works.
    try:
        logger.info("[*] Testing Gmail IMAP connection...")
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        imap.login(gmail_email, gmail_app_password)
        imap.select("INBOX")

        # Get inbox status
        status, count = imap.search(None, "ALL")
        total_emails = len(count[0].split()) if status == "OK" else 0

        logger.success(f"[+] Gmail connection successful! Inbox has {total_emails} emails")
        imap.logout()
        return True
    except Exception as e:
        logger.error(f"[!] Gmail connection failed: {e}")
        return False


if __name__ == "__main__":
    # Test the connection
    if test_gmail_connection():
        print("\n[*] Testing verification code fetch (waiting 30s)...")
        code = fetch_paloalto_verification_code(max_wait_seconds=30)
        if code:
            print(f"\n=== FOUND CODE: {code} ===")
        else:
            print("\n=== NO CODE FOUND ===")
