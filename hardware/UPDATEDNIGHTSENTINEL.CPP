#include <Arduino.h>
#include <Servo.h>
#include <ultrasonic.h>

// NightSentinel integrated Arduino Nano firmware.
// The Jetson is the only component allowed to classify a target as a person.

// --- Confirmed Pin Assignments ---
const uint8_t radarOutPin = 4;  // mmWave OUT: HIGH means presence detected
const uint8_t servoPin = 5;     // MG996R signal (use an external supply)
const uint8_t relayPin = 7;     // Active-low relay input
const uint8_t trigPin = 8;      // JSN-SR04T trigger
const uint8_t echoPin = 9;      // JSN-SR04T echo
const uint8_t ldrPin = A0;      // Photoresistor voltage divider

// --- Configuration ---
// Calibrated from observed hardware values: covered/dim readings were 80-213
// and uncovered readings were approximately 300-400. Separate enter/exit
// thresholds prevent rapid mode changes near a single boundary.
const int DARK_ENTER_THRESHOLD = 230;
const int DAYLIGHT_EXIT_THRESHOLD = 270;
const int SWEEP_MIN = 30;
const int SWEEP_MAX = 150;
const int SWEEP_STEP = 7;
const unsigned long SWEEP_DELAY_MS = 130UL;
const unsigned long ACTIVE_TIMEOUT_MS = 10000UL;
const uint8_t STROBE_BURST_COUNT = 4;
const uint8_t STROBE_STEP_COUNT = 11;
const unsigned int STROBE_STEP_MS[STROBE_STEP_COUNT] = {
    80, 50, 80, 60, 150, 70, 60, 60, 60, 60, 100};

Servo scannerServo;
UltrasonicSensor ultrasonic(
    trigPin,
    echoPin,
    250UL,    // Measurement interval
    100.0f,   // Near threshold
    130.0f,   // Clear threshold
    3,        // Consecutive valid near readings required
    25.0f,    // Provisional minimum valid distance
    450.0f,   // Provisional maximum valid distance
    30000UL   // pulseIn timeout
);

bool systemActive = false;
bool sweepEnabled = true;
bool darkMode = false;
bool jetsonOnline = false;
unsigned long activationTime = 0;
int currentServoAngle = 90;
bool strobeActive = false;
uint8_t strobeBurst = 0;
uint8_t strobeStep = 0;
unsigned long strobeStepStartedAt = 0;
unsigned int strobeStepDurationMs = 0;

void stopStrobe() {
  digitalWrite(relayPin, HIGH);
}

void setServoAngle(int angle) {
  currentServoAngle = constrain(angle, SWEEP_MIN, SWEEP_MAX);
  scannerServo.write(currentServoAngle);
}

void resetSystem() {
  strobeActive = false;
  systemActive = false;
  sweepEnabled = true;
  setServoAngle(90);
  stopStrobe();
}

bool updateDarkMode(int lightLevel) {
  if (darkMode) {
    if (lightLevel > DAYLIGHT_EXIT_THRESHOLD) {
      darkMode = false;
    }
  } else if (lightLevel < DARK_ENTER_THRESHOLD) {
    darkMode = true;
  }
  return darkMode;
}

void setStrobeOutputForStep(uint8_t step) {
  // Steps alternate active-low ON and OFF. The final step is an OFF gap.
  digitalWrite(relayPin, step < 10 && step % 2 == 0 ? LOW : HIGH);
}

void finishDeterrentSequence(bool aborted) {
  stopStrobe();
  strobeActive = false;
  activationTime = millis();

  if (aborted) {
    Serial.println(F("EVENT:STROBE_ABORTED"));
  } else {
    Serial.println(F("EVENT:STROBE_COMPLETE"));
  }

  // The servo stays at the last tracked angle so vision can continue without
  // the Nano and Jetson disagreeing about its physical position.
  Serial.print(F("STATE:SERVO_ANGLE:"));
  Serial.println(currentServoAngle);
}

// Start a non-blocking deterrent sequence. loop() continues polling serial,
// sensors, and safety state while the relay timing advances with millis().
void startDeterrentSequence() {
  Serial.println(F("[DETERRENT] Jetson-authorized strobe sequence started."));
  Serial.println(F("EVENT:STROBE_STARTED"));
  strobeActive = true;
  strobeBurst = 0;
  strobeStep = 0;
  strobeStepStartedAt = millis();
  strobeStepDurationMs = STROBE_STEP_MS[0];
  setStrobeOutputForStep(0);
}

void updateDeterrentSequence() {
  if (!strobeActive) {
    return;
  }

  if (millis() - strobeStepStartedAt < strobeStepDurationMs) {
    return;
  }

  ++strobeStep;
  if (strobeStep >= STROBE_STEP_COUNT) {
    ++strobeBurst;
    if (strobeBurst >= STROBE_BURST_COUNT) {
      finishDeterrentSequence(false);
      return;
    }

    if (!updateDarkMode(analogRead(ldrPin))) {
      Serial.println(F("[DAYTIME OVERRIDE] Strobe aborted."));
      finishDeterrentSequence(true);
      return;
    }
    strobeStep = 0;
  }

  strobeStepStartedAt = millis();
  strobeStepDurationMs = strobeStep == 10
      ? static_cast<unsigned int>(random(100, 250))
      : STROBE_STEP_MS[strobeStep];
  setStrobeOutputForStep(strobeStep);
}

void handleCommand(const String &command) {
  if (command == "JETSON_ONLINE") {
    jetsonOnline = true;
    resetSystem();
    if (updateDarkMode(analogRead(ldrPin))) {
      // Perform one immediate nighttime scan instead of waiting for the first
      // radar transition. Normal radar gating resumes after the timeout.
      systemActive = true;
      sweepEnabled = true;
      activationTime = millis();
    }
    Serial.println(F("[ACK] Jetson control online."));
    Serial.println(F("STATE:JETSON_ONLINE:1"));
    return;
  }

  if (command == "JETSON_OFFLINE") {
    jetsonOnline = false;
    resetSystem();
    Serial.println(F("[ACK] Jetson control offline; servo parked."));
    Serial.println(F("STATE:JETSON_ONLINE:0"));
    return;
  }

  if (command == "RESET_SYSTEM") {
    resetSystem();
    Serial.println(F("[ACK] System reset to standby."));
    return;
  }

  if (!jetsonOnline) {
    Serial.println(F("[NACK] Command requires JETSON_ONLINE."));
    resetSystem();
    return;
  }

  if (!updateDarkMode(analogRead(ldrPin))) {
    Serial.println(F("[NACK] Command blocked by daylight."));
    resetSystem();
    return;
  }

  if (strobeActive) {
    Serial.println(F("[BUSY] Strobe active; command ignored."));
    return;
  }

  if (command == "TRIGGER_STROBE") {
    if (!systemActive) {
      Serial.println(F("[NACK] TRIGGER_STROBE requires an active radar window."));
      return;
    }

    Serial.println(F("[ACK] Jetson person confirmation accepted."));
    sweepEnabled = false;
    startDeterrentSequence();
  } else if (command == "SERVO_STOP") {
    systemActive = true;
    sweepEnabled = false;
    activationTime = millis();
    setServoAngle(currentServoAngle);
    Serial.println(F("[ACK] Servo sweep stopped."));
    Serial.print(F("STATE:SERVO_ANGLE:"));
    Serial.println(currentServoAngle);
  } else if (command == "SERVO_SCAN") {
    systemActive = true;
    sweepEnabled = true;
    activationTime = millis();
    Serial.println(F("[ACK] Servo sweep enabled."));
  } else if (command.startsWith("SERVO_ANGLE:")) {
    const int requestedAngle = command.substring(12).toInt();
    if (requestedAngle < SWEEP_MIN || requestedAngle > SWEEP_MAX) {
      Serial.println(F("[NACK] Servo angle must be between 30 and 150."));
      return;
    }

    systemActive = true;
    sweepEnabled = false;
    activationTime = millis();
    setServoAngle(requestedAngle);
    Serial.print(F("[ACK] Servo angle set to "));
    Serial.println(currentServoAngle);
    Serial.print(F("STATE:SERVO_ANGLE:"));
    Serial.println(currentServoAngle);
  } else if (command.length() > 0) {
    Serial.print(F("[NACK] Unknown command: "));
    Serial.println(command);
  }
}

void pollSerialCommand() {
  if (Serial.available() <= 0) {
    return;
  }

  String command = Serial.readStringUntil('\n');
  command.trim();
  handleCommand(command);
}

void handleActiveTimeout() {
  // Tracking mode is explicitly ended by SERVO_SCAN or RESET_SYSTEM. This
  // keeps a centered target from timing out merely because no angle changed.
  if (!sweepEnabled) {
    return;
  }

  if (millis() - activationTime <= ACTIVE_TIMEOUT_MS) {
    return;
  }

  if (digitalRead(radarOutPin) == LOW) {
    Serial.println(F("[TIMEOUT] Returning to standby center."));
    resetSystem();
  } else {
    activationTime = millis();
  }
}

void handleDuringSweep() {
  if (!updateDarkMode(analogRead(ldrPin))) {
    Serial.println(F("[DAYTIME OVERRIDE] Sweep stopped."));
    resetSystem();
    return;
  }

  pollSerialCommand();
  ultrasonic.update();
}

void setup() {
  Serial.begin(9600);
  Serial.setTimeout(50);

  pinMode(radarOutPin, INPUT);
  pinMode(ldrPin, INPUT);
  pinMode(relayPin, OUTPUT);

  stopStrobe();
  scannerServo.attach(servoPin);
  setServoAngle(90);
  ultrasonic.begin();

  Serial.println(F("--- NightSentinel Hardware: Jetson-authorized deterrent mode ---"));
  Serial.println(F("STATE:JETSON_ONLINE:0"));
}

void loop() {
  const int lightLevel = analogRead(ldrPin);
  const bool isDark = updateDarkMode(lightLevel);

  // Daylight is a hard safety interlock. The ultrasonic sensor is left idle
  // here to preserve the existing daytime power-saving behavior.
  if (!isDark) {
    resetSystem();
    pollSerialCommand();

    static unsigned long lastDaytimePrint = 0;
    if (millis() - lastDaytimePrint > 1000UL) {
      Serial.print(F("[DAYTIME MODE] LDR Light Level: "));
      Serial.print(lightLevel);
      Serial.println(F(" (System Locked OFF)"));
      lastDaytimePrint = millis();
    }

    delay(100);
    return;
  }

  // The Nano may reset when the USB serial connection closes. Defaulting to
  // offline ensures that Ctrl+C or a disconnected Jetson always parks the
  // camera instead of allowing radar to restart an autonomous sweep.
  pollSerialCommand();
  if (!jetsonOnline) {
    resetSystem();
    delay(50);
    return;
  }

  // Distance is supplementary information only. UltrasonicSensor emits the
  // standardized DISTANCE_CM and proximity state-change messages.
  ultrasonic.update();

  if (strobeActive) {
    updateDeterrentSequence();
    delay(2);
    return;
  }

  if (digitalRead(radarOutPin) == HIGH && !systemActive) {
    systemActive = true;
    sweepEnabled = true;
    activationTime = millis();

    Serial.print(F("[RADAR TRIGGER] Motion detected on Pin 4! LDR: "));
    Serial.println(lightLevel);
    Serial.println(F("EVENT:RADAR_TRIPPED"));
  }

  if (!systemActive) {
    setServoAngle(90);
    stopStrobe();
    delay(50);
    return;
  }

  // SERVO_STOP and SERVO_ANGLE place the servo in hold/tracking mode while
  // the loop continues polling commands and measuring distance.
  if (!sweepEnabled) {
    handleActiveTimeout();
    delay(10);
    return;
  }

  for (int angle = SWEEP_MIN;
       angle <= SWEEP_MAX && systemActive && sweepEnabled;
       angle += SWEEP_STEP) {
    setServoAngle(angle);
    handleDuringSweep();
    delay(SWEEP_DELAY_MS);
  }

  for (int angle = SWEEP_MAX;
       angle >= SWEEP_MIN && systemActive && sweepEnabled;
       angle -= SWEEP_STEP) {
    setServoAngle(angle);
    handleDuringSweep();
    delay(SWEEP_DELAY_MS);
  }

  handleActiveTimeout();
}
