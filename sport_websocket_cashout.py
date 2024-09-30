from websocket import create_connection
from locust import FastHttpUser, LoadTestShape, TaskSet, task, events, constant, run_single_user
from locust.exception import InterruptTaskSet, StopUser
from prometheus_client import Metric, REGISTRY, exposition
from locustCollector import LocustCollector
from flask import request, Response
from json.decoder import JSONDecodeError
import settings
import logging
import stomper
import csv
import Function.function as func
import tiger.user as tiger_user
import tiger.thirdparty as tiger_thirdparty
import json
import time
from datetime import datetime as dt
from gevent import Timeout

acc_list = list()
running_param = dict()

settings_iid = 1967060


@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--usernamelist", type=str, env_var="LOCUST_USERNAME_LIST", default="qa6_1", help="It's working")
    parser.add_argument("--iid", type=str, env_var="LOCUST_IID", default=settings_iid, help="It's working")


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
    running_param['iid'] = environment.parsed_options.iid

    print('running_param:', running_param)
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

        self.need_conn = True
        self.ws = None
        # =========== basic object ===========
        self.account = acc_list.pop()
        self.ptoken = ''
        self.ws_url = settings.ws_url
        self.platform_url = settings.platform_url
        self.api_url = settings.api_url
        self.platform_user = tiger_user.platform_user()
        self.platform_user.api_url = settings.api_url
        self.last_msg_time = 0
        self.iid = running_param['iid']
        self.logger.info(f"start {self.account}")      
        self.extension_time = round(time.time() * 1000)

    def on_stop(self):
        if self.ws is not None and self.ws.connected == True:
            self.disconnect()
            self.ws.close()
        # raise StopUser()

    def disconnect(self):
        print(f"{self.account} send disconnect!")
        logging.info(f"{self.account} send disconnect!")
        self.ws.send("DISCONNECT\nreceipt:1\n\n\x00")

    def get_orders_with_iid(self):
        # 這隻 API 可以 query 指定 iid 的注單，但注單投注金額需 > 100
        path = settings.api_url + "/Test_API_domain/ordersWithIid"
        payload = {
            "iid": self.iid
        }
        self.orders = []
        with self.client.get(path, params=payload, headers=self.sport_header, catch_response=True) as response:
            try:
                if response.status_code == 200:
                    data = json.loads(response.text)
                    if data['code'] != 0:
                        print(f"{self.account} get orders with iid {self.iid} , code not 0, data code: {str(data['code'])}, msg: {str(data['msg'])}")
                        response.failure(f"data code:{str(data['code'])}, msg:{str(data['msg'])}")
                        self.logger.error(f"{self.account} /Test_API_domain/business/bets/ordersWithIid get payment method fail, code not 0, " + str(data))
                    else:
                        self.orders = [d['uuid'] for d in data['data']['orders']]
                        if len(self.orders) <= 0:
                            self.logger.info(f'{self.account} no orders.')
                            response.failure('account no orders.')
                        else:
                            self.logger.info(f'{self.account} /Test_API_domain/business/bets/ordersWithIid orders length = {len(self.orders)}  orders = {str(self.orders)}')
                else:
                    print(f"{self.account} get orders with iid {self.iid} , status code not 200, {str(response.status_code)} {str(response.content)}")
                    response.failure(f'status_code:{str(response.status_code)}')
                    self.logger.error(f"{self.account} /Test_API_domain/business/bets/ordersWithIid get orders with iid {self.iid}, status code not 200, {str(response.status_code)} {str(response.content)}")
            except Exception as e:
                response.failure("Exception :"+str(response.content))
                self.logger.error(f"{self.account} /Test_API_domain/business/bets/ordersWithIid Exception: {e}")

    def cashout_subscribe(self):
        # subscribe cashout odds change events
        path = settings.api_url + "/Test_API_domain/cashout/subscribe"
        payload = self.orders
        with self.client.post(path, json=payload, headers=self.sport_header, catch_response=True) as response:
            try:
                if response.status_code == 200:
                    data = json.loads(response.text)
                    if data['code'] != 0:
                        print(f"{self.account} subscribe cashout event , code not 0, data code: {str(data['code'])}, msg: {str(data['msg'])}")
                        response.failure(f"data code:{str(data['code'])}, msg:{str(data['msg'])}")
                        self.logger.error(f"{self.account} /Test_API_domain/cashout/subscribe subscribe cashout event fail, code not 0, " + str(data))
                    else:
                        self.logger.info(f"{self.account} /Test_API_domain/cashout/subscribe cashout orders lenght = {len(data['data']['cashOut'])},  cashOut data = {str(data['data']['cashOut'])}")
                else:
                    print(f"{self.account} subscribe cashout event , status code not 200, ,  {str(response.status_code)} {str(response.content)}")
                    response.failure(f'status_code:{str(response.status_code)}')
                    self.logger.error(f"{self.account} /Test_API_domain/cashout/subscribe subscribe cashout event, status code not 200, {str(response.status_code)} {str(response.content)}")
            except Exception as e:
                response.failure("Exception :"+str(response.content))
                self.logger.error(f"{self.account} /Test_API_domain/cashout/subscribe Exception: {e}")

    def cashout_unsubscribe(self):
        # unsubscribe cashout odds change events
        path = settings.api_url + "/Test_API_domain/unsubscribe"
        payload = self.orders
        with self.client.post(path, json=payload, headers=self.sport_header, catch_response=True) as response:
            try:
                if response.status_code == 200:
                    data = json.loads(response.text)
                    if data['code'] != 0:
                        print(f"{self.account} unsubscribe cashout event , code not 0, data code: {str(data['code'])}, msg: {str(data['msg'])}")
                        response.failure(f"data code:{str(data['code'])}, msg:{str(data['msg'])}")
                        self.logger.error(f"{self.account} /Test_API_domain/cashout/unsubscribe unsubscribe cashout event fail, code not 0, " + str(data))
                else:
                    print(f"{self.account} unsubscribe cashout event , status code not 200, ,  {str(response.status_code)} {str(response.content)}")
                    response.failure(f'status_code:{str(response.status_code)}')
                    self.logger.error(f"{self.account} /Test_API_domain/cashout/unsubscribe unsubscribe cashout event, status code not 200, {str(response.status_code)} {str(response.content)}")
            except Exception as e:
                response.failure("Exception :"+str(response.content))
                self.logger.error(f"{self.account} /Test_API_domain/cashout/unsubscribe Exception: {e}")

    def connect_ws(self):
        try:
            # print("re-login platform and sport.")
            self.ptoken = self.platform_user.login(self.client, self.account, settings.password)
            if self.ptoken is None:
                self.ptoken = self.platform_user.login(self.client, self.account, settings.password)

            self.thirdparty = tiger_thirdparty.platform_thirdparty(self.ptoken)
            self.stoken = self.thirdparty.login_sport(self.client, self.account)
            if self.stoken is None:
                self.stoken = self.thirdparty.login_sport(self.client, self.account)
            self.sport_header = func.set_sport_header(environment=settings.env, vend=settings.vend, stoken=self.stoken)
            self.get_orders_with_iid()
            self.cashout_unsubscribe()
            self.cashout_subscribe()

            self.logger.info(f"{self.account} connect_ws!")
            self.ws = create_connection(f"{self.ws_url}/Test_API_domain/websocket/ws?referer={self.platform_url}&token={self.stoken}&device=mobile&region=CN")
            self.ws.send("CONNECT\naccept-version:1.0,1.1,2.0")

            msg = self.ws.recv()
            # print(msg)
            self.logger.info(f"{self.account} message = {msg}")

            self.need_conn = False
        except Exception as e:
            self.logger.error(f"{self.account} connect_ws Exception {str(e)}")
            self.stoken = self.thirdparty.login_sport(self.client, self.account)

    @task(1)
    def listen_cashout(self):
        try:
            if self.need_conn == True:
                self.connect_ws()

            timeout = Timeout(1)
            timeout.start()
            msg = self.ws.recv()
            # print(msg)
            if msg is not None and msg != '' and 'heart-beat' not in msg:

                self.ws.ping()
                self.ws.send('')
                
                topic = msg[msg.index('destination:'):msg.index('\ncontent-type')].replace('destination:', '')
                msg_list = msg.split('\n')
                msg_list.remove('MESSAGE')
                temp_str = json.loads(msg_list[-1].replace('\x00', ''))
                
                if int(dt.now().timestamp()) - self.last_msg_time > 60 :
                    self.last_msg_time = int(dt.now().timestamp())
                    if '/topic/order/cashout' in topic:
                        # print(f"TOPIC : {topic} , MESSAGE : {temp_str}")
                        # self.logger.info(f"{self.account} TOPIC : {topic} , MESSAGE : {temp_str}")
                        events.request.fire(
                            request_type="WSS",
                            name=f'Receive_Cashout_Message',
                            response_time=0,
                            response_length=0,
                            exception=None,
                            context="request")
                else :                    
                    self.logger.info(f"{self.account} TOPIC : {topic} , MESSAGE : {temp_str}")
                    events.request.fire(
                            request_type="WSS",
                            name=f'Receive_Duplicate_Message',
                            response_time=0,
                            response_length=0,
                            exception=None,
                            context="request")

        except JSONDecodeError as e:
            print(f"{self.account} =====JSONDecodeError Exception=====", e, "=====JSONDecodeError Exception End=====")
            events.request.fire(
                request_type=f'WSR',
                name=f'ReceiveMessageError_JSONDecodeError',
                response_time=0,
                response_length=0,
                exception=f'{e}',
                context=f"{e}")

            self.logger.error(f"{self.account} JSONDecodeError ex: {str(e)}", exc_info=True)
        except Timeout:
            # print('send ping pong')
            self.ws.ping()
            self.ws.send('')
        except Exception as e:
            print("=====Exception=====", e, "=====Exception End=====")
            self.logger.error(f"{self.account} ==Exception==: {str(e)}")
            self.need_conn = True
            if len(str(e)) < 40:
                error_msg = str(e)
            else:
                error_msg = str(e)[0:39]
            events.request.fire(
                request_type=f'WSR',
                name=f'ReceiveMessageError',
                response_time=0,
                response_length=0,
                exception=f'{error_msg}',
                context=f"{error_msg}"
            )
        finally:
            timeout.cancel()

class StagesShape(LoadTestShape):
    stages = func.caculate_stages(start_user=1000, end_user=8500, user_diff=500, start_duration=180, duration_diff=180, spawn_rate=10)
    step = {
                "duration": 8150, 
                "users": 9000, 
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

class EchoLocust(FastHttpUser):
    tasks = [EchoTaskSet]
    host = settings.api_url
    # wait_time = constant(1)

if __name__ == "__main__":
    run_single_user(EchoLocust)
