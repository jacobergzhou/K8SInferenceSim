from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
import os, time, signal, threading

app = FastAPI(title="Inference Simulator", version="0.1.0")

# Tunables (can be overridden by env/ConfigMap)
INFER_MS = int(os.getenv("INFER_MS", "80"))          # simulated work per request (ms)
BUSY_WAIT = os.getenv("BUSY_WAIT", "1") == "1"       # use CPU spin (helps CPU-based HPA see load)
READY_DELAY = int(os.getenv("READY_DELAY", "2"))     # seconds before being "ready" on startup
SHUTDOWN_GRACE = float(os.getenv("SHUTDOWN_GRACE", "5"))  # seconds to finish inflight on SIGTERM

_ready = False
_inflight = 0
_lock = threading.Lock()

def busy_work(ms: int):
    if BUSY_WAIT:
        end = time.perf_counter() + ms / 1000.0
        x = 0.0
        while time.perf_counter() < end:
            x += 1.0  # meaningless math to burn CPU
        return x
    else:
        time.sleep(ms / 1000.0)

def _startup_delay():
    global _ready
    time.sleep(READY_DELAY)
    _ready = True

def _on_sigterm(signum, frame):
    # Stop accepting new traffic via readiness but allow in-flight to finish
    global _ready
    _ready = False
    time.sleep(SHUTDOWN_GRACE)

signal.signal(signal.SIGTERM, _on_sigterm)

@app.on_event("startup")
def _on_startup():
    threading.Thread(target=_startup_delay, daemon=True).start()

@app.get("/healthz")
def healthz():
    return JSONResponse({"status": "ok"})

@app.get("/readyz")
def readyz():
    return JSONResponse({"ready": _ready}, status_code=200 if _ready else 503)

@app.get("/infer")
def infer():
    global _inflight
    with _lock:
        _inflight += 1
    try:
        busy_work(INFER_MS)
        return JSONResponse({"ok": True, "infer_ms": INFER_MS, "busy_wait": BUSY_WAIT})
    finally:
        with _lock:
            _inflight -= 1

@app.get("/metrics")
def metrics():
    # Minimal text metrics (not Prometheus format)
    return Response(f"ready={int(_ready)} inflight={_inflight}\n", media_type="text/plain")
