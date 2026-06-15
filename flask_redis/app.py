import socket
import time

import redis
from flask import Flask, make_response

app = Flask(__name__)

# В Docker Compose и Kubernetes имя redis разрешается через DNS.
# В Kubernetes это будет имя Service.
cache = redis.Redis(
    host="redis",
    port=6379,
)


def get_hit_count() -> int:
    """Прочитать счётчик без его увеличения."""

    return int(cache.get("hits") or 0)


def incr_hit_count() -> int:
    """Увеличить счётчик, повторяя подключение при временной ошибке."""

    retries = 5

    while True:
        try:
            return cache.incr("hits")

        except redis.exceptions.ConnectionError as exc:
            if retries == 0:
                raise exc

            retries -= 1
            time.sleep(0.5)


@app.route("/metrics")
def metrics():
    metrics_text = f"""# HELP view_count Flask-Redis-App visit counter
# TYPE view_count counter
view_count{{service="Flask-Redis-App"}} {get_hit_count()}
"""

    response = make_response(metrics_text, 200)
    response.mimetype = "text/plain"
    return response


@app.route("/")
def index():
    count = incr_hit_count()
    pod_name = socket.gethostname()

    response_text = (
        "Hello from Kubernetes!\n"
        f"Pod: {pod_name}\n"
        f"Visits: {count}\n"
    )

    response = make_response(response_text, 200)
    response.mimetype = "text/plain"
    return response
