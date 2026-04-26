from flask import Flask, request, jsonify, render_template
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import requests
import re
import urllib.parse
import base64

app = Flask(__name__)

# Load configuration
try:
    from config import SITE_CONFIG
    print("✓ Loaded config from config.py")
except ImportError:
    print("⚠ config.py not found, using defaults")
    SITE_CONFIG = {
        "site_name": "Musu ✿",
        "site_logo_emoji": "✿",
        "freefire_version": "OB53",
        "youtube_link": "https://youtube.com/@muskangaming18",
        "instagram_link": "https://www.instagram.com/muskan_gaming18",
        "telegram_link": "https://t.me/MUSUKITEAM",
        "popup_title": "✿ JOIN THE FAMILY ✿",
        "popup_message": "Follow us!",
        "bio_char_limit": 300,
        "default_region": "IND",
        "footer_text": "Musu ✿ Bio Tool",
        "howto_youtube_link": "https://youtube.com/@muskangaming18",
        "howto_button_text": "📺 Watch Tutorial",
        "create_own_site_link": "https://youtube.com/@muskangaming18",
        "templates": [],
        "regions": [],
        "v_badges": [],
        "colors": [],
        "gradients": []
    }

app.config['SITE_CONFIG'] = SITE_CONFIG

# Simple protobuf alternative - using manual byte construction
def create_protobuf_data(bio_text):
    """
    Manually create the protobuf data structure
    This avoids complex protobuf dependencies
    """
    # Simple structure: field_2=17, field_8=bio, field_9=1
    bio_bytes = bio_text.encode('utf-8')
    
    # Build a simple protobuf-like structure
    # Field 2 (varint 17)
    data = bytearray()
    
    # field_2 = 17 (tag 2, varint)
    data.extend([0x10, 0x11])  # tag 2 (field number 2 << 3 | 0 = 16) + value 17
    
    # field_5 = empty message
    data.extend([0x2a, 0x00])  # tag 5 (field number 5 << 3 | 2 = 42) + length 0
    
    # field_6 = empty message  
    data.extend([0x32, 0x00])  # tag 6 (field number 6 << 3 | 2 = 50) + length 0
    
    # field_8 = bio text
    tag_8 = 0x42  # field number 8 << 3 | 2 = 66
    data.extend([tag_8])
    data.extend(_encode_length(len(bio_bytes)))
    data.extend(bio_bytes)
    
    # field_9 = 1
    data.extend([0x48, 0x01])  # tag 9 (field number 9 << 3 | 0 = 72) + value 1
    
    # field_11 = empty message
    data.extend([0x5a, 0x00])  # tag 11 (field number 11 << 3 | 2 = 90) + length 0
    
    # field_12 = empty message
    data.extend([0x62, 0x00])  # tag 12 (field number 12 << 3 | 2 = 98) + length 0
    
    return bytes(data)

def _encode_length(length):
    """Encode length for protobuf"""
    if length < 128:
        return bytes([length])
    result = bytearray()
    while length > 0:
        result.append(length & 0x7F)
        length >>= 7
    return bytes(result)

# Encryption keys
key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

def get_region_url(region):
    region_urls = {
        "IND": "https://client.ind.freefiremobile.com",
        "BR": "https://client.us.freefiremobile.com",
        "US": "https://client.us.freefiremobile.com",
        "SAC": "https://client.us.freefiremobile.com",
        "NA": "https://client.us.freefiremobile.com",
        "ME": "https://clientbp.common.ggbluefox.com",
        "TH": "https://clientbp.common.ggbluefox.com"
    }
    return region_urls.get(region.upper(), "https://clientbp.ggblueshark.com")

def get_account_from_eat(eat_token):
    try:
        if '?eat=' in eat_token:
            parsed = urllib.parse.urlparse(eat_token)
            params = urllib.parse.parse_qs(parsed.query)
            eat_token = params.get('eat', [eat_token])[0]
        elif '&eat=' in eat_token:
            match = re.search(r'[?&]eat=([^&]+)', eat_token)
            if match:
                eat_token = match.group(1)
        
        EAT_API_URL = "https://eat-api.thory.buzz/api"
        response = requests.get(f"{EAT_API_URL}?eatjwt={eat_token}", timeout=15)
        
        if response.status_code != 200:
            return None, None, f"API error: HTTP {response.status_code}"
        
        data = response.json()
        if data.get('status') != 'success':
            return None, None, f"Invalid token: {data.get('message', 'Unknown error')}"
        
        jwt_token = data.get('token')
        if not jwt_token:
            return None, None, "No JWT token in response"
        
        account_info = {
            "uid": data.get('uid'),
            "region": data.get('region', 'IND'),
            "nickname": data.get('nickname')
        }
        
        return jwt_token, account_info, None
        
    except Exception as e:
        return None, None, str(e)

def update_bio_with_jwt(jwt_token, bio_text, region):
    try:
        base_url = get_region_url(region)
        url_bio = f"{base_url}/UpdateSocialBasicInfo"
        
        # Create protobuf data
        data_bytes = create_protobuf_data(bio_text.replace('+', ' '))
        
        # Encrypt
        padded_data = pad(data_bytes, AES.block_size)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted_data = cipher.encrypt(padded_data)
        
        if "ind" in base_url:
            host = "client.ind.freefiremobile.com"
        elif "us" in base_url:
            host = "client.us.freefiremobile.com"
        elif "common" in base_url:
            host = "clientbp.common.ggbluefox.com"
        else:
            host = "clientbp.ggblueshark.com"
        
        headers = {
            "Expect": "100-continue",
            "Authorization": f"Bearer {jwt_token}",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": SITE_CONFIG.get('freefire_version', 'OB53'),
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; SM-A305F Build/RP1A.200720.012)",
            "Host": host,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip"
        }
        
        res_bio = requests.post(url_bio, headers=headers, data=encrypted_data, timeout=30)
        return res_bio.status_code == 200
        
    except Exception as e:
        raise Exception(str(e))

def pad(data, block_size):
    """Manual padding function"""
    padding_len = block_size - (len(data) % block_size)
    return data + bytes([padding_len] * padding_len)

# Routes
@app.route('/')
@app.route('/page')
def index():
    return render_template('index.html', config=SITE_CONFIG)

@app.route('/api/verify-token', methods=['POST'])
def verify_token():
    try:
        data = request.get_json()
        eat_token = data.get('eat_token')
        
        if not eat_token:
            return jsonify({"success": False, "error": "Missing EAT token"}), 400
        
        jwt_token, account_info, error = get_account_from_eat(eat_token)
        
        if error:
            return jsonify({"success": False, "error": error}), 400
        
        return jsonify({
            "success": True,
            "account": {
                "uid": account_info.get('uid'),
                "region": account_info.get('region'),
                "nickname": account_info.get('nickname')
            },
            "jwt_token": jwt_token
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/update-bio', methods=['POST'])
def update_bio():
    try:
        data = request.get_json()
        jwt_token = data.get('jwt_token')
        bio_text = data.get('bio')
        region = data.get('region')
        
        if not jwt_token:
            return jsonify({"success": False, "error": "Missing JWT token"}), 400
        
        if not bio_text:
            return jsonify({"success": False, "error": "Missing bio text"}), 400
        
        max_chars = SITE_CONFIG.get('bio_char_limit', 300)
        if len(bio_text) > max_chars:
            return jsonify({"success": False, "error": f"Bio exceeds {max_chars} characters"}), 400
        
        success = update_bio_with_jwt(jwt_token, bio_text, region)
        
        if success:
            return jsonify({"success": True, "message": "Bio updated successfully!"})
        else:
            return jsonify({"success": False, "error": "Bio update failed - server error"}), 400
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
