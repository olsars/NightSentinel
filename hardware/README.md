# NightSentinel hardware

## Confirmed Arduino Nano pin map

The integrated firmware currently uses:

| Component | Arduino Nano pin |
| --- | --- |
| mmWave radar OUT | D4 |
| MG996R servo signal | D5 |
| Active-low relay input | D7 |
| JSN-SR04T TRIG | D8 |
| JSN-SR04T ECHO | D9 |
| LDR voltage divider | A0 |

D7 is not available for ultrasonic ECHO because it controls the relay. The
servo and strobe must use correctly rated external power/driver hardware with
a common ground; do not power either load directly from an Arduino GPIO.
Inspect the repaired wiring before applying power.

The observed LDR ranges are separated with hysteresis: the system enters dark
mode below 230 and returns to daylight lockout above 270. This avoids command
rejection and servo resets when covered/dim readings fluctuate between 80 and
213, while the observed uncovered readings remain around 300-400.

## Ultrasonic behavior

`ultrasonic.h` uses a 250 ms interval, a provisional 25-450 cm valid range,
and a 30 ms `pulseIn()` timeout. Scheduling is nonblocking between samples,
but `pulseIn()` can block for up to that timeout during a measurement.

Three consecutive valid readings at or below 100 cm confirm a near state. A
valid reading at or above 130 cm clears it. Invalid readings reset an
unconfirmed sequence but do not clear an already confirmed near state.

Distance is supplementary information only. It does not classify an object as
a person and cannot activate the strobe. Only a `TRIGGER_STROBE` command from
the Jetson during an active, dark radar window can run the deterrent sequence.

### Serial output protocol

```text
DISTANCE_CM:125.5
DISTANCE_CM:INVALID
EVENT:PROXIMITY_NEAR
EVENT:PROXIMITY_CLEARED
EVENT:RADAR_TRIPPED
```

The bridge temporarily recognizes the legacy `[JSN VERIFIED] ... cm` and
`EVENT:JSN_TRIGGERED` messages so the currently flashed firmware remains
readable during migration.

### Jetson-to-Arduino commands

```text
SERVO_STOP
SERVO_SCAN
SERVO_ANGLE:90
RESET_SYSTEM
TRIGGER_STROBE
```

The Arduino reports its actual held position as `STATE:SERVO_ANGLE:<angle>` so
vision begins closed-loop steering from the physical sweep position instead of
assuming the camera was centered when a person was acquired.

Servo angles are limited to 30-150 degrees. `vision/detector.py` uses confirmed
YOLO track IDs, a smoothed target center, a horizontal dead zone, bounded angle
steps, and a 100 ms command interval to follow one person without excessive
jitter. Once acquired, the target remains selected until it has been absent
for multiple frames; only then does scanning resume. The default servo
direction is `-1`; set `NIGHTSENTINEL_SERVO_DIRECTION=1` if physical movement
is reversed.

Vision pauses the sweep after two plausible person frames so confirmation is
performed on a steady image, then requires five frames before selecting the
track. The default confidence threshold is 0.4 and can be overridden with
`NIGHTSENTINEL_CONFIDENCE`.

Strobe commands from vision are disabled by default. For a controlled test,
they can be enabled with `NIGHTSENTINEL_STROBE_ENABLED=1`; even then, both a
confirmed YOLO person and ultrasonic near state are required before the Jetson
sends `TRIGGER_STROBE`.

## Compile

Compile the integrated firmware from the repository root:

```bash
/home/solars/bin/arduino-cli compile \
  --fqbn arduino:avr:nano \
  --build-property "compiler.cpp.extra_flags=-I$(pwd)/hardware" \
  hardware/integrated_nightsentinel
```

Compile the isolated sensor test with:

```bash
/home/solars/bin/arduino-cli compile \
  --fqbn arduino:avr:nano \
  --build-property "compiler.cpp.extra_flags=-I$(pwd)/hardware" \
  hardware/ultrasonic_test
```

Compilation does not upload firmware. Do not upload until the Nano processor
and bootloader variant are confirmed. Uploading replaces the currently working
firmware.

## Test and run

Only one process may own `/dev/ttyUSB0`.

```bash
./.venv/bin/python -B -m unittest discover -s tests -v
./.venv/bin/python -B hardware/serial_bridge.py --simulate
./.venv/bin/python -B hardware/serial_bridge.py \
  --port /dev/ttyUSB0 --baud 9600
```

Run vision with tracking and strobe disabled:

```bash
NIGHTSENTINEL_STROBE_ENABLED=0 \
NIGHTSENTINEL_CAMERA_SOURCE=1 \
./.venv/bin/python -B vision/detector.py
```

The camera defaults to index `0`. Override it with a numeric index or stable
device path when the C920 enumerates elsewhere, such as `/dev/video1`.

To view annotated detections from a laptop on the same trusted local network,
enable the optional 10 FPS web preview:

```bash
NIGHTSENTINEL_CAMERA_SOURCE=1 \
NIGHTSENTINEL_STREAM_ENABLED=1 \
NIGHTSENTINEL_STROBE_ENABLED=0 \
./.venv/bin/python -B vision/detector.py
```

Open `http://<jetson-ip>:8080` in the laptop browser. The preview has no login,
so only enable it on a trusted local network. Override the port with
`NIGHTSENTINEL_STREAM_PORT` and stop the detector to stop the stream.

Do not run the standalone serial bridge beside the detector. The detector uses
the same bridge implementation and must be the sole owner of `/dev/ttyUSB0`
while tracking.
