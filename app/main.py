"""
DevPulse — a small uptime & health-check service.

Theme: a DevOps team almost always ends up building a lightweight internal
tool to watch the health of the services it owns (an "UptimeRobot" you run
yourself). DevPulse IS that tool — and it is deployed using the exact same
production pipeline it would recommend for any other service: Docker, GKE,
Terraform, GitHub Actions with OIDC, and Prometheus/Grafana. Eating its own
dog food end to end.

What it does:
- POST /targets        register a URL to watch
- GET  /targets        list watched URLs and their last known status
- GET  /healthz        liveness probe for Kubernetes
- GET  /readyz         readiness probe (checks DB connectivity)
- GET  /metrics        Prometheus exposition format — scraped by Prometheus
A background scheduler pings every registered target every 30s, stores the
result in Postgres, and updates Prometheus gauges/counters.
"""
import os
import time
import threading
from contextlib import asynccontextmanager

import psycopg2
import requests
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, HttpUrl
from starlette.responses import Response

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "devpulse")
DB_USER = os.getenv("DB_USER", "devpulse")
DB_PASS = os.getenv("DB_PASS", "changeme")
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "30"))
DB_CONNECT_RETRIES = int(os.getenv("DB_CONNECT_RETRIES", "10"))
DB_CONNECT_RETRY_DELAY_SECONDS = float(os.getenv("DB_CONNECT_RETRY_DELAY_SECONDS", "2"))

# --- Prometheus metrics -----------------------------------------------------
CHECKS_TOTAL = Counter("devpulse_checks_total", "Total health checks performed", ["target"])
CHECK_FAILURES_TOTAL = Counter("devpulse_check_failures_total", "Total failed health checks", ["target"])
TARGET_UP = Gauge("devpulse_target_up", "1 if target responded with < 400 status, else 0", ["target"])
TARGET_LATENCY_SECONDS = Gauge("devpulse_target_latency_seconds", "Last observed response latency", ["target"])

_db_lock = threading.Lock()
scheduler = BackgroundScheduler()


def get_conn():
    return psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASS,
        cursor_factory=RealDictCursor,
    )


def wait_for_db():
    """
    Retries the DB connection on startup instead of crashing immediately.
    In docker-compose, Postgres accepting TCP connections can lag a couple
    of seconds behind the container reporting "started" -- without this,
    the app container can crash-loop once before settling, which is a
    confusing first impression in a live demo.
    """
    last_error = None
    for attempt in range(1, DB_CONNECT_RETRIES + 1):
        try:
            conn = get_conn()
            conn.close()
            return
        except psycopg2.OperationalError as exc:
            last_error = exc
            time.sleep(DB_CONNECT_RETRY_DELAY_SECONDS)
    raise RuntimeError(
        f"Could not reach Postgres at {DB_HOST} after {DB_CONNECT_RETRIES} attempts"
    ) from last_error


def run_checks():
    """Called by the scheduler: pings every registered target once."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, url FROM targets;")
        targets = cur.fetchall()
    conn.close()

    for t in targets:
        label = t["name"]
        start = time.monotonic()
        try:
            resp = requests.get(t["url"], timeout=5)
            latency = time.monotonic() - start
            up = 1 if resp.status_code < 400 else 0
            status_code = resp.status_code
        except requests.RequestException:
            latency = time.monotonic() - start
            up = 0
            status_code = None

        CHECKS_TOTAL.labels(target=label).inc()
        if not up:
            CHECK_FAILURES_TOTAL.labels(target=label).inc()
        TARGET_UP.labels(target=label).set(up)
        TARGET_LATENCY_SECONDS.labels(target=label).set(latency)

        with _db_lock:
            conn = get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO checks (target_id, status_code, is_up, latency_ms, checked_at)
                       VALUES (%s, %s, %s, %s, now())""",
                    (t["id"], status_code, bool(up), round(latency * 1000, 2)),
                )
            conn.commit()
            conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    wait_for_db()
    scheduler.add_job(run_checks, "interval", seconds=CHECK_INTERVAL_SECONDS, id="run_checks")
    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown(wait=False)


app = FastAPI(title="DevPulse", description="Self-hosted uptime monitoring API", lifespan=lifespan)


@app.get("/")
def root():
    # Bare "/" has no natural meaning for an API-only service -- without
    # this, hitting the base URL in a browser (the first thing anyone does
    # in a demo) shows an unhelpful bare 404 instead of pointing anywhere
    # useful.
    return {
        "service": "DevPulse",
        "docs": "/docs",
        "endpoints": ["/targets", "/healthz", "/readyz", "/metrics"],
    }


class Target(BaseModel):
    url: HttpUrl
    name: str


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    try:
        conn = get_conn()
        conn.close()
        return {"status": "ready"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/targets")
def add_target(target: Target):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO targets (name, url) VALUES (%s, %s) RETURNING id;",
            (target.name, str(target.url)),
        )
        new_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return {"id": new_id, "name": target.name, "url": str(target.url)}


@app.get("/targets")
def list_targets():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT t.id, t.name, t.url,
                   c.is_up, c.status_code, c.latency_ms, c.checked_at
            FROM targets t
            LEFT JOIN LATERAL (
                SELECT is_up, status_code, latency_ms, checked_at
                FROM checks WHERE target_id = t.id
                ORDER BY checked_at DESC LIMIT 1
            ) c ON true
            ORDER BY t.id;
        """)
        rows = cur.fetchall()
    conn.close()
    return rows


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
