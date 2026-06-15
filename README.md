# Docker Compose

Лабораторный проект с двумя отдельными Docker Compose-стеками:

- `flask_redis` - Flask-приложение с Redis и endpoint `/metrics`.
- `monitoring` - Prometheus, Grafana и Blackbox Exporter.

Главная идея проекта: приложение считает посещения в Redis, отдает метрику в формате Prometheus, а стек мониторинга собирает и показывает эти данные.
Сбор идет двумя способами: через Blackbox Exporter для HTTP-проверок и напрямую через endpoint `/metrics` приложения.

## Структура

```text
docker-compose/
├── flask_redis/
│   ├── app.py
│   ├── compose.yml
│   ├── dockerfile
│   └── requirements.txt
├── monitoring/
│   ├── compose.yml
│   ├── blackbox/
│   │   └── blackbox.yml
│   ├── grafana/
│   │   └── datasource.yml
│   └── prometheus/
│       └── prometheus.yml
└── debug_outputs/
    ├── docker_compose_ps_flask.txt
    ├── docker_compose_ps_mon.txt
    └── grafana_view_count_panel.JPG
```

## Flask + Redis

Папка: `flask_redis`.

Сервисы:

- `web` - Flask-приложение, собирается из локального `dockerfile`.
- `redis` - Redis из образа `redis:alpine`.

Оба сервиса имеют:

```yaml
restart: unless-stopped
```

Это значит: Docker будет поднимать контейнеры после перезапуска Docker daemon или сервера, пока пользователь сам явно их не остановит.

Приложение доступно на хосте:

```text
http://localhost:8000
```

Внутри контейнера Flask слушает порт `5000`, наружу проброшен порт `8000`:

```yaml
ports:
  - '8000:5000'
```

Flask подключается к Redis по имени сервиса:

```python
redis.Redis(host='redis', port=6379)
```

Внутри Docker Compose контейнеры видят друг друга по именам сервисов, поэтому `redis` здесь означает контейнер Redis.

## Endpoint приложения

Главная страница:

```text
GET /
```

Увеличивает счетчик `hits` в Redis и возвращает текст:

```text
Hello World! I have been seen N times.
```

Метрики:

```text
GET /metrics
```

Возвращает метрику Prometheus:

```text
# HELP view_count Flask-Redis-App visit counter
# TYPE view_count counter
view_count{service="Flask-Redis-App"} N
```

Важно: `/metrics` не увеличивает счетчик. Иначе Prometheus сам накручивал бы просмотры при каждом опросе.

## Запуск Flask + Redis

```bash
cd /home/ops/projects/docker-compose/flask_redis
docker compose up -d --build
```

`--build` нужен, если менялись `app.py`, `requirements.txt` или `dockerfile`.

Проверка:

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/metrics
```

Остановка:

```bash
docker compose down
```

## Monitoring

Папка: `monitoring`.

Сервисы:

- `prometheus` - собирает и хранит метрики.
- `grafana` - показывает dashboards и графики.
- `blackbox` - проверяет доступность HTTP/HTTPS-сервисов.

Доступные URL:

```text
Prometheus:        http://localhost:9090
Grafana:           http://localhost:3000
Blackbox Exporter: http://localhost:9115
```

Логин Grafana по умолчанию (задается в compose):

```text
admin / grafana
```

Запуск:

```bash
cd /home/ops/projects/docker-compose/monitoring
docker compose up -d
```

Остановка:

```bash
docker compose down
```

## Prometheus

Конфиг: `monitoring/prometheus/prometheus.yml`.

Prometheus собирает:

- собственные метрики Prometheus с `localhost:9090/metrics`;
- метрику Flask `view_count` с `host.docker.internal:8000/metrics`;
- HTTP-проверки через Blackbox Exporter.

`host.docker.internal` используется, чтобы контейнер Prometheus мог обращаться к сервису, опубликованному на хосте на порту `8000`.

### Job `view_total`

```yaml
- job_name: view_total
  metrics_path: /metrics
  scrape_interval: 15s
  scrape_timeout: 10s
  static_configs:
    - targets:
        - host.docker.internal:8000
      labels:
        service: Flask-Redis-App
```

`view_total` - это имя задания Prometheus.

`view_count` - это имя метрики, которую отдает Flask.

В Grafana для скорости посещений используется PromQL:

```promql
rate(view_count{job="view_total"}[30s])
```

Для общего значения счетчика:

```promql
view_count{job="view_total"}
```

## Blackbox Exporter

Конфиг Blackbox: `monitoring/blackbox/blackbox.yml`.

В нем настроены два модуля:

- `http_2xx` - обычная HTTP/HTTPS-проверка с проверкой TLS-сертификата.
- `http_2xx_insecure` - учебная проверка HTTPS без строгой проверки TLS-сертификата.

Обычные цели проверяются job `blackbox-http`:

```text
http://host.docker.internal:8000/
https://etis.psu.ru/
https://ya.ru/
https://www.amazon.com/
```

Цель с проблемной TLS-цепочкой вынесена в отдельный job `blackbox-http-insecure`:

```text
https://student.psu.ru
```

Для доступности сайта в Grafana нужно смотреть:

```promql
probe_success
```

`up` для blackbox показывает, что Prometheus смог опросить сам Blackbox Exporter. Реальный результат HTTP-проверки сайта показывает именно `probe_success`.

## DNS Blackbox

В `monitoring/compose.yml` для `blackbox` явно задан DNS:

```yaml
dns:
  - 192.168.1.57
```

Это сделано из-за долгого DNS lookup при проверках внешних сайтов. Вероятно, локальная особенность docker DNS.

## Grafana

Конфиг datasource: `monitoring/grafana/datasource.yml`.

Grafana автоматически подключает Prometheus:

```text
http://prometheus:9090
```

Это внутренний адрес Docker Compose. Контейнер Grafana обращается к контейнеру Prometheus по имени сервиса `prometheus`.

На dashboard с метриками Blackbox добавлена отдельная панель с нативной метрикой Flask:

```promql
rate(view_count{job="view_total"}[30s])
```

Dashboard может содержать разные метрики: Blackbox показывает доступность HTTP, а `view_count` показывает внутренний счетчик приложения.

## Памятка по изменениям

Если изменился `flask_redis/app.py`:

```bash
cd /home/ops/projects/docker-compose/flask_redis
docker compose up -d --build
```

Если изменился `monitoring/prometheus/prometheus.yml`:

```bash
cd /home/ops/projects/docker-compose/monitoring
docker compose restart prometheus
```

Если изменился `monitoring/blackbox/blackbox.yml`:

```bash
cd /home/ops/projects/docker-compose/monitoring
docker compose restart blackbox
```

Если изменился `monitoring/compose.yml`:

```bash
cd /home/ops/projects/docker-compose/monitoring
docker compose up -d
```

`docker compose up -d` читает compose-файл и создает или пересоздает контейнеры, если изменилась их конфигурация.

`docker compose restart <service>` просто перезапускает уже созданный контейнер, не меняя его конструкцию.

## Volumes

В `monitoring/compose.yml` используются named volumes:

- `prom_data` - данные Prometheus: временные ряды, WAL, служебное состояние.
- `grafana_data` - данные Grafana: настройки, dashboards, плагины, локальная база.

Обычный `docker compose down` не удаляет эти volumes.

Команда ниже удалит контейнеры вместе с данными:

```bash
docker compose down -v
```

Это удалит историю Prometheus и локальные данные Grafana.

## Debug Outputs

Папка `debug_outputs` содержит справочно сохраненные выводы команд, скриншоты и другие материалы для отладки или отчета.

Сейчас там лежат:

- `docker_compose_ps_flask.txt` - сохраненный вывод `docker compose ps` для стека Flask + Redis.
- `docker_compose_ps_mon.txt` - сохраненный вывод `docker compose ps` для стека мониторинга.
- `grafana_view_count_panel.JPG` - скриншот панели Grafana с метрикой `view_count`.
