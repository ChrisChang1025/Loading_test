from locust import HttpUser, TaskSet, task, events, constant, run_single_user

from prometheus_client import Metric, REGISTRY, exposition
from flask import request, Response
from locustCollector import LocustCollector

import logging
import csv, random, time

import Function.function as func
import tiger.user as tiger_user
import tiger.thirdparty as tiger_thirdparty
import tiger.thirdparty_report as tiger_thirdparty_report
import sport.game as sport_game
import function.settings as settings
from locust import LoadTestShape


acc_list = list()
running_param = dict()

    
@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--usernamelist", type=str, env_var="LOCUST_USERNAME_LIST", default="cashout_1", help="It's working")
    

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
        self.ptoken = self.platform_user.login(self.client, self.account, settings.password)
        if self.ptoken == 'None' or self.ptoken == '':
            self.ptoken = self.platform_user.login(self.client, self.account, settings.password)        
        self.thirdparty = tiger_thirdparty.platform_thirdparty(self.ptoken)
        self.stoken = self.thirdparty.login_sport(self.client, self.account)
        self.thirdparty_report = tiger_thirdparty_report.platform_thirdparty_report(self.ptoken)
        self.game = sport_game.product_game(self.stoken, self.account)
        self.orders = dict()
        self.ignore_orders=[]

    
    def get_user_orders_sport(self):
        if self.ptoken == 'None' or self.ptoken == '':
            return
        self.orders = self.thirdparty_report.get_user_sport_orders(self.client, date_type='today', bet_status=0, time_condition_type='BET') #未帶cursor預設抓到的最大數量為50筆

    @task
    def cashout(self):
        if self.ptoken == 'None' or self.ptoken == '' :
            return
        logging.info(f'{self.account} start get orders')
        self.get_user_orders_sport()
        logging.info(f'{self.account} end get orders. cnt:{len(self.orders["unSettlement"]["data"])}')
        for order in self.orders['unSettlement']['data']:
            if order['orderId'] not in self.ignore_orders:
                key = self.game.get_cashout_key(self.client, order['orderId'])
                if key is not None and key != '':
                    self.game.cashout(self.client, order['orderId'], key)
                else:
                    self.ignore_orders.append(order['orderId'])
                time.sleep(1)


class EchoLocust(HttpUser):
    
    tasks = [EchoTaskSet]
    host = settings.api_url
    # wait_time = constant(1)

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
    stages = caculate_stages(start_user=50, end_user=1500, user_diff=50, start_duration=180, duration_diff=180, spawn_rate=5)
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