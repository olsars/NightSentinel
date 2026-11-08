# NightSentinel dashboard

The FastAPI backend serves this dashboard directly. On the Jetson, run:

```bash
./.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Then open `http://<jetson-ip>:8000` from a laptop on the same trusted network.
The dashboard polls `/health` and `/events` and loads the annotated camera feed
from port `8080`. Run `vision/detector.py` with
`NIGHTSENTINEL_STREAM_ENABLED=1` to make the live feed available.
