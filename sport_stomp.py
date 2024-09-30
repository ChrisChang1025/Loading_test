import json
import time, random

from websocket import create_connection

from locust import FastHttpUser, LoadTestShape, TaskSet, task, events, constant, run_single_user

from json.decoder import JSONDecodeError
import function.settings as settings
import logging,datetime
import stomper, csv, socket

import Function.function as func

from locust.exception import InterruptTaskSet, StopUser


settings_sid =1
settings_iid = 0
settings_inplay=1
settings_caculate_delay=0
acc_list = list()
running_param = dict()


@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--usernamelist", type=str, env_var="LOCUST_USERNAME_LIST", default="qa11_1", help="It's working")
    parser.add_argument("--sid", type=int, env_var="LOCUST_SID", default=settings_sid, help="It's working")
    parser.add_argument("--iid", type=int, env_var="LOCUST_IID", default=settings_iid, help="It's working")
    parser.add_argument("--inplay", type=bool, env_var="LOCUST_INPLAY", default=settings_inplay, help="It's working")
    parser.add_argument("--caculate_delay", type=int, env_var="LOCUST_CACULATE_DELAY", default=settings_caculate_delay, help="It's working")


@events.init.add_listener
def on_test_start(environment, runner, **kwargs):
    csv_path = f'./testdata/'
    login_brand_player_csv_path = f'{environment.parsed_options.usernamelist}.csv'
    settings_sid = environment.parsed_options.sid
    settings_iid = environment.parsed_options.iid
    settings_inplay = environment.parsed_options.inplay
    settings_caculate_delay = environment.parsed_options.caculate_delay

    running_param['sid'] = int(settings_sid)
    running_param['iid'] = int(settings_iid)
    running_param['inplay'] = int(settings_inplay)
    running_param['caculate_delay'] = int(settings_caculate_delay)  

    print('running_param:', running_param)
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
        
        self.need_conn = True
        self.ws = None
        # =========== basic object ===========
        self.account = acc_list.pop()
        self.ptoken = ''
        self.password = 'test1234'

        self.sid = running_param['sid']
        self.iid = running_param['iid']
        self.inplay = running_param['inplay']
        base_api_url = self.client.base_url
        self.ws_url = settings.ws_url
        self.platform_url = settings.platform_url
        self.api_url = settings.api_url

        print(f'====== {self.account} [{self.api_url}] [{self.platform_url}] [{self.ws_url}]======')
        self.headers= {            
            "referer": f"{self.platform_url}",
            "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4044.141 Safari/537.36",
            "devicemode": "Pixel 5",
            "apptype": 2,
            "device": 'mobile',
            "content-type": "application/json;charset=UTF-8",       
        }
        self.sport_headers = {            
            "referer": f"{self.platform_url}",
            "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4044.141 Safari/537.36",
            "devicemode": "Pixel 5",
            "apptype": 2,
            "device": 'mobile',
            "content-type": "application/json;charset=UTF-8",
            "currency": "CNY",
            "Time-Zone": "GMT-04:00"
        }

        self.login_tiger_sport()
        self.match_list = list()
        self.get_sport_tournaments()
        self.logger.info(f"start {self.account}")
        
        self.extension_time = round(time.time() * 1000)
        self.switch_time = round(time.time() * 1000)
        self.switch_type = 1 # 1:簡易盤, 2:總盤

    def login(self):
        url = f"/Test_API_domain/user/token"
        
        pwd = func.encrypt(self.password).decode("utf-8")        
        payload = {
            "account": self.account,
            "password": pwd,
            "device": "mobile",
            "clientNonce": None
        }

        with self.client.post(url, json=payload, headers=self.headers, catch_response=True) as response:
            try:
                if response.status_code == 200 :                
                    response_json = response.json()
                    if response_json["code"] == 0:
                        assert response_json["data"]["account"] == self.account
                        token = response_json["data"]["token"]
                        self.headers.update({"authorization": "Bearer " + str(token)})
                        return token
                    else:
                        self.logger.error(f'{self.account} login data_code not 200, data_code:{response_json["code"]} {str(response.text)}')
                        response.failure('data_code:'+str(response_json["code"]))
                else:
                    self.logger.error(f"{self.account} login status_code not 200, status_code:{response.status_code} {str(response.text)}")
                    response.failure('status_code:'+str(response.status_code))
            except Exception as e:
                response.failure(f"Exception {response.text}")
                self.logger.error(f"{self.account} login Exception {str(response.text)}")
    
    def login_sport(self):
        path = f"/Test_API_domain/thirdparty/game/entry?providerCode=1&device=mobile"
        payload = {
        }  
        stoken = ''
        with self.client.get(path, json=payload, headers=self.headers, catch_response=True) as response:
            try:
                if response.status_code == 200 :
                    data = response.json()
                    if data['code'] == 0:
                        stoken = data['data']['token']
                        self.sport_headers.update({"authorization": "Bearer " + str(stoken)})
                        
                    else:
                        self.logger.error(f'{self.account} /Test_API_domain/thirdparty/game/entry data_code not 200, data_code:{data["code"]} {str(response.text)}')
                        response.failure('data_code:'+str(data["code"]))
                else:
                    self.logger.error(f"{self.account} /Test_API_domain/thirdparty/game/entry status_code not 200, status_code:{response.status_code} {str(response.text)}")
                    response.failure('status_code:'+str(response.status_code))
            except Exception as e:
                response.failure(f"Exception {response.text}")
                self.logger.error(f"{self.account} /Test_API_domain/thirdparty/game/entry Exception {response.text}")

            return stoken

    def on_stop(self):
        if self.ws is not None and self.ws.connected == True:
            self.ws.close()
        raise StopUser()
        

    def get_sport_tournaments(self):
        self.match_list = list()
        if self.inplay==True:
            path = f"/Test_API_domain/info?sid={self.sid}&inplay=true&sort=tournament&language=zh-cn"         
        else:
            path = f"/Test_API_domain/info?sid={self.sid}&inplay=False&sort=tournament&date=today&language=zh-cn" 
        
        with self.client.get(path, headers=self.sport_headers, catch_response=True) as response:
            if response.status_code == 200 :
                data = response.json()
                
                if data['code'] == 0:
                    for t in data['data']['tournaments']:
                        for m in t['matches']:
                            self.match_list.append(m['iid'])
                elif data['code'] != 0:
                    response.failure(f"data_code:{str(data['code'])}")
                    self.logger.error(f"{self.account} info code is not 0. code:{str(data['code'])} {str(response.text)}")
                
            else:                    
                response.failure(f'status_code:{str(response.status_code)}')
                self.logger.error(f"{self.account} status_code is not 200. status_code:{str(response.status_code)} {str(response.text)}")

            print(f"====== {self.account} match_list:{self.match_list}")

    def disconnect(self):
        print(f"{self.account} send disconnect!")
        logging.info(f"{self.account} send disconnect!")
        self.ws.send("DISCONNECT\nreceipt:1\n\n\x00")

    def login_tiger_sport(self):
        logging.info(f"{self.account} login")
        self.ptoken = self.login()
        if self.ptoken != None and self.ptoken != '' and self.ptoken != 'None':
            self.stoken = self.login_sport()
        else:
            self.stoken = None

        if self.stoken == None or self.stoken == '' or self.stoken == 'None':
            logging.error(f"{self.account} token empty! ptoken:{self.ptoken} , stoken:{self.stoken}")
            sleep_sec = random.randint(300, 600)
            logging.info(f"{self.account} sleep {sleep_sec} sec")
            time.sleep(sleep_sec)
            logging.info(f"{self.account} sleep finish")
        else:
            logging.info(f"{self.account} ptoken:{self.ptoken} , stoken:{self.stoken}")
    
    def connect_ws(self):
        try:
            self.logger.info(f"{self.account} connect_ws!")
            sub_id = 1
            self.ws = create_connection(f"{self.ws_url}/Test_API_domain/ws?referer={self.platform_url}&token={self.stoken}&device=mobile&region=CN")                
            self.ws.send("CONNECT\naccept-version:1.0,1.1,2.0")
            sub = stomper.subscribe(f"/topic/odds-diff/match/111111", sub_id, ack="auto")
            self.ws.send(sub)
            
            msg = self.ws.recv()
            self.subscribe_matches()
            self.need_conn = False
        except Exception as e:
            self.logger.error(f"{self.account} connect_ws Exception {str(e)}")
            self.login_tiger_sport()
            

    def subscribe_matches(self, target_iid=''):
        
        if target_iid == '':
            for iid in self.match_list:                
                sub_id = 'o_'+str(iid)                
                sub = stomper.subscribe(f"/topic/odds-diff/match/{iid}", sub_id, ack="auto")
                self.ws.send(sub)

                sub_id = 'i_'+str(iid)
                sub = stomper.subscribe(f"/topic/match/inplay/info/{iid}", sub_id, ack="auto")
                self.ws.send(sub)
        else:            
            sub_id = 'o_'+str(target_iid)
            sub = stomper.subscribe(f"/topic/odds-diff/match/{target_iid}", sub_id, ack="auto")
            self.ws.send(sub)

            sub_id = 'i_'+str(target_iid)
            sub = stomper.subscribe(f"/topic/match/inplay/info/{target_iid}", sub_id, ack="auto")
            self.ws.send(sub)
       
    def unsubscribe(self, target_iid=''):
        if target_iid == '':
            tmp_list = self.match_list.copy()
            # self.match_list.clear()
            for iid in tmp_list:                
                sub_id = 'o_'+str(iid)
                sub = stomper.unsubscribe(sub_id)
                self.ws.send(sub)

                sub_id = 'i_'+str(iid)
                sub = stomper.unsubscribe(sub_id)
                self.ws.send(sub)            
            
        elif target_iid != '' and target_iid in self.match_list:            
            sub_id = 'o_'+str(target_iid)
            sub = stomper.unsubscribe(sub_id)
            self.ws.send(sub)

            sub_id = 'i_'+str(target_iid)
            sub = stomper.unsubscribe(sub_id)
            self.ws.send(sub)

    @task(50)
    def stomp(self):
        
        # if self.stoken == 'None' or self.stoken == '' or self.stoken == None:
        #     self.logger.error(f"{self.account} login fail. stoken is None or empty. InterruptTaskSet. stoken={self.stoken}")
        #     raise InterruptTaskSet(reschedule=False)   
        
        try:
            
            if self.need_conn == True:                
                self.connect_ws()

            self.ws.settimeout(20.0)            
            msg = self.ws.recv()
            if running_param['caculate_delay'] == 1:
                local_receive_time = round(time.time() * 1000)

            if msg is not None and msg != '' and 'heart-beat' not in msg :
                
                self.ws.ping()
                self.ws.send('')

                topic = msg[msg.index('destination:'):msg.index('\ncontent-type')].replace('destination:', '')
                msg_list = msg.split('\n')
                msg_list.remove('MESSAGE')
                temp_str = json.loads(msg_list[-1].replace('\x00',''))
                # print(topic)
                events.request.fire(
                        request_type="WSS",
                        name=f'Receive_Message',
                        response_time=0,
                        response_length=0,
                        exception=None,
                        context="request")
                    
                if '/topic/match/event/' in topic:                            
                    for m in temp_str:
                        if m['sid']==self.sid and m['status'] in (3,8) and m['iid'] not in self.match_list: # 開賽
                                    print(f'========== new match {m["iid"]}, status: {m["status"]}, sid:{m["sid"]}')
                                    logging.info(f'{self.account} new match {m["iid"]}')
                                    self.subscribe_matches(m['iid'])
                                    self.match_list.append(m['iid'])
                        elif m['sid']==self.sid and m['status'] in (1,2,4,6,7): #取消, unsubscribe
                                    
                                    if m['iid'] in self.match_list:
                                        print(f'========== remove match {m["iid"]}, status: {m["status"]}, sid:{m["sid"]}')
                                        logging.info(f'{self.account} remove match {m["iid"]}')
                                        self.unsubscribe(m['iid'])
                                        self.match_list.remove(m['iid'])

                if running_param['caculate_delay'] == 1 and 'timestamp' in msg:
                        if 'timestamp' in msg_list[0]:
                                stomp_sent_time = float(msg_list[0].replace('timestamp:',''))
                        elif 'timestamp' in msg_list[-1]: # timestamp in stomp message content                       
                                stomp_sent_time = float(temp_str['timestamp'])
                        else:
                                stomp_sent_time = 0000000000000
                            
                        diff = (local_receive_time - stomp_sent_time) / 1000
                            
                        if diff >5 :
                            range1 = (int(diff/10)) * 10
                            range2 =  (int(diff/10) + 1) * 10

                            if diff < 10:
                                range1 = 5

                            events.request.fire(
                                request_type=f'WSS',
                                name=f'Receive_delay{topic}_{range1}s_{range2}s',
                                response_time=diff,
                                response_length=0,
                                exception=None,
                                context="request")

                
            if round(time.time() * 1000) > self.switch_time+300000:
                # 模擬進入總盤的行為, 取消訂閱所有賽事, 重新訂閱單一賽事                
                self.logger.info(f'{self.account} switch !!!!! , original:{self.switch_type}')
                if self.switch_type==1:
                    # 目前簡易盤, 切換至總盤
                    self.switch_type =2
                    
                    self.unsubscribe()
                    tmp_list = self.match_list.copy()
                    self.match_list.clear()
                    if len(tmp_list)>0:
                        self.detail_iid = random.choice(tmp_list)
                        self.subscribe_matches(self.detail_iid)
                        self.match_list.append(self.detail_iid)
                    else:
                        self.detail_iid = 0
                        self.logger.info(f'{self.account} match size is 0')

                elif self.switch_type==2: # 目前總盤, 切換至簡易盤
                    self.switch_type =1
                    if self.detail_iid != 0 and self.detail_iid in self.match_list:
                        self.unsubscribe(self.detail_iid)
                        self.match_list.remove(self.detail_iid)

                    self.get_sport_tournaments()
                    self.subscribe_matches()
        
                self.switch_time = round(time.time() * 1000)
            
            if round(time.time() * 1000) > self.extension_time+900000:
                self.logger.info(f'{self.account} extension')
                self.extension()
                self.extension_time = round(time.time() * 1000)
                 

        except JSONDecodeError as e:
            print(f"{self.account} =====JSONDecodeError Exception=====", e, "=====JSONDecodeError Exception End=====")

            events.request.fire(
                request_type=f'WSR',
                name=f'ReceiveMessageErr_JSONDecodeError',
                response_time=0,
                response_length=0,
                exception=f'{e}')

            self.logger.error(f"{self.account} JSONDecodeError ex: {str(e)}", exc_info=True)


        except Exception as e:
            print("=====Exception=====", e, "=====Exception End=====")
            self.logger.error(f"{self.account} ==Exception==: {str(e)}")
            self.need_conn = True
            if len(str(e)) <40:
                error_msg = str(e)
            else:
                error_msg = str(e)[0:39]
            
            events.request.fire(
                request_type=f'WSR',
                name=f'ReceiveMessageErr_{error_msg}',
                response_time=0,
                response_length=0,
                exception=f'{error_msg}'
            )
    
    def extension(self):
        if self.ptoken != None and self.ptoken != '' and self.ptoken != 'None':
            path = "/Test_API_domain/user/token/extension"
            payload = {}
            headers = {
                 # confidential data
            }
            with self.client.put(path, json=payload, headers=headers, catch_response=True) as response:
                try:
                    if response.status_code == 200:
                        data = json.loads(response.text)
                        if data['code'] != 0:
                            response.failure(f"data code:{str(data['code'])}")
                    else:
                        response.failure(f'status_code:{str(response.status_code)}')
                except Exception as e:
                    response.failure(f"Exception {response.text}")

class StagesShape(LoadTestShape):
    stages = func.caculate_stages(start_user=1000, end_user=50000, user_diff=1000, start_duration=180, duration_diff=180, spawn_rate=10)
    # step = {
    #         "duration": 3600, 
    #         "users": 10000, 
    #         "spawn_rate": 10
    #     }
    # stages.append(step)
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
            
class EchoLocust(FastHttpUser):
    tasks = [EchoTaskSet]    
    host = settings.api_url
    # wait_time = constant(1)

if __name__ == "__main__":
    run_single_user(EchoLocust)