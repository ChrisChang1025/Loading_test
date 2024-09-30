from locust import HttpUser, TaskSet, task, events, constant, run_single_user


import logging
import random,json
import Function.function as func
import sport.business as sport
import function.settings as settings, csv
from locustCollector import LocustCollector
from prometheus_client import REGISTRY, exposition
from flask import request, Response
from locust import TaskSet, task, constant, FastHttpUser
from locust import LoadTestShape
import requests
from locust.exception import InterruptTaskSet
from datetime import datetime as dt
from datetime import timezone, timedelta

acc_list = list()
running_param = dict()
match_list = list()
match_info = dict()
settings_sid = 1
settings_iid = ''
settings_inplay = False
settings_date = '20231208'

headers = func.set_sport_header(environment=settings.env, vend=settings.vend)

def get_sport_tournaments(inplay, date, sid):
    if inplay==True:
        path = settings.api_url + f"/Test_API_domain/tournament/info?sid={sid}&inplay=true&sort=tournament"
    elif date !='None' and date !='':
        path = settings.api_url + f"/Test_API_domain/tournament/info?sid={sid}&inplay=False&sort=tournament&date={date}"        
    else:
        path = settings.api_url + f"/Test_API_domain/tournament/info?sid={sid}&inplay=False&sort=tournament&date=today" 
            
    response = requests.request("GET", path, headers=headers, json={})
    response_json = response.json()
    return response_json

def get_initial_data(param):
    if param['target_iid']=='':
        tournaments = get_sport_tournaments(bool(param['target_inplay']), param['target_date'], param['target_sid'])
        # print(tournaments)
        for tournament in tournaments['data']['tournaments']:        
            for match in tournament['matches']:
                iid = match['iid']
                match_list.append(iid)
    else:
        match_list.append(param['target_iid'])

@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--sid", type=int, env_var="LOCUST_SID", default=settings_sid, help="It's working")
    parser.add_argument("--iid", type=str, env_var="LOCUST_IID", default=settings_iid, help="It's working")
    parser.add_argument("--inplay", type=str, env_var="LOCUST_INPLAY", default=settings_inplay, help="It's working")
    parser.add_argument("--date", type=str, env_var="LOCUST_DATE", default=settings_date, help="It's working")
    parser.add_argument("--usernamelist", type=str, env_var="LOCUST_USERNAME_LIST", default="qa7_1", help="It's working")
    parser.add_argument("--dbvendor", type=str, env_var="LOCUST_USERNAME_LIST", default="pp1", help="It's working")

@events.init.add_listener
def on_test_start(environment, runner, **kwargs):
    if environment.web_ui and runner:   
        @environment.web_ui.app.route("/export/prometheus")
        def prometheus_exporter():
            registry = REGISTRY
            encoder, content_type = exposition.choose_encoder(request.headers.get('Accept'))
            if 'name[]' in request.args:
                registry = REGISTRY.restricted_registry(request.args.get('name[]'))
            body = encoder(registry)
            return Response(body, content_type=content_type)

        REGISTRY.register(LocustCollector(environment, runner))
    
    settings_sid = environment.parsed_options.sid
    settings_iid = environment.parsed_options.iid
    settings_inplay = environment.parsed_options.inplay
    settings_date = environment.parsed_options.date
    settings_db_vendor = environment.parsed_options.dbvendor

    running_param['target_sid'] = int(settings_sid)
    running_param['target_iid'] = settings_iid
    running_param['target_inplay'] = settings_inplay
    running_param['target_date'] = settings_date
    running_param['vendor'] = settings_db_vendor

    get_initial_data(running_param)

    running_param['usernamelist'] = environment.parsed_options.usernamelist

    csv_path = f'./testdata/'
    login_brand_player_csv_path = f'{environment.parsed_options.usernamelist}.csv'

    with open(csv_path + login_brand_player_csv_path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        for row in csv_reader:
            if row[0].strip() != '':
                acc_list.append(row[0].strip())
        print(f'============================= {len(acc_list)} accounts loaded.')
    
        
class EchoTaskSet(TaskSet):
    def on_start(self):
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        self.account = acc_list[random.choice(range(len(acc_list)))]
        self.api_url = settings.api_url
        self.sid = int(running_param['target_sid'])        
        self.inplay = bool(str(running_param['target_inplay']).lower() in ('true', '1', 't', 'y', 'yes'))   
        self.db_vendor = running_param['vendor']     
        iid_count = len(match_list)
        random_idx = random.choice(range(iid_count))
        self.iid = match_list[random_idx]
        match_data = self.get_sport_match_info()
        self.match_info = match_data['data']['data']
        self.content = [{
            "account": f"{self.db_vendor}_{self.account}",
            "transferType": -1, 
            "transferID": "",
            "currency": "CNY",
            "amountTotal": 23,
            "effectiveAmount": 0,
            "orderNum": "",
            "actionType": "NEW",
            "order": {},
            "useCoupon": False,
            "masterUuid": ""
        }]
        self.header = {
            "authorization" : "---------",
            "accept":"application/json"
        }
        

    def generate_random_hex(self,length):
        num = random.randrange(16 ** (length - 1), 16 ** length)
        hex_str = hex(num)[2:].upper()
        hex_str = hex_str.zfill(length)
        return hex_str

    def parse_odds(self,mk , odds_set):
        odds_lists = []

        if type(odds_set) is dict:
            k=''
            odds_info={}
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
                        odds_lists.append(odds_info)
        elif type(odds_set) is list:
            for i in range(0,len(odds_set)):
                    k=''
                    beton=''
                    odds=''                
                    
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
                            odds_lists.append(odds_info)
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
                            odds_lists.append(odds_info)
            
        return odds_lists

    def get_sport_match_info(self):
        if self.inplay == True:
            path = settings.api_url + f"/Test_API_domain/business/sport/inplay/match?sid={self.sid}&iid={self.iid}"
        else:
            path = settings.api_url + f"/Test_API_domain/business/sport/prematch/match?sid={self.sid}&iid={self.iid}"

        response = requests.request("GET", path, headers=headers, json={})
        response_json = response.json()
        return response_json
    
    @task
    def send_fake_order(self):
        self.account = acc_list[random.choice(range(len(acc_list)))]
        self.content[0]["account"] = f"{self.db_vendor}_{self.account}"
        self.generate_order()
        self.content[0]["orderNum"] = self.content[0]["masterUuid"] = self.order_content["uuid"]
        self.content[0]["amountTotal"] = self.order_content["ante"]
        self.content[0]["order"] = self.order_content
        self.content[0]["transferID"] = self.generate_random_hex(10)+ "-" + hex((int(dt.now().timestamp())))+ hex(int(self.account[4:]))
        path = self.api_url + "/Test_API_domain/payment/sport/transferV2"
        with self.client.post(path, json=self.content, headers=self.header, catch_response=True) as response:
            if response.status_code == 200:
                data = json.loads(response.text)
                if data['code'] != 1:
                    response.failure(f"data code:{str(data['code'])}, msg:{str(data['msg'])}")
                    self.logger.error(f"{self.content[0]['orderNum']}  fail, code not 1, " + str(data))
            else :
                response.failure(f"http code:{response.status_code}")
                self.logger.error(f"http code:{response.status_code}")
                    
    
    def generate_order(self):
        try:    
            tz = timezone(timedelta(hours=-4))
            self.order_content = {
                "id": int(self.iid),
                "gameType": 1,
                "createTime": "2023-07-24 04:45:09",
                "betTime": "2023-07-24 04:45:09",
                "device": random.choice(range(3)),
                "uuid": "230724044509-69cf0b",
                "username": f"{self.db_vendor}_{self.account}",
                "parlay": 1,
                "option": 1,
                "combination": None,
                "ante": 5.00,
                "totalAnte": 5.00,
                "effectiveTotalAnte": 0E-8,
                "mayWinAmount": 12.00,
                "netWin": None,
                "payout": 0E-8,
                "status": 2,
                "useCoupon": False,
                "parlayBet": False,
                "payoutTime": None,
                "cashOut": False,
                "marketType": "EU",
                "betOrderAdminDetailVOs": [
                {
                    "id": int(self.iid),
                    "runningTime": "",
                    "cashoutRunningTime": "",
                    "sid": int(self.sid),
                    "iid": int(self.iid),
                    "tid": self.match_info['tid'],
                    "kickOffTime": self.match_info['kickoffDT'],
                    "homeId": self.match_info['home']['id'],
                    "awayId": self.match_info['away']['id'],
                    "homeOdds": 0,
                    "awayOdds": 0,
                    "homeScore": 0,
                    "awayScore": 0,
                    "market": "ah",
                    "odds": 1.5100,
                    "betOn": "h",
                    "cancel": False,
                    "reason": "",
                    "won": 0,
                    "matchScore": "",
                    "outright": False,
                    "inplay": settings_inplay,
                    "period": 'not_started',
                    "stage": "",
                    "cashoutPeriod": "",
                    "cashoutStage": "",
                    "k": "1",
                    "specifier": "",
                    "outcome": "{\"k\":\"2\",\"a\":\"0.49\",\"h\":\"1.51\"}",
                    "probability": 0.682900,
                    "cashoutProbability": None,
                    "safeFlag": True,
                    "vendor": self.match_info['vd'],
                    "source": "unknown",
                    "orderPhase": "0",
                    "stoppageTime": 0,
                    "kickOff": self.match_info['kickoff'],
                    "scoreType": "NORMAL"
                }
                ],
                "platform": self.db_vendor,
                "currency": "CNY",
                "perNormalAmount": 5.00000000,
                "perCreditAmount": None,
                "normalAmount": 5.00000000,
                "couponAmount": None,
                "creditAmount": None,
                "payoutForNormal": 0E-8,
                "payoutForCoupon": None,
                "payoutForCredit": None,
                "mayWinAmountForNormal": 1.55000000,
                "mayWinAmountForCoupon": None,
                "mayWinAmountForCredit": None,
                "result": None,
                "safeFlag": True,
                "lastUpdateTime": 1690270160378
            }
            
           
            if self.inplay == True:
                scores = self.match_info['detail']['score'].split('-')
                self.order_content['betOrderAdminDetailVOs'][0]['homeScore'] = int(scores[0].strip())
                self.order_content['betOrderAdminDetailVOs'][0]['awayScore'] = int(scores[1].strip())
                self.order_content['betOrderAdminDetailVOs'][0]['orderPhase'] = "1"
                self.order_content['betOrderAdminDetailVOs'][0]['period'] = self.match_info['detail']['period']
            else:
                self.order_content['betOrderAdminDetailVOs'][0]['homeScore'] = 0
                self.order_content['betOrderAdminDetailVOs'][0]['awayScore'] = 0
                self.order_content['betOrderAdminDetailVOs'][0]['orderPhase'] = "4"
                self.order_content['betOrderAdminDetailVOs'][0]['period'] = "not_started"

            total_market_list = {
                'ah': ['a', 'h'],
                'ou': ['ov', 'ud'],
                'ah_1st': ['a', 'h'],
                'ou_1st': ['ov', 'ud']
            }
            
            select_market = random.choice(list(total_market_list.keys()))
            select_beton = random.choice(total_market_list[select_market])

            for mk, mk_value in self.match_info['market'].items():
                # if mk not in ('ou','ah','ou_1st','ah_1st'):
                #     continue
                if mk != select_market:
                    continue
                
                random_idx = random.randint(0, len(mk_value)-1)
                mk_set = mk_value[random_idx]
                if 'absK' in mk_set:
                    mk_set.pop('absK')

                odds_list = self.parse_odds(mk,mk_set)
                for odds_info in odds_list:
                        
                    if odds_info['beton'] != 'absK' and odds_info['beton'] == select_beton:

                        self.order_content['betOrderAdminDetailVOs'][0]['homeOdds'] = 0
                        self.order_content['betOrderAdminDetailVOs'][0]['awayOdds'] = 0                            
                        self.order_content['betOrderAdminDetailVOs'][0]['market'] = mk
                            
                        self.order_content['betOrderAdminDetailVOs'][0]['betOn'] = odds_info['beton']
                        self.order_content['betOrderAdminDetailVOs'][0]['k'] = odds_info['k']
                        self.order_content['betOrderAdminDetailVOs'][0]['outcome'] = str(mk_set).replace('\'', '\"')
                        
                        created_time = dt.now(tz).strftime("%Y-%m-%d %H:%M:%S")
                        create_timestamp = int(dt.now().timestamp())
                        self.order_content['createTime'] = self.order_content['betTime']=created_time
                        self.order_content['lastUpdateTime'] = create_timestamp
                        self.order_content['uuid'] = dt.now(tz).strftime("%Y%m%d%H%M%S")[2:] + '-' + self.generate_random_hex(6).lower()

                        if float(odds_info['odds'])==0.00:
                            new_odds = 1.09
                            print(self.order_content['uuid'])
                        else:
                            new_odds = float(odds_info['odds'])

                        self.order_content['betOrderAdminDetailVOs'][0]['odds'] = new_odds

                        ante = random.randint(5, 30)*1.000
                        mayWinAmount = ante*new_odds

                        self.order_content['ante'] = ante
                        self.order_content['totalAnte'] = ante
                        self.order_content['mayWinAmount'] = mayWinAmount

                        self.order_content['perNormalAmount'] = ante
                        self.order_content['normalAmount'] = ante
                        self.order_content['mayWinAmountForNormal'] = mayWinAmount  
                        break   
        except Exception as e:
            self.logger.error("Generate order error : " + e)


               
   

class EchoLocust(FastHttpUser):
    tasks = [EchoTaskSet]
    host = settings.api_url
    wait_time = constant(1)

class StagesShape(LoadTestShape):
    stages = func.caculate_stages(start_user=500, end_user=20000, user_diff=500, start_duration=180, duration_diff=180, spawn_rate=10)
    print(stages)

    def tick(self):
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                try:
                    tick_data = (stage["users"], stage["spawn_rate"], stage["user_classes"])
                except:
                    tick_data = (stage["users"], stage["spawn_rate"])
                return tick_data

if __name__ == "__main__": 
    # get_initial_data()
    # print(get_sport_tournaments(True, datetime.now().date() + timedelta(days=1), 1))
    run_single_user(EchoLocust)
    # print(get_sport_match_info(False, 1, '9541004'))
    