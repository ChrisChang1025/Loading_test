import json
import time

from websocket import create_connection
from locust import FastHttpUser, TaskSet, task, events, constant, run_single_user

from json.decoder import JSONDecodeError
from locust.exception import InterruptTaskSet
import logging
from datetime import datetime, timezone, timedelta
import csv, socket, random, string, base64
from locustCollector import LocustCollector
from flask import request, Response
from prometheus_client import Metric, REGISTRY, exposition
from locust import LoadTestShape
from im.chat_ws import chat_ws as chat_ws
from im.chat_ws import Command as Command
from gevent import Timeout
import function.settings as settings
from locust.exception import StopUser

acc_list = list()
running_param = dict()

@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--usernamelist", type=str, env_var="LOCUST_USERNAME_LIST", default="local", help="It's working")

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

    csv_path = f'./testdata/'
    login_brand_player_csv_path = f'{environment.parsed_options.usernamelist}.csv'
    
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
        self.needConn = True
        self.ws = None
        # =========== basic object ===========
        self.account = acc_list.pop()
        self.token = self.login(self.account, self.account)
        
        self.ws_url = f"{settings.tp_ws_url}/ws/ws?token={self.token}"
        self.logger.info(f"{self.account} on_start. token:{self.token}")
        print(f"{self.account} on_start. token:{self.token}")

    def on_stop(self):
        if self.ws is not None and self.ws.connected == True:
            self.ws.close()
        raise StopUser()
    
    def ws_connect(self):
        try:
            self.logger.info(f"{self.account} ws_connect!")
            self.ws = create_connection(f"{self.ws_url}")         
            self.ws.recv()
            self.logger.info(f"{self.account} ws_connect_end!")
            events.request.fire(
                    request_type="WSS",
                    name=f'ws_connect',
                    response_time=0,
                    response_length=0,
                    exception=None,
                    context="request")
            
            self.needConn = False
        except Exception as e:
            print("=====Exception=====", e, "=====Exception End=====")
            
            msg = str(e)
            if '{' in msg and '}' in msg:
                index1 = msg.rfind('{')
                index2 = msg.rfind('}')
                ex_msg = msg[index1:index2+1]
            else:
                ex_msg = msg
            self.logger.error(f"{self.account} ws_connect ex: {e}")
            events.request.fire(
                        request_type=f'WSR',
                        name=f'ws_connect_error_{str(ex_msg)}',
                        response_time=0,
                        response_length=0,
                        exception=None,
                        context="request") 
            raise InterruptTaskSet(reschedule=False)

    def login(self, account, pwd):
        url = f"/tp/v1/login"
        headers = {
            "content-type":"application/json",
            "accept":"*/*",            
            "origin" : f"{settings.tp_url}"
        }
        payload = {
            "username": account,
            "password": pwd
        }
        api_starttime = datetime.now()
        with self.client.post(url, json=payload, headers=headers, catch_response=True) as response:
            api_endtime = datetime.now()
            response_sec = (api_endtime - api_starttime).seconds + ((api_endtime - api_starttime).microseconds)*0.000001
            try:
                if response.status_code == 200 :                
                    response_json = response.json()
                    if response_json["code"] == 200:
                        assert response_json["data"]["username"] == self.account
                        token = response_json["data"]["token"]
                        return token
                    else:
                        response.failure(f'login data_code not 200, data_code:{response_json["code"]}')
                    # print(response_json)
                else:
                    response.failure(f"login status_code not 200, status_code:{response.status_code}")
            except Exception as e:
                response.failure(f"Exception")
                self.logger.error(f"{self.account} login Exception {response.text}")

    @task
    def read_msg(self):    
        try:

            if self.needConn == True:
                self.ws_connect()               
            try :
                timeout = Timeout(1)
                timeout.start()           
                msg = self.ws.recv()
                local_receive_time = datetime.now().timestamp() #.utcnow()
                msg = msg.decode("utf-8") #.replace("\x00", '').replace("\x01", '').replace("\x04", '')

                index1 = msg.find('{')
                index2 = msg.rfind('}')
                msg = msg[index1:index2+1]
                json_msg = json.loads(msg)
                msg_time = json_msg['timestamp']

                msg_time = datetime.strptime(msg_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                msg_timestamp_gmt8 = msg_time.timestamp()

                time_diff =local_receive_time - (msg_timestamp_gmt8)
                if time_diff > 1:
                    events.request.fire(
                        request_type=f'WSR',
                        name=f'receive_message_delay_{int(time_diff)}s',
                        response_time=int(time_diff),
                        response_length=0,
                        exception=None,
                        context="request")
                    self.logger.info(f"diff:{time_diff}, local_receive_time:{local_receive_time}, msg time:{msg_timestamp_gmt8}, {json_msg} ")                
                else:
                    events.request.fire(
                        request_type="WSS",
                        name=f'receive_message',
                        response_time=int(time_diff),
                        response_length=0,
                        exception=None,
                        context="request")

                print(f"diff:{time_diff}, local_receive_time:{local_receive_time}, msg time:{msg_timestamp_gmt8}")
                
                self.needConn = False

            except Timeout:
                pass
            finally:
                timeout.cancel()

            self.ws.ping()

        except Exception as e:
            print(f"=====Exception====={str(e)} {msg}=====Exception End=====")
            
            if 'Handshake status 503 Service Unavailable' in str(e):
                error_name = f'receive_message_error_Handshake_status_503'
                error_msg = 'Handshake status 503 Service Unavailable'
            elif 'Handshake status 403 Forbidden' in str(e):
                error_name = f'receive_message_error_Handshake_status_403'
                error_msg = 'Handshake status 403 Forbidden'
            else:
                error_name = 'receive_message_error'
                error_msg = str(e)
            
            events.request.fire(
                request_type=f'WSR',
                name=f'{error_name}',
                response_time=0,
                response_length=0,
                exception=f'{error_msg}'
            )

            self.needConn = True
            self.logger.error(f"{self.account} ex: {str(e)}")

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

class StagesShape(LoadTestShape):
    stages = caculate_stages(start_user=20, end_user=500, user_diff=20, start_duration=180, duration_diff=180, spawn_rate=2)
    # stages = caculate_stages(start_user=5, end_user=500, user_diff=5, start_duration=300, duration_diff=300, spawn_rate=1)
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
    host = settings.tp_url

if __name__ == "__main__":
    run_single_user(EchoLocust)
    