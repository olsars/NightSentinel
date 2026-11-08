
"""
NightSentinel - Backend Event Client

Sends detection events from the Jetson vision system
to the NightSentinel FastAPI backend.
"""

import os
import requests


# Backend address is configured through an environment variable.
# Defaults to localhost for testing on the same machine.
API_URL = os.getenv("NIGHTSENTINEL_API_URL", "http://127.0.0.1:8000")


def send_event(track_id, event_type="person_detected", zone="front_door"):
    """
    Send a detection event to the backend.

    Returns True if the backend accepts the event,
    otherwise returns False.
    """

    # Build the JSON payload expected by the backend.
    payload = {
        "track_id": f"track_{track_id}",
        "event_type": event_type,
        "zone": zone,
    }

    try:
        # Send the event using an HTTP POST request.
        response = requests.post(
            f"{API_URL}/events",
            json=payload,
            timeout=3,
        )

        # New events return 201; duplicate-suppressed events return the
        # existing record with 200 and should also count as accepted.
        if response.status_code in (200, 201):
            print(f"[EVENT] Sent successfully: {payload}")
            return True

        print(
            f"[EVENT] Backend rejected event: "
            f"{response.status_code} {response.text}"
        )
        return False

    except requests.RequestException as error:
        # Prevent temporary network failures from crashing YOLO.
        print(f"[EVENT] Connection failed: {error}")
        return False
