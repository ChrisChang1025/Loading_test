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
from kafka import KafkaProducer
from datetime import datetime as dt

acc_list = list()
running_param = dict()
match_list = list()
match_info = dict()
settings_sid = 1
settings_iid = ''
settings_inplay = True
settings_date = '20230906'

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

def get_sport_match_info(inplay, sid, iid):
    if inplay == True:
        path = settings.api_url + f"/Test_API_domain/business/sport/inplay/match?sid={sid}&iid={iid}"
    else:
        path = settings.api_url + f"/Test_API_domain/business/sport/prematch/match?sid={sid}&iid={iid}"

    response = requests.request("GET", path, headers=headers, json={})
    response_json = response.json()
    return response_json

def parse_odds(mk , odds_set):
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

    running_param['target_sid'] = int(settings_sid)
    running_param['target_iid'] = settings_iid
    running_param['target_inplay'] = settings_inplay
    running_param['target_date'] = settings_date

    get_initial_data(running_param)
    
        
class EchoTaskSet(TaskSet):
    def on_start(self):
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)

        self.producer = KafkaProducer(value_serializer=lambda v:json.dumps(v).encode('utf-8'),bootstrap_servers=settings.tp_kafka)
        
        self.topic = 'inno.console.order.info'
        self.sid = int(running_param['target_sid'])
        self.inplay = bool(str(running_param['target_inplay']).lower() in ('true', '1', 't', 'y', 'yes'))
        

    def generate_random_hex(self,length):
        num = random.randrange(16 ** (length - 1), 16 ** length)
        hex_str = hex(num)[2:].upper()
        hex_str = hex_str.zfill(length)
        return hex_str

    @task
    def send_order(self):
        try:
            iid_count = len(match_list)

            random_idx = random.choice(range(iid_count))
            self.iid = match_list[random_idx]
            match_data = get_sport_match_info(sid=self.sid, iid=self.iid, inplay=self.inplay)
            self.match_info = match_data['data']['data']

            
            self.content = [ # confidential data
                            ]
            
           
            if self.inplay == True:
                scores = self.match_info['detail']['score'].split('-')
                self.content[0]['betOrderAdminDetailVOs'][0]['homeScore'] = int(scores[0].strip())
                self.content[0]['betOrderAdminDetailVOs'][0]['awayScore'] = int(scores[1].strip())
                self.content[0]['betOrderAdminDetailVOs'][0]['orderPhase'] = "1"
                self.content[0]['betOrderAdminDetailVOs'][0]['period'] = self.match_info['detail']['period']
            else:
                self.content[0]['betOrderAdminDetailVOs'][0]['homeScore'] = 0
                self.content[0]['betOrderAdminDetailVOs'][0]['awayScore'] = 0
                self.content[0]['betOrderAdminDetailVOs'][0]['orderPhase'] = "4"
                self.content[0]['betOrderAdminDetailVOs'][0]['period'] = "not_started"

            total_market_list = {
                'ah': ['a', 'h'],
                'ou': ['ov', 'ud'],
                'ah_1st': ['a', 'h'],
                'ou_1st': ['ov', 'ud']
            }
            
            select_market = random.choice(list(total_market_list.keys()))
            select_beton = random.choice(total_market_list[select_market])
            print(f'============= {self.iid} start, {select_market}===={select_beton}')

            for mk, mk_value in self.match_info['market'].items():
                # if mk not in ('ou','ah','ou_1st','ah_1st'):
                #     continue
                if mk != select_market:
                    continue
                
                random_idx = random.randint(0, len(mk_value)-1)
                mk_set = mk_value[random_idx]
                if 'absK' in mk_set:
                    mk_set.pop('absK')

                odds_list = parse_odds(mk,mk_set)
                for odds_info in odds_list:
                        
                    if odds_info['beton'] != 'absK' and odds_info['beton'] == select_beton:
                        print(odds_info)

                        self.content[0]['betOrderAdminDetailVOs'][0]['homeOdds'] = 0
                        self.content[0]['betOrderAdminDetailVOs'][0]['awayOdds'] = 0                            
                        self.content[0]['betOrderAdminDetailVOs'][0]['market'] = mk
                            
                        self.content[0]['betOrderAdminDetailVOs'][0]['betOn'] = odds_info['beton']
                        self.content[0]['betOrderAdminDetailVOs'][0]['k'] = odds_info['k']
                        self.content[0]['betOrderAdminDetailVOs'][0]['outcome'] = str(mk_set).replace('\'', '\"')

                        

                        for tmp in range(0, settings.kafka_count):
                            created_time = dt.now().strftime("%Y-%m-%d %H:%M:%S")
                            create_timestamp = int(dt.now().timestamp())
                            self.content[0]['createTime'] = self.content[0]['betTime']=created_time
                            self.content[0]['lastUpdateTime'] = create_timestamp
                            self.content[0]['uuid'] = dt.now().strftime("%Y%m%d%H%M%S")[2:] + '-' + self.generate_random_hex(6).lower()

                            if float(odds_info['odds'])==0.00:
                                new_odds = 1.09
                                print(self.content[0]['uuid'])
                            else:
                                new_odds = float(odds_info['odds'])

                            self.content[0]['betOrderAdminDetailVOs'][0]['odds'] = new_odds

                            ante = random.randint(5, 500)*1.000
                            mayWinAmount = ante*new_odds

                            self.content[0]['ante'] = ante
                            self.content[0]['totalAnte'] = ante
                            self.content[0]['mayWinAmount'] = mayWinAmount

                            self.content[0]['perNormalAmount'] = ante
                            self.content[0]['normalAmount'] = ante
                            self.content[0]['mayWinAmountForNormal'] = mayWinAmount


                            self.producer.send(self.topic, self.content)

                        print(f'send {settings.kafka_count} times, {mk} {odds_info}')
                        events.request.fire(
                                request_type="WSS",
                                name=f'Send_kafka_success',
                                response_time=0,
                                response_length=0,
                                exception=None,
                                context="request")


            
            
        except Exception as e:
            self.logger.error(f'error: {e}')
            events.request.fire(
                request_type=f'WSR',
                name=f'send_kafka_error{e}',
                response_time=0,
                response_length=0,
                exception=None,
                context="request")     
            self.logger.error(f'send kafka error : {e}')    
   

class EchoLocust(FastHttpUser):
    tasks = [EchoTaskSet]
    host = settings.api_url
    wait_time = constant(1)

class StagesShape(LoadTestShape):
    stages = [
        {"duration": 600, "users": 19, "spawn_rate": 1}
    ]

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
    