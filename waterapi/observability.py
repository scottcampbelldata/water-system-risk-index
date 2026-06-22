"""Lightweight observability for the API: structured JSON logging, per-request
timing, in-memory metrics, and a global exception handler. No heavy dependencies
(no Prometheus/Sentry) so the service stays simple to run.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if isinstance(getattr(record, "extra_fields", None), dict):
            payload.update(record.extra_fields)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


class _Metrics:
    """Minimal in-memory request metrics (counts + latency samples per route)."""

    def __init__(self, max_samples: int = 1000) -> None:
        self.requests: dict[str, int] = defaultdict(int)
        self.status_classes: dict[str, int] = defaultdict(int)
        self.errors = 0
        self._latency: dict[str, list[float]] = defaultdict(list)
        self._max = max_samples

    def observe(self, route: str, status: int, duration_ms: float) -> None:
        self.requests[route] += 1
        self.status_classes[f"{status // 100}xx"] += 1
        if status >= 500:
            self.errors += 1
        samples = self._latency[route]
        samples.append(duration_ms)
        if len(samples) > self._max:
            del samples[0 : len(samples) - self._max]

    def snapshot(self) -> dict:
        def pct(values: list[float], p: float) -> float:
            if not values:
                return 0.0
            s = sorted(values)
            return round(s[min(len(s) - 1, int(p / 100 * len(s)))], 2)

        return {
            "total_requests": sum(self.requests.values()),
            "errors_5xx": self.errors,
            "status_classes": dict(self.status_classes),
            "by_route": {
                route: {
                    "count": self.requests[route],
                    "p50_ms": pct(self._latency[route], 50),
                    "p95_ms": pct(self._latency[route], 95),
                }
                for route in sorted(self.requests)
            },
        }


metrics = _Metrics()
logger = logging.getLogger("waterapi.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            route = _route_template(request)
            metrics.observe(route, 500, duration_ms)
            logger.error(
                "request failed",
                exc_info=True,
                extra={"extra_fields": {"method": request.method, "route": route, "status": 500, "duration_ms": round(duration_ms, 2)}},
            )
            return JSONResponse({"detail": "Internal server error"}, status_code=500)
        duration_ms = (time.perf_counter() - start) * 1000
        route = _route_template(request)
        metrics.observe(route, response.status_code, duration_ms)
        logger.info(
            "request",
            extra={"extra_fields": {"method": request.method, "route": route, "status": response.status_code, "duration_ms": round(duration_ms, 2)}},
        )
        return response


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)
