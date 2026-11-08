# NightSentinel hardware

## JSN-SR04T ultrasonic sensor

This integration assumes a JSN-SR04T revision that supports the conventional
TRIG/ECHO interface. Confirm the module revision and inspect the repaired
wiring before applying power; USB detection alone does not establish that the
circuit is safe.

Initial wiring assumption:

| JSN-SR04T | Arduino Nano | Notes |
| --- | --- | --- |
| VCC | 5V | Confirm against the exact module revision. |
| GND | GND | All logic must share a common ground. |
| TRIG | D6 | Configurable in the constructor. |
| ECHO | D7 | Configurable in the constructor. |

The existing isolated servo sketch uses D5. The integrated firmware files are
currently empty, so D6/D7 cannot yet be confirmed against the teammate's real
mmWave, LDR, relay, and warning-light pin map. Do not power the MG996R servo or
a strobe directly from an Arduino GPIO; use correctly rated external power and
driver hardware with a common ground.

`ultrasonic.h` defaults to a 250 ms measurement interval, a nominal 25-450 cm
accepted range, and a 30 ms echo timeout. These range values are provisional
until the exact sensor revision is identified. Scheduling is nonblocking
between samples, but Arduino `pulseIn()` can block for up to the configured
timeout during a sample.

Three consecutive valid readings at or below 100 cm confirm a near state. A
subsequent valid reading at or above 130 cm clears it. Hysteresis prevents
rapid state changes near the boundary. Invalid readings reset an unconfirmed
near sequence, but do not clear an already confirmed near state; a valid clear
reading is required.

### Serial protocol

All messages use the existing 9600-baud connection:

```text
DISTANCE_CM:125.5
DISTANCE_CM:INVALID
EVENT:PROXIMITY_NEAR
EVENT:PROXIMITY_CLEARED
```

The ultrasonic sensor only supplies proximity information. It does not
classify an object as a person, and the bridge does not post these messages to
the backend `/events` endpoint.

### Standalone test sketch

The repository's intended integrated firmware is empty, so
`ultrasonic_test/ultrasonic_test.ino` is deliberately standalone. After the
hardware teammate confirms the board, sensor revision, wiring, and pins,
compile it from the repository root with:

```bash
arduino-cli compile \
  --fqbn arduino:avr:nano \
  --build-property "compiler.cpp.extra_flags=-I$(pwd)/hardware" \
  hardware/ultrasonic_test
```

The explicit include path is required because Arduino CLI copies the sketch to
a temporary build directory; a relative include such as `../ultrasonic.h`
would no longer point at the repository's canonical header from there.

Do not upload automatically. Some Nano clones require a different processor
or old-bootloader board option, which must be confirmed before upload.

When the real integrated sketch is available, add `#include "ultrasonic.h"`,
create one `UltrasonicSensor` instance with confirmed pins, call `begin()` from
the existing `setup()`, and call `update()` on every pass through the existing
`loop()`. Do not add a second `setup()` or `loop()`.

### Jetson serial bridge

Only one process may own `/dev/ttyUSB0`. Run the bridge with real hardware:

```bash
python hardware/serial_bridge.py --port /dev/ttyUSB0 --baud 9600
```

Run realistic messages without hardware and execute the parser tests with:

```bash
python hardware/serial_bridge.py --simulate
python -m unittest discover -s tests -v
```

Before the physical demonstration, the hardware teammate must confirm the
sensor revision, repaired wiring, final pin map, Nano variant/bootloader, power
arrangement, and successful bench readings. The backend team can later approve
a rate-limited latest-reading API such as `GET /sensor-readings`; storing every
250 ms sample in SQLite is intentionally out of scope.
