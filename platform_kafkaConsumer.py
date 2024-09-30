import traceback
from locust import FastHttpUser, TaskSet, task, events, constant, run_single_user
from locust.exception import InterruptTaskSet

from locust import stats as locust_stats, runners as locust_runners
from locustCollector import LocustCollector
from flask import request, Response
from prometheus_client import Metric, REGISTRY, exposition
from locust import LoadTestShape

import logging
import tiger.user as tiger_user
import tiger.payment as tiger_payment
import function.settings as settings
import Function.function as func
from kafka import KafkaConsumer
import time

platform_url = settings.platform_url
payment_info = dict()
running_param = dict()

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
    running_param['sum'] = 0

class EchoTaskSet(TaskSet):
    def on_start(self):
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        self.consumer = KafkaConsumer("Kafka_Topic", bootstrap_servers=settings.tiger_kafka, api_version=(2,5,0))

    @task(1)
    def kafka_poll(self):
        try: 
            message = self.consumer.poll(timeout_ms=1000)
            events.request.fire(request_type=f'KSS',
                                name=f'kafka_consumer_poll_success',
                                response_time=0,
                                response_length=0,
                                exception=None,
                                context=f"kafka consumer poll")
            if message:
                time.sleep(5)
                for tp, msg in message.items():
                    running_param['sum'] += len(msg)
                    self.logger.info(f"current sum : {running_param['sum']}")
                    # print("%s:%d:%d: key=%s value=%s" % (tp.topic, tp.partition,
                    #                               msg.offset, msg.key,
                    #                               msg.value))
                    # print(f"Received message: {message.value().decode('utf-8')}")        
        except Exception as ex:
            self.logger.error(traceback.format_exc())
            self.logger.error(f"Exception : {ex}")
            events.request.fire(
                request_type=f'KSR',
                name=f'kafka_consumer_poll_fail',
                response_time=0,
                response_length=0,
                exception=f'{ex}'
            )


class EchoLocust(FastHttpUser):

    tasks = [EchoTaskSet]
    host = settings.api_url
    wait_time = constant(60)


if __name__ == "__main__":
    run_single_user(EchoLocust)
