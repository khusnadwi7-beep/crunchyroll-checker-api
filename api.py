from flask import Flask, request, jsonify
import json
import sys
import os
import importlib.util
import traceback

app = Flask(__name__)

# ============ LOAD ALL CHECKERS ============
checkers = {}

def load_checker(name, path):
    """Load checker module dynamically"""
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"Error loading {name}: {e}")
        return None

# Load semua checker
checker_files = {
    'crunchyroll': 'checkers/crunchyroll.py',
    'disney': 'checkers/disney.py',
    'expressvpn': 'checkers/expressvpn.py',
    'hotmail': 'checkers/hotmail.py',
    'steam': 'checkers/steam.py',
    'netflix': 'checkers/netflix.py',
    'tod': 'checkers/tod.py',
    'netflixvm': 'checkers/netflixvm.py'
}

print("=" * 50)
print("Loading checkers...")
print(f"Current directory: {os.getcwd()}")

for name, path in checker_files.items():
    if os.path.exists(path):
        module = load_checker(name, path)
        if module:
            checkers[name] = module
            print(f"✅ Loaded {name}")
        else:
            print(f"❌ Failed to load {name}")
    else:
        print(f"❌ File not found: {path}")

print(f"Loaded services: {list(checkers.keys())}")
print("=" * 50)

# ============ ROUTES ============
@app.route('/')
def home():
    return jsonify({
        'status': 'ok',
        'message': 'Checker API is running',
        'services': list(checkers.keys())
    })

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'services': list(checkers.keys())})

@app.route('/check', methods=['POST'])
def check_account():
    try:
        data = request.get_json()
        service = data.get('service')
        email = data.get('email')
        password = data.get('password')
        
        if not service or not email or not password:
            return jsonify({'status': 'error', 'message': 'Missing parameters: service, email, password'}), 400
        
        if service not in checkers:
            return jsonify({'status': 'error', 'message': f'Service {service} not found. Available: {list(checkers.keys())}'}), 404
        
        module = checkers[service]
        
        # ============ CRUNCHYROLL ============
        if service == 'crunchyroll':
            try:
                result = module.baron_check(email, password)
                if result['st'] == 'hit':
                    return jsonify({
                        'status': 'hit',
                        'details': f"Plan: {result.get('plan', '?')} | Exp: {result.get('expires', '?')} | Streams: {result.get('streams', '?')}"
                    })
                elif result['st'] == 'free':
                    return jsonify({'status': 'free', 'details': 'Free account'})
                else:
                    return jsonify({'status': 'bad'})
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)})
        
        # ============ DISNEY+ ============
        if service == 'disney':
            try:
                status, detail, info = module._check(email, password, None)
                if status == 'HIT':
                    return jsonify({'status': 'hit', 'details': f"Plan: {info.get('plan', '?')} | Exp: {info.get('expiry', '?')}"})
                elif status == 'FREE':
                    return jsonify({'status': 'free', 'details': 'No subscription'})
                else:
                    return jsonify({'status': 'bad'})
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)})
        
        # ============ EXPRESSVPN ============
        if service == 'expressvpn':
            try:
                checker = module.ExpressVPNChecker()
                result = checker.check_account(email, password)
                if result['status'] == 'HIT':
                    data = result['data']
                    return jsonify({'status': 'hit', 'details': f"Plan: {data.get('plan', '?')} | Exp: {data.get('expire_date', '?')}"})
                elif result['status'] == 'EXPIRED':
                    return jsonify({'status': 'free', 'details': 'Expired'})
                else:
                    return jsonify({'status': 'bad'})
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)})
        
        # ============ HOTMAIL ============
        if service == 'hotmail':
            try:
                token, cid = module.authenticate(email, password)
                if token:
                    return jsonify({'status': 'hit', 'details': 'Valid Hotmail account'})
                else:
                    return jsonify({'status': 'bad'})
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)})
        
        # ============ STEAM ============
        if service == 'steam':
            try:
                result = module.baron_check(email, password)
                if result['st'] == 'hit':
                    return jsonify({'status': 'hit', 'details': f"Level: {result.get('level', '?')} | Games: {result.get('games', 0)}"})
                elif result['st'] == '2fa':
                    return jsonify({'status': 'hit', 'details': '2FA Required'})
                else:
                    return jsonify({'status': 'bad'})
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)})
        
        # ============ TOD.TV ============
        if service == 'tod':
            try:
                status, detail, info = module._check(email, password, None)
                if status == 'HIT':
                    return jsonify({'status': 'hit', 'details': f"Plan: {info.get('plan', '?')} | Exp: {info.get('expiry', '?')}"})
                else:
                    return jsonify({'status': 'bad'})
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)})
        
        # ============ NETFLIX VM ============
        if service == 'netflixvm':
            try:
                checker = module.NetflixVMSubChecker()
                result = checker.check_account(email, password, use_proxy=False)
                if result['status'] in ['HIT_SUBSCRIPTION', 'HIT_NO_SUBSCRIPTION']:
                    return jsonify({'status': 'hit', 'details': result.get('subscription_status', 'Active')})
                else:
                    return jsonify({'status': 'bad'})
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)})
        
        # ============ NETFLIX (COOKIE) ============
        if service == 'netflix':
            return jsonify({'status': 'error', 'message': 'Netflix requires cookie format, use /checknetflix command'})
        
        return jsonify({'status': 'error', 'message': 'Unknown service'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e), 'trace': traceback.format_exc()}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)