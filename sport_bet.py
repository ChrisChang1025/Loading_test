from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import json
import time

from locust import FastHttpUser, HttpUser, LoadTestShape, TaskSet, task, events, constant, run_single_user

from json.decoder import JSONDecodeError

import logging,datetime
import stomper, csv, socket

import Function.function as func
import tiger.user as tiger_user
import tiger.thirdparty as tiger_thirdparty
import sport.business as sport_business
import settings


platform_url = settings.api_url
ws_url = settings.ws_url
settings_sid = 1
settings_iid = '0'
settings_inplay = False
settings_date = '20231129'
settings_market = 'None'

# acc_list = func.generate_user_account(999)
acc_list = list()
running_param = dict()

headers = {
    'accept': '*/*',
    'Content-Type': 'application/json',
    'Referer': platform_url,
    'Time-Zone': 'GMT+8',
    'accept-language': 'zh-cn'
}
    
@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--usernamelist", type=str, env_var="LOCUST_USERNAME_LIST", default="qa11_1", help="It's working")
    parser.add_argument("--sid", type=int, env_var="LOCUST_SID", default=settings_sid, help="It's working")
    parser.add_argument("--iid", type=str, env_var="LOCUST_IID", default=settings_iid, help="It's working")
    parser.add_argument("--inplay", type=str, env_var="LOCUST_INPLAY", default=settings_inplay, help="It's working")
    parser.add_argument("--date", type=str, env_var="LOCUST_DATE", default=settings_date, help="It's working")
    parser.add_argument("--market", type=str, env_var="LOCUST_MARKET", default=settings_market, help="It's working")
    

@events.init.add_listener
def on_test_start(environment, runner, **kwargs):
    csv_path = f'./testdata/'
    login_brand_player_csv_path = f'{environment.parsed_options.usernamelist}.csv'
    settings_sid = environment.parsed_options.sid
    settings_iid = environment.parsed_options.iid
    settings_inplay = environment.parsed_options.inplay
    settings_date = environment.parsed_options.date
    settings_market = environment.parsed_options.market

    print(login_brand_player_csv_path)
    running_param['bet_sid'] = int(settings_sid)
    running_param['bet_iid'] = settings_iid
    running_param['bet_inplay'] = settings_inplay
    running_param['bet_date'] = settings_date
    if settings_market == '' or settings_market=='None':
        running_param['bet_market'] = 'None'
    else:
        running_param['bet_market'] = settings_market.split(',')
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
        self.login()
        # =========== market and odds dict for bet_from_stomp ===========
        self.market_dict = {}
        self.logger.info(f"{self.account} ptoken. {self.ptoken}")
        self.logger.info(f"{self.account} stoken. {self.stoken}")

    def login(self):        
        self.ptoken = self.platform_user.login(self.client, self.account, settings.password)
        self.thirdparty = tiger_thirdparty.platform_thirdparty(self.ptoken)
        self.stoken = self.thirdparty.login_sport(self.client, self.account)
        self.business = sport_business.product_business(stoken=self.stoken, username=self.account)

    @task(1)
    def bet_from_api(self):

        if self.business.bet_process(self.client, running_param) == '10203' :
            self.login()
        

    # @task(1)
    def extension(self):
        self.platform_user.extension(self.client)
   
# 5mins +3000 users , spawn_rate 20
class StagesShape(LoadTestShape):
    stages = func.caculate_stages(start_user=3000, end_user=80000, user_diff=3000, start_duration=300, duration_diff=300, spawn_rate=20)
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
    wait_time = constant(100)

if __name__ == "__main__":    
    run_single_user(EchoLocust)