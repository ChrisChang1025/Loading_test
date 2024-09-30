import Function.function as func
import requests
# from platform_thirdparty import *
import logging
import function.settings as settings
import json
from datetime import datetime, timedelta


class platform_user:
    api_url = None
    header = None
    account = None

    def __init__(self, token=None, stoken=None):
        self.token = token
        self.stoken = stoken
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)

    @property
    def token(self):
        # print('property')
        return self.__token

    @token.setter
    def token(self, value):
        # print('setter')
        self.header = func.set_platform_header(settings.env, settings.vend, value)
        self.__token = value

    def login(self, client, account, password, remove_token=True):
        path = self.api_url + "/Test_API_domain/user/token"
        pwd = func.encrypt(password).decode("utf-8")
        ptoken = 'None'
        payload = {
            "account": account,
            "password": pwd,
            "device": "mobile",
            "clientNonce": None
        }
        if remove_token == True and 'authorization' in self.header:
            self.header.pop('authorization')
        api_starttime = datetime.now()
        with client.post(path, json=payload, headers=self.header, catch_response=True) as response:
            try:
                api_endtime = datetime.now()
                response_sec = (api_endtime - api_starttime).seconds + ((api_endtime - api_starttime).microseconds)*0.000001
                if response.status_code == 200:
                    data = json.loads(response.text)
                    if data['code'] == 0:
                        self.token = data['data']['token']
                        self.account = account
                        if data['data']['token'] == '':
                            response.failure("no token")
                            self.logger.error(f"{self.account} no token. {str(response.text)}")
                        else:
                            ptoken = str(self.token)
                            self.header.update({"authorization": "Bearer " + str(self.token)})

                    else:
                        response.failure(f"data code:{str(data['code'])}")
                        self.logger.error(f"{self.account} /Test_API_domain/user/token data code is not 0. {str(response.text)}")
                else:
                    print(f"{self.account} login fail, status code not 200. {str(response.status_code)}")
                    response.failure(f'status_code:{str(response.status_code)}')
                    self.logger.error(f"{self.account} /Test_API_domain/user/token status code is not 0. {str(response.status_code)} {str(response.text)}")

            except Exception as e:
                response.failure("Exception")
                self.logger.error(f"{self.account} /Test_API_domain/user/token ex. {e}")

            return ptoken

    def get_wallets_list(self, client):
        path = self.api_url + "/Test_API_domain/payment/wallets/list"
        payload = {}

        with client.get(path, json=payload, headers=self.header, catch_response=True) as response:
            try:
                if response.status_code == 200:
                    data = json.loads(response.text)
                    if 'wallets' not in data['data']:
                        response.failure(str(data))
                    else:
                        userId = data['data']['wallets'][0]['userId']
                        amount = data['data']['wallets'][0]['amount']
                        print(f'wallet [{self.account}] {amount}')
                else:
                    print("login fail, status code not 200")
                    response.failure(f'status_code:{str(response.status_code)}')
            except Exception as e:
                response.failure("Error :"+str(response.content))

    def extension(self, client):
        path = self.api_url + "/Test_API_domain/user/token/extension"
        payload = {}

        with client.put(path, json=payload, headers=self.header, catch_response=True) as response:
            try:
                if response.status_code == 200:
                    data = json.loads(response.text)
                    if data['code'] != 0:
                        response.failure(f"data code:{str(data['code'])}")
                else:
                    response.failure(f'status_code:{str(response.status_code)}')
            except Exception as e:
                response.failure("Exception")

    def nonce(self, client):
        path = self.api_url + "/Test_API_domain/user/nonce"
        payload = {
            "imageWidth": 500,
            "imageHeight": 300,
            "jigsawWidth": 50,
            "jigsawHeight": 50
        }
        nonce = ''
        with client.post(path, json=payload, headers=self.header, catch_response=True) as response:
            try:
                if response.status_code == 200:
                    data = json.loads(response.text)
                    if data['code'] != 0:
                        print("nonce fail, code not 0, data code:", str(data['code']), ", msg:" + str(data['msg']))
                        response.failure(f"data code:{str(data['code'])}, msg:{str(data['msg'])}")
                        self.logger.error("/Test_API_domain/user/nonce nonce fail, code not 0, " + str(data))
                    else:
                        nonce = data['data']['clientNonce']
                else:
                    print("nonce fail, status code not 200, " + str(response.status_code))
                    response.failure(f'status_code:{str(response.status_code)}')
                    self.logger.error(f"/Test_API_domain/user/nonce nonce fail, status code not 200, {str(response.status_code)} {str(response.content)}")
            except Exception as e:
                response.failure("Exception :"+str(response.content))
                self.logger.error(f"/Test_API_domain/user/nonce Exception: {e}")
            return nonce

    def register(self, client, account, password, currency, device, type):

        nonce = platform_user.nonce(self, client)
        ptoken = 'None'
        path = self.api_url + "/Test_API_domain/user/accounts"
        payload = {
            "account": account,
            "password": func.encrypt(password).decode("utf-8"),
            "confirmPassword": func.encrypt(password).decode("utf-8"),
            "device": device,
            "inviteCode": "",
            "clientNonce": nonce,
            "currency": currency,
            "type": type
        }

        with client.post(path, json=payload, headers=self.header, catch_response=True) as response:
            try:
                if response.status_code == 200:
                    data = json.loads(response.text)
                    if data['code'] != 0 and data['code'] != 130002:
                        print(f"register fail, code not 0, data code: {str(data['code'])}, msg: {str(data['msg'])}")
                        response.failure(f"data code:{str(data['code'])}, msg:{str(data['msg'])}")
                        self.logger.error("/Test_API_domain/user/accounts register fail, code not 0, " + str(data))
                    else:
                        if data['code'] == 130002:
                            print(f"register name repeat. {str(response.text)}")
                            ptoken = data
                        else:
                            self.token = data['data']['token']
                            if data['data']['token'] == '' or data['data']['account'] != account:
                                response.failure("no token")
                                self.logger.error(f"/Test_API_domain/user/accounts {self.account} no token or account incorrect. {str(response.text)}")
                            else:
                                ptoken = str(self.token)
                else:
                    print("nonce fail, status code not 200, " + str(response.status_code))
                    response.failure(f'status_code:{str(response.status_code)}')
                    self.logger.error(f"/Test_API_domain/user/accounts register fail, status code not 200, {str(response.status_code)} {str(response.content)}")
            except Exception as e:
                response.failure("Exception :"+str(response.content))
                self.logger.error(f"/Test_API_domain/user/accounts Exception: {e}")
            return ptoken


if __name__ == '__main__':
    user = platform_user()

    user.api_url = settings.api_url

    ptoken = user.login(requests, 'qaqa9001', 'test1234')
    user.get_wallets_list(requests)

    # thirdparty = platform_thirdparty(ptoken)
    # stoken = thirdparty.login_sport(requests, 'qaqa9001')
    # business = product_business(stoken, 'qaqa9001')
    # inplay_list = business.bet(requests, sid=1, inplay=True)
    # print(stoken)
