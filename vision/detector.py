
"""
NightSentinel - Vision Detection Module

Hardware: NVIDIA Jetson Orin Nano + Logitech C920
Model: YOLO11 Nano
Tracker: ByteTrack

Features:
- Real-time person detection
- GPU-accelerated inference
- Persistent tracking IDs across frames
- Automatic backend event notifications
- Duplicate alert prevention
"""

from ultralytics import YOLO
from events import send_event


def main():
    # Load the pretrained YOLO11 Nano model.
    model = YOLO("yolo11n.pt")

    # Store IDs that have already generated successful alerts.
    # This prevents repeated notifications for the same tracked person.
    alerted_tracks = set()

    print("[NightSentinel] Starting vision system...")

    # Start live camera detection and tracking.
    #
    # source=0: Logitech C920 at /dev/video0
    # device=0: NVIDIA Jetson GPU
    # classes=[0]: Detect people only
    # conf=0.5: Minimum 50% detection confidence
    # tracker: ByteTrack tracking algorithm
    # persist=True: Keep tracker state across frames
    # stream=True: Process video frames continuously
    # show=True: Don't open a graphical window
    results = model.track(
        source=0,
        device=0,
        classes=[0],
        conf=0.2,
        tracker="vision/botsort_reid.yaml",
        persist=True,
        stream=True,
        show=True,
        verbose=False,
    )

    try:
        # Process each frame received from the camera.
        for result in results:

            # Skip frames without detected objects.
            if result.boxes is None:
                continue

            # Process every detected person.
            for box in result.boxes:

                # Read the model's confidence score.
                confidence = float(box.conf.item())

                # A tracking ID may not be available immediately.
                if box.id is None:
                    continue

                track_id = int(box.id.item())

                print(
                    f"[DETECTION] Person detected | "
                    f"Track ID: {track_id} | "
                    f"Confidence: {confidence:.2f}"
                )

                # Only alert the backend once per tracked person.
                if track_id not in alerted_tracks:

                    print(
                        f"[ALERT] New person detected: "
                        f"Track ID {track_id}"
                    )

                    # Send the detection event to FastAPI.
                    success = send_event(
                        track_id=track_id,
                        event_type="person_detected",
                        zone="front_door",
                    )

                    # Remember this ID only after a successful request.
                    if success:
                        alerted_tracks.add(track_id)

    except KeyboardInterrupt:
        # Stop cleanly when Ctrl+C is pressed.
        print("\n[NightSentinel] Stopping vision system...")

    finally:
        # Close the video stream and release camera resources.
        if hasattr(results, "close"):
            results.close()

        print("[NightSentinel] Vision system stopped.")


if __name__ == "__main__":
    main()
