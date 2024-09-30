from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import json
import time

from locust import FastHttpUser, HttpUser, TaskSet, task, events, constant, run_single_user

from json.decoder import JSONDecodeError

import logging,datetime
from datetime import datetime, timedelta
import Function.function as func
import tiger.user as tiger_user
import tiger.thirdparty as tiger_thirdparty
import sport.business as sport_business
import socket, random, string, csv, uuid, requests
import settings

platform_url = settings.api_url
ws_url = settings.ws_url
input_setting = {"sid":1,"parlay":2}
acc_list = list()
running_param = list()

headers = {
    'accept': '*/*',
    'Content-Type': 'application/json',
    'Referer': settings.platform_url,
    'Time-Zone': 'GMT+8',
    'accept-language': 'zh-cn'
}

@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--usernamelist", type=str, env_var="LOCUST_USERNAME_LIST", default="qa11_1", help="It's working")
    parser.add_argument("--sid", type=int, env_var="LOCUST_SID", default=input_setting["sid"], help="It's working")
    parser.add_argument("--parlay", type=int, env_var="LOCUST_MARKET", default=input_setting["parlay"], help="It's working")

def get_sport_tournaments(inplay, date, sid):
    if inplay==True:
        path = settings.api_url + f"/Test_API_domain/tournament/info?sid={sid}&inplay=true&sort=tournament"
    elif date !='None' and date !='':
        path = settings.api_url + f"/Test_API_domain/tournament/info?sid={sid}&inplay=False&sort=tournament&date={date}"        
    else:
        path = settings.api_url + f"/Test_API_domain/tournament/info?sid={sid}&inplay=False&sort=tournament&date=today" 
    
    try:
        response = requests.request("GET", path, headers=headers, json={})
        if response.status_code==200:
            response_json = response.json()
        else:
            response_json = dict()
    except Exception as e:
        print(e)
        response_json = dict()
    
    
    return response_json

def get_sport_match_info(sid, iid):
    path = settings.api_url + f"/Test_API_domain/business/sport/prematch/match?sid={sid}&iid={iid}"

    try:
        response = requests.request("GET", path, headers=headers, json={})
        if response.status_code==200:
            response_json = response.json()
        else:
            response_json = dict()
    except Exception as e:
        print(e)
        response_json = dict()
        
    return response_json

def get_initial_data(sid):

    today = datetime.today()
    for i in range(1, 7):
        future_date = today + timedelta(days=i)
        new_date = future_date.strftime('%Y%m%d')
        tournaments = get_sport_tournaments(False, new_date, 1)
        if tournaments != {}:
            for tournament in tournaments['data']['tournaments']:        
                for match in tournament['matches']:
                    try:
                        iid = match['iid']
                        market = get_sport_match_info(sid, iid)
                        if "market" in market['data']['data'] and market['data']['data']['market'] != {}:
                            running_param.append(market['data']['data'])
                    except Exception as e:
                        print(e)   
    return running_param
   

@events.init.add_listener
def on_test_start(environment, runner, **kwargs):
    csv_path = f'./testdata/'
    login_brand_player_csv_path = f'{environment.parsed_options.usernamelist}.csv'
    input_setting['parlay'] = environment.parsed_options.parlay    
    input_setting['sid'] = environment.parsed_options.sid

    get_initial_data(input_setting['sid'])
    print(f'running_param = {len(running_param)}')
    with open(csv_path + login_brand_player_csv_path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')        
        for row in csv_reader:
            if row[0].strip() != '':
                acc_list.append(  row[0].strip() )            

        print(f'============================= {len(acc_list)} accounts loaded.')
        
class EchoTaskSet(TaskSet):
    def on_start(self):
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        # =========== basic object ===========
        self.account = acc_list.pop()        
        self.platform_user = tiger_user.platform_user()
        self.platform_user.api_url = settings.api_url
        self.login()
        self.header = func.set_sport_header(settings.env, settings.vend, self.stoken)
        
    def login(self):
        self.ptoken = self.platform_user.login(self.client, self.account, settings.password)
        self.thirdparty = tiger_thirdparty.platform_thirdparty(self.ptoken)
        self.stoken = self.thirdparty.login_sport(self.client, self.account)

    @task(1)
    def extension(self):
        self.platform_user.extension(self.client)

    @task(600)
    def bet_parlay(self):
        
        path = settings.api_url + f"/Test_API_domain/bet"
        parlay = [{
                         # confidential data
                    }]
        bet_payload = {
                         # confidential data
                    }
        
        with self.client.post(path, json=bet_payload, headers=self.header, catch_response=True) as response:
            try:    
                if response.status_code == 200 :
                    if response.json()['code'] == 0:
                        response.success()
                    elif response.json()['code'] == 10203:
                        self.login()
                    elif response.json()['code'] == 30533:
                        events.request.fire(
                                request_type=f'WSS',
                                name=f'Code : 30533',
                                response_time=0,
                                response_length=0,
                                exception=None,
                                context="request")
                    else:
                        response.failure(f"code:{str(response.json()['code'])} , msg:{str(response.json()['msg'])}")
                        self.logger.error(f"code:{str(response.json()['code'])}, msg:{str(response.json()['msg'])}\nbet payload: {bet_payload}")
                else:
                    response.failure(f"status_code:{str(response.status_code)}")     
                    self.logger.error(f"status_code:{str(response.status_code)}") 

            except Exception as e:
                response.failure(f"Exception {e}")  
                self.logger.error(f"Exception {e} bet \n payload: {bet_payload}")

    def generate_tickets(self, matchinfo_list, parlay_count):
        tickets = list()
        delete_idx = list()        

        match_idx = random.sample(range(0, len(matchinfo_list)), parlay_count)
        for idx in match_idx:
            match = matchinfo_list[idx]
            odds_set = random.choice(list(match['market'].keys()))
            odds = self.parse_odds(odds_set, match['market'][odds_set])
            if odds['odds'] == '0.00':
                running_param[idx] = self.get_sport_match_info(match['sid'], match['iid'])
                print(f'update match info {running_param[idx]}')

            tickets.append({ # confidential data
                })

        return tickets

    def parse_odds(self, mk , odds_set):
        
        odds_info={}
        if type(odds_set) is dict:
            k=''            
            odds_set.pop('absK', None)
            for tmpKey, tmpValue in odds_set.items():
                
                if tmpKey == 'k':
                    k=tmpValue
                else :
                    beton=tmpKey
                    odds=tmpValue                 
                    odds_info = {
                                'k': k,
                                'beton' : beton,
                                'odds': odds
                            }
                    return odds_info

        elif type(odds_set) is list:
            for i in range(0,len(odds_set)):
                k=''
                beton=''
                odds=''                
                odds_set[i].pop('absK', None)
                for tmpKey, tmpValue in odds_set[i].items():                   
                    odds_info={} # 紀錄整理完的賠率組合
                    if tmpKey=='k' and len(odds_set[i])>2 :
                        k=tmpValue
                    elif tmpKey=='k' and len(odds_set[i])==2 :
                        beton=tmpValue
                    elif tmpKey=='o' and len(odds_set[i])==2 :
                        odds=tmpValue
                        odds_info = {
                                'k': k,
                                'beton' : beton,
                                'odds': odds
                            }
                        return odds_info
                    else :
                        beton = tmpKey
                        odds = tmpValue                        
                        if beton == "a":
                            betk = k.replace("-", "+") if k[0] == "-" else k.replace("+", "-")
                        else :
                            betk = k
                            odds_info = {
                                'k': betk,
                                'beton' : beton,
                                'odds': odds
                            }
                            return odds_info
            
        return odds_info
    
    def get_sport_match_info(self, sid, iid):
        path = settings.api_url + f"/Test_API_domain/business/sport/prematch/match?sid={sid}&iid={iid}"

        try:
            response = requests.request("GET", path, headers=headers, json={})
            if response.status_code==200:
                response_json = response.json()
            else:
                response_json = dict()
        except Exception as e:
            print(e)
            response_json = dict()
            
        return response_json

class EchoLocust(FastHttpUser):
    
    tasks = [EchoTaskSet]
    host = settings.api_url
    wait_time = constant(1)


if __name__ == "__main__":    
    run_single_user(EchoLocust)
    # print(list(range(0,input_setting['parlay'])))
    # parse_odds('ah',[{'k': '-0.5/1', 'absK': '-0.5/1', 'a': '0.86', 'h': '1.04'}, {'k': '-0.5', 'absK': '-0.5', 'a': '1.12', 'h': '0.79'}],'a')