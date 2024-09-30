from locust import HttpUser, TaskSet, task, events, constant, run_single_user

from json.decoder import JSONDecodeError

import logging
import csv

import Function.function as func
import tiger.user as tiger_user

import function.settings as settings

acc_list = list()
running_param = dict()

@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--usernamelist", type=str, env_var="LOCUST_USERNAME_LIST", default="local", help="It's working")

@events.init.add_listener
def on_test_start(environment, runner, **kwargs):
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
        
        self.account = acc_list.pop()
        
        self.platform_user = tiger_user.platform_user()
        self.platform_user.api_url = settings.api_url

    @task
    def login(self):
        self.ptoken = self.platform_user.login(self.client, self.account, settings.password)
        print(f"{self.account} login.")
        self.logger.info(f"{self.account} ptoken. {self.ptoken}")

class EchoLocust(HttpUser):
    
    tasks = [EchoTaskSet]
    host = ""
    wait_time = constant(1)

if __name__ == "__main__":    
    run_single_user(EchoLocust)