#  Just for demo test framework structure. Already remove confidential data and function.

Master 執行時使用 master.py 可以在 Grafana 上留下執行紀錄
指令 : `locust -f master.py --master`

若是 Script 內容有使用 locustCollector 且已包入下列REGISTRY的Listener, 即可使用原 Script 當 master 
```
from locustCollector import LocustCollector

@events.init.add_listener
def on_test_start(environment, runner, **kwargs):
    if environment.web_ui and runner:
        @environment.web_ui.app.route("/export/prometheus")
        def prometheus_exporter():
            registry = REGISTRY
            encoder, content_type = exposition.choose_encoder(
                request.headers.get('Accept'))
            if 'name[]' in request.args:
                registry = REGISTRY.restricted_registry(
                    request.args.get('name[]'))
            body = encoder(registry)
            return Response(body, content_type=content_type)

        REGISTRY.register(LocustCollector(environment, runner))
```