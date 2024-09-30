from Crypto.Cipher import PKCS1_OAEP, PKCS1_v1_5
import Crypto
from Crypto.PublicKey import RSA
from Crypto import Random
from base64 import b64encode, b64decode
import function.settings as settings
import requests
import socket, random, string

Pk1 = ''
Pk2 = ''

private_key = '-----BEGIN RSA PRIVATE KEY-----\n{}\n-----END RSA PRIVATE KEY-----'.format(Pk1)
public_key = '-----BEGIN PUBLIC KEY-----\n{}\n-----END PUBLIC KEY-----'.format(Pk2)

pc_name = socket.gethostname()

if '-' in pc_name:
    prefix = 'at'+pc_name.split('-')[-1]
else:
    prefix = 'at'+pc_name

def generate_user_account(totaluser):
    account_list = []
    for i in range(totaluser):
        
        acc_name = prefix+"{:03d}".format(i+1)
        account_list.append(acc_name)
    
    print(account_list)
    return account_list

def get_env(s) -> dict:    
    env = {        
        
        
    }
    return env.get(s)

def set_platform_header(environment, vend, token=None, x_uuid=None):
    characters = string.ascii_letters + string.digits
    header= {
        "origin": settings.platform_url,
        "referer": settings.platform_url,
        "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4044.141 Safari/537.36",
        "devicemode": "Pixel 5",
        "apptype": "2",
        "device":"mobile",
        "content-type": "application/json;charset=UTF-8",
        "x-uuid":''.join(random.choice(characters) for i in range(20))
    }
    
    if token is not None:
        header.update({"authorization": "Bearer " + str(token)})
    return header

def set_sport_header(environment, vend, stoken=None):
    header= {
            "origin": settings.platform_url,
            "referer": settings.platform_url,
            "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4044.141 Safari/537.36",
            "devicemode": "Pixel 5",            
            "apptype": "2",
            "device":"mobile",
            "content-type": "application/json;charset=UTF-8",
            "currency": "CNY"
            # "cks" : str(get_cks(vend, account))
        }

    if stoken is not None:
        header.update({"authorization": "Bearer " + str(stoken)})
    return header


def encrypt(text):
    s = str.encode(text)
    rsa_public_key = RSA.importKey(public_key)
    rsa_public_key = PKCS1_v1_5.new(rsa_public_key)
    encrypted_text = rsa_public_key.encrypt(s)
    encrypted_text = b64encode(encrypted_text)
    return encrypted_text

def decrypt(text):
    rsa_private_key = RSA.importKey(private_key)
    rsa_private_key = PKCS1_v1_5.new(rsa_private_key)
    decrypted_text = rsa_private_key.decrypt(b64decode(text), 0)
    return decrypted_text

def get_score_type():
    
    try:
        if settings.env == 'pre-prod':            
            path = f'{settings.api_url}/Test_API_domain/systatus/proxy/sports/prod/Java/json/zh-cn/market_property_setting'
        elif settings.env.startswith('qa'):
            path = f'{settings.api_url}/Test_API_domain/systatus/proxy/sports/{settings.env[:2]}-{settings.env[-1]}/Java/json/zh-cn/market_property_setting'
        else:
            path = f'https://Test_API_domain/sports/{settings.env}/Java/json/zh-cn/market_property_setting.json'
        response = requests.request("GET", path).json()
        # ball = response[balltype.get(str(sid))]
        # for i, j in ball.items():
        #     new_dict = {}
        #     new_dict['betScoreType'] = j['betScoreType']   
        #     new_dict['withPrincipal'] = j['withPrincipal']   
        #     res[i] = new_dict
        response['1'] = response.pop('football')
        response['2'] = response.pop('basketball')
        response['3'] = response.pop('tennis')
        response['4'] = response.pop('baseball')
        return response
    except Exception as e:
        print('get_score_type error: %s'%e)
        return {
            '1':{},
            '2':{},
            '3':{},
            '4':{}
        }

def caculate_stages(start_user, end_user, user_diff, start_duration, duration_diff, spawn_rate=10):
    stages = []

    steps = int((end_user-start_user)/user_diff)
    for x in range(0, steps+1):
        step = {
            "duration": start_duration + (duration_diff* x), 
            "users": start_user + (user_diff * x), 
            "spawn_rate": spawn_rate
        }
        stages.append(step)
    
    return stages