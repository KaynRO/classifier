# Classifier
A comprehensive domain categorization and reputation checking tool leveraging stealth browser automation. It automates interaction with major security vendors to check current categorization and submit requests for recategorization, designed to bypass modern bot detections including Cloudflare and reCAPTCHA.


## Features
- **Bot detection evasion** using SeleniumBase with undetected-chromedriver to bypass Cloudflare, DataDome, and other anti-bot systems
- **Automated CAPTCHA solving** via 2Captcha API (reCAPTCHA v2/v3/Enterprise, Cloudflare Turnstile)
- **Multi-vendor support** for domain categorization checks and recategorization submissions across 12 security vendors
- **API-based reputation checks** via VirusTotal, URLhaus/AbuseCH, and AbuseIPDB (no browser needed)
- **Automatic retry logic** with up to 3 attempts per vendor on failure
- **Headless mode** support via xvfb for server environments

**Important:** Before running the script, you must fill in `helpers/credentials.py` with your 2Captcha API key, vendor login credentials (Watchguard, Talos Intelligence), and API keys (VirusTotal, AbuseIPDB, AbuseCH).


## Installation
```bash
# Run the setup script (installs system deps, Python deps, Chrome for Testing, and drivers)
bash setup.sh

# Activate the virtual environment
source .venv/bin/activate

# Configure Credentials
# Update helpers/credentials.py with your 2Captcha API key and vendor credentials (where required)
```


## Usage
```bash
# General Syntax
python3 classifier.py --domain <domain> [options] <action>

# Check category/reputation on all vendors
python3 classifier.py --domain example.com check

# Check specific vendor
python3 classifier.py --domain example.com --vendor talosintelligence check

# Submit for recategorization
python3 classifier.py --domain example.com --vendor watchguard submit --email me@example.com --category "Information Technology"

# Check reputation only
python3 classifier.py --domain example.com reputation
```


**Arguments:**
- `--domain, -d`: Target domain (Required).
- `--vendor, -v`: Specific vendor to target (Default: all). Use `--list-vendors` to see available options.
- `--headless`: Run browsers in headless mode (requires xvfb, see below).
- `--list-vendors`: List all supported vendors and exit.


**Actions:**
- `check`: Retrieve current category and reputation.
- `submit`: Submit a request to change the domain's category. Requires `--email` and `--category`.
- `reputation`: Check domain reputation using API-based vendors (no browser needed). Queries VirusTotal (engine analysis + community votes), URLhaus/AbuseCH (blacklist and threat data), and AbuseIPDB (abuse reports, resolves domain to IP via DNS).


## Headless Mode
Headless mode requires `xvfb` to provide a virtual display for Chrome:
```bash
# Install xvfb (included in setup.sh)
sudo apt-get install -y xvfb

# Run with xvfb
xvfb-run --auto-servernum python3 classifier.py --domain example.com --headless check
```


## Supported Vendors
| Vendor | Check | Submit | Auth Required |
|--------|-------|--------|---------------|
| TrendMicro | Yes | Yes | No |
| McAfee | Yes | Yes | No |
| Brightcloud | Yes | Yes | No |
| BlueCoat | Yes | Yes | No |
| Palo Alto | Yes | Yes | No |
| Zvelo | Yes | Yes | No |
| Watchguard | Yes | Yes | Yes |
| Talos Intelligence | Yes | Yes | Yes |
| LightspeedSystems | Yes | No | No |
| VirusTotal | Yes (API) | No | Yes (API key) |
| AbuseCH / URLhaus | Yes (API) | No | Yes (Auth-Key) |
| AbuseIPDB | Yes (API) | No | Yes (API key) |


## Troubleshooting
- **CAPTCHA Issues**: Ensure a valid 2Captcha API key is set in `helpers/credentials.py`.
- **Timeouts**: Some vendors may require longer wait times due to challenge solving; the tool retries up to 3 times per vendor automatically.
- **Chrome Not Found**: Run `bash setup.sh` to install Chrome for Testing and drivers via SeleniumBase.
- **Headless Fails**: Make sure to run with `xvfb-run --auto-servernum` when using `--headless`.


## Adding a New Vendor
1. Create a new module in `modules/` with a class implementing `check(driver, url, return_reputation_only)` and optionally `submit(driver, url, email, category)`
2. Import and register it in `classifier.py`: add to imports, `init_vendors()` class list, and both `check_vendors` and `submit_vendors` lists in `parse_args()`
3. Add vendor-specific category mappings to `helpers/constants.py` if the vendor supports submit
4. Add any required credentials to `helpers/credentials.py`


## Available Categories
Use `--list-vendors` with an action to see which vendors support it:
```bash
# List vendors that support check
python3 classifier.py --domain example.com --list-vendors check

# List vendors that support submit
python3 classifier.py --domain example.com --list-vendors submit
```