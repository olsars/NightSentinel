
"""
NightSentinel - Vision Detection Module

Hardware: NVIDIA Jetson Orin Nano + Logitech C920
Model: YOLO11 Nano
Tracking: ByteTrack

Detects people from a live camera feed and assigns
temporary tracking IDs to detected individuals.
"""

from ultralytics import YOLO


def main():
    # Load the pretrained YOLO11 Nano model.
    # Ultralytics downloads the weights if they aren't available.
    model = YOLO("yolo11n.pt")

    print("[NightSentinel] Starting vision system...")

    # Run person detection and tracking on the Jetson GPU.
    #
    # source=0: USB camera at /dev/video0
    # device=0: NVIDIA GPU (CUDA device 0)
    # classes=[0]: Detect people only
    # conf=0.5: Minimum detection confidence of 50%
    # tracker: ByteTrack assigns temporary IDs
    # stream=True: Process frames continuously
    # show=False: No graphical window required
    results = model.track(
        source=0,
        device=0,
        classes=[0],
        conf=0.5,
        tracker="bytetrack.yaml",
        stream=True,
        show=False,
        verbose=False,
    )

    try:
        # Each result represents one processed camera frame.
        for result in results:

            # Boxes contain detected objects in the frame.
            if result.boxes is None:
                continue

            # Read each detected person's bounding box.
            for box in result.boxes:

                # Confidence is a PyTorch tensor.
                confidence = float(box.conf.item())

                # Tracking IDs may be unavailable in early frames.
                if box.id is None:
                    continue

                track_id = int(box.id.item())

                print(
                    f"[DETECTION] Person detected | "
                    f"Track ID: {track_id} | "
                    f"Confidence: {confidence:.2f}"
                )

    except KeyboardInterrupt:
        # Allow the operator to stop detection with Ctrl+C.
        print("\n[NightSentinel] Stopping vision system...")

    finally:
        # Release the camera when the program exits.
        if hasattr(results, "close"):
            results.close()

        print("[NightSentinel] Vision system stopped.")


if __name__ == "__main__":
    main()
