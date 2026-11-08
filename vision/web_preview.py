"""Small MJPEG server for viewing annotated Jetson frames on the LAN."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Condition, Thread


INDEX_HTML = b"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NightSentinel Camera</title>
  <style>
    body { margin: 0; background: #080b10; color: #eef2f7;
           font-family: system-ui, sans-serif; text-align: center; }
    h1 { font-size: 1.2rem; font-weight: 600; margin: 1rem; }
    img { display: block; width: min(96vw, 960px); height: auto;
          margin: 0 auto 1rem; border: 1px solid #29313d;
          border-radius: 8px; background: #000; }
  </style>
</head>
<body>
  <h1>NightSentinel Camera</h1>
  <img src="/stream.mjpg" alt="Live NightSentinel camera stream">
</body>
</html>
"""


class PreviewFrameStore:
    """Thread-safe storage for the newest encoded JPEG frame."""

    def __init__(self):
        self._condition = Condition()
        self._sequence = 0
        self._frame = None

    def publish(self, frame):
        with self._condition:
            self._frame = frame
            self._sequence += 1
            self._condition.notify_all()

    def wait_for_frame(self, after_sequence, timeout=1.0):
        with self._condition:
            if self._sequence <= after_sequence:
                self._condition.wait_for(
                    lambda: self._sequence > after_sequence,
                    timeout=timeout,
                )
            if self._sequence <= after_sequence:
                return after_sequence, None
            return self._sequence, self._frame


class _PreviewHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(INDEX_HTML)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(INDEX_HTML)
            return

        if path == "/healthz":
            body = b'{"status":"online"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path != "/stream.mjpg":
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "multipart/x-mixed-replace; boundary=frame",
        )
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()

        sequence = 0
        try:
            while True:
                sequence, frame = self.server.frame_store.wait_for_frame(
                    sequence,
                    timeout=1.0,
                )
                if frame is None:
                    continue
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(
                    f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii")
                )
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def log_message(self, _format, *_args):
        return


class WebPreviewServer:
    """Serve frames published by the detector as an MJPEG browser stream."""

    def __init__(self, host="0.0.0.0", port=8080, jpeg_quality=80):
        self.host = host
        self.port = port
        self.jpeg_quality = jpeg_quality
        self.frame_store = PreviewFrameStore()
        self._server = ThreadingHTTPServer((host, port), _PreviewHandler)
        self._server.daemon_threads = True
        self._server.frame_store = self.frame_store
        self._thread = Thread(
            target=self._server.serve_forever,
            name="nightsentinel-web-preview",
            daemon=True,
        )

    def start(self):
        self._thread.start()

    def publish_image(self, image):
        import cv2

        encoded_ok, encoded = cv2.imencode(
            ".jpg",
            image,
            [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality],
        )
        if encoded_ok:
            self.frame_store.publish(encoded.tobytes())

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)
