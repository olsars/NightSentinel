import cv2
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from ultralytics import YOLO
from vision.events import send_event

app = FastAPI(title="NightSentinel Live Vision")

model = YOLO("yolo11n.pt")
alerted_tracks = set()


@app.get("/")
def index():
    return HTMLResponse("""
    <html>
    <head><title>NightSentinel Live Camera</title></head>
    <body style="background:#101820;color:white;text-align:center;font-family:Arial">
        <h1>NightSentinel — Live Detection</h1>
        <img src="/video" style="width:90%;max-width:1000px">
        <p>YOLO11 | Jetson Orin Nano | Logitech C920</p>
    </body>
    </html>
    """)


def generate_frames():
    results = model.track(
        source=0,
        device=0,
        classes=[0],
        conf=0.2,
        tracker="vision/botsort_reid.yaml",
        persist=True,
        stream=True,
        show=False,
        verbose=False,
    )

    try:
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    if box.id is None:
                        continue

                    track_id = int(box.id.item())

                    if track_id not in alerted_tracks:
                        print(f"[DETECTION] Track ID {track_id}", flush=True)

                        success = send_event(
                            track_id=track_id,
                            event_type="person_detected",
                            zone="front_door",
                        )

                        if success:
                            alerted_tracks.add(track_id)

            annotated = result.plot()
            success, jpeg = cv2.imencode(".jpg", annotated)

            if success:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + jpeg.tobytes()
                    + b"\r\n"
                )

    finally:
        if hasattr(results, "close"):
            results.close()


@app.get("/video")
def video():
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
