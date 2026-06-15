import socket

import redis
from flask import Flask, make_response

app = Flask(__name__)

# Подключаемся к Redis по имени сервиса из compose.yml.
# Внутри docker compose контейнеры видят друг друга по именам сервисов.
cache = redis.Redis(host='redis', port=6379)


def get_hit_count() -> int:
    # Читаем текущее значение счетчика из Redis.
    # Если ключа hits еще нет, считаем, что посещений было 0.
    return int(cache.get('hits') or 0)


def incr_hit_count() -> int:
    # Увеличиваем счетчик посещений на 1.
    return cache.incr('hits')


@app.route('/metrics')
def metrics():
    # Endpoint для Prometheus.
    # Prometheus периодически нативно забирает отсюда метрики (мимо блекбокса)
    metrics_text = f'''# HELP view_count Flask-Redis-App visit counter
# TYPE view_count counter
view_count{{service="Flask-Redis-App"}} {get_hit_count()}
'''
    # make_response нужен, чтобы явно задать HTTP-ответ и его Content-Type.
    response = make_response(metrics_text, 200)
    response.mimetype = 'text/plain'
    return response


@app.route('/')
def hello():
    # Обычный пользовательский endpoint увеличивает счетчик посещений.
    incr_hit_count()
    count = get_hit_count()
    return 'Hello World! I have been seen {} times.'.format(count)
