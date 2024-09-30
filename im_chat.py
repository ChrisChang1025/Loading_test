import json
import time

from websocket import create_connection
from locust import HttpUser, TaskSet, task, events, constant, run_single_user

from json.decoder import JSONDecodeError
from locust.exception import InterruptTaskSet
import logging
from datetime import datetime as dt
import stomper, csv, socket, random, string, base64
from locustCollector import LocustCollector
from flask import request, Response
from prometheus_client import Metric, REGISTRY, exposition
from locust import LoadTestShape
import Function.function as func
import tiger.user as tiger_user
import tiger.thirdparty as tiger_thirdparty
from im.chat_ws import chat_ws as chat_ws
from im.chat_ws import Command as Command
from gevent import Timeout
import settings

acc_list = list()
running_param = dict()
settings_iid = '3061161'
sendmsg = '1'

@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--usernamelist", type=str, env_var="LOCUST_USERNAME_LIST", default="qa6_1", help="It's working")
    parser.add_argument("--iid", type=int, env_var="LOCUST_IID", default=settings_iid, help="It's working")
    parser.add_argument("--sendmsg", type=str, env_var="LOCUST_SENDMSG", default=sendmsg, help="It's working")

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
    settings_iid = environment.parsed_options.iid
    running_param['chat_iid'] = str(settings_iid)
    running_param['sendmsg'] = environment.parsed_options.sendmsg

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
        self.platform_user = tiger_user.platform_user()
        self.platform_user.api_url = settings.api_url
        self.ptoken = self.platform_user.login(self.client, self.account, settings.password)
        self.send_time = int(dt.now().timestamp())
        self.ws_url = f"{settings.imchat_ws_url}&lang=zh_CN&account={self.account}&referer={str(base64.b64encode(settings.platform_url.encode('utf-8')), 'utf-8')}" 
        self.chat_ws = chat_ws(running_param['chat_iid'])
        self.is_send_msg = str(running_param['sendmsg']).lower() in ('true', '1', 't', 'y', 'yes')
        self.logger.info(f"{self.account} login.")

    def on_stop(self):
        if self.ws is not None and self.ws.connected == True:
            self.ws.close()

    def ws_connect(self):
                
        self.ws = create_connection(f"{self.ws_url}",subprotocols=[self.ptoken]) 
        conn_msg = self.chat_ws.subscribe_chat()
        self.ws.send(conn_msg,opcode=0x2)
        msg = self.ws.recv()
        code, command, content = self.chat_ws.get_msg(msg)
        if code == 1 or code == 0:
            self.needConn = False
        else:
            self.logger.error(f"{self.account} stop test : code {code}")
            raise InterruptTaskSet(reschedule=False)

    @task
    def send_msg(self):
        try:
            if (dt.now().timestamp() - self.send_time) < 10:
                return
            if self.needConn == True:
                self.ws_connect()

            self.send_time =  int(dt.now().timestamp())
            contentTime = dt.fromtimestamp(self.send_time).strftime('%Y-%m-%d %H:%M:%S')
            if self.is_send_msg == True:
                msg = self.chat_ws.send_msg(content =  'robot%s'%contentTime   )
                self.ws.send(msg,opcode=0x2)
                events.request.fire(
                    request_type="WSS",
                    name=f'sendmsg',
                    response_time=0,
                    response_length=0,
                    exception=None,
                    context="request")
            self.ws.send(self.chat_ws.ping(),opcode=0x2)

        except Exception as e:
            self.logger.error(f"{self.account} sendmsg ex: {str(e)}")
            if 'Handshake status 503 Service Unavailable' in str(e):
                error_name = f'sendmsg_error_Handshake_status_503'
                error_msg = 'Handshake status 503 Service Unavailable'
            elif 'Handshake status 403 Forbidden' in str(e):
                error_name = f'sendmsg_error_Handshake_status_403'
                error_msg = 'Handshake status 403 Forbidden'
                self.ptoken = self.platform_user.login(self.client, self.account, settings.password)
                self.logger.info(f"{self.account} re-login.")
            else:
                error_name = 'sendmsg_error'
                error_msg = e
            events.request.fire(
                request_type=f'WSR',
                name=f'{error_name}',
                response_time=0,
                response_length=0,
                exception=error_msg,
                context="request")
            self.needConn = True

    @task
    def read_msg(self):    
        try:

            if self.needConn == True:
                self.ws_connect()               
            try :
                timeout = Timeout(1)
                timeout.start()                
                msg = self.ws.recv()
                local_receive_time = int(dt.now().timestamp())
                code, command, content = self.chat_ws.get_msg(msg)
                if command == Command.PUSH_MESSAGE.value:
                    try:
                        events.request.fire(
                                    request_type=f'WSS',
                                    name=f'receive_message',
                                    response_time=0,
                                    response_length=0,
                                    exception=None,
                                    context="request")
                    except Exception as e:
                        pass                

                self.needConn = False

            except Timeout:
                    pass
            finally:
                timeout.cancel()

        except Exception as e:
            print("=====Exception=====", e, "=====Exception End=====")
            
            if 'Handshake status 503 Service Unavailable' in str(e):
                error_name = f'receive_message_error_Handshake_status_503'
                error_msg = 'Handshake status 503 Service Unavailable'
            elif 'Handshake status 403 Forbidden' in str(e):
                error_name = f'receive_message_error_Handshake_status_403'
                error_msg = 'Handshake status 403 Forbidden'
                self.ptoken = self.platform_user.login(self.client, self.account, settings.password)
                self.logger.info(f"{self.account} re-login.")
            else:
                error_name = 'receive_message_error'
                error_msg = e
            
            events.request.fire(
                request_type=f'WSR',
                name=f'{error_name}',
                response_time=0,
                response_length=0,
                exception=f'{error_msg}'
            )

            self.needConn = True
            self.logger.error(f"{self.account} receive message ex: {str(e)}")


class EchoLocust(HttpUser):
    
    tasks = [EchoTaskSet]
    host = settings.platform_url

class StagesShape(LoadTestShape):
    stages = func.caculate_stages(start_user=200, end_user=4900, user_diff=100, start_duration=600, duration_diff=600, spawn_rate=10)
    step = {
            "duration": 86400, 
            "users": 5000, 
            "spawn_rate": 10
        }
    stages.append(step)
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
    run_single_user(EchoLocust)
    