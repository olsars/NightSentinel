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

void stopStrobe() {
  digitalWrite(relayPin, HIGH);
}

void setServoAngle(int angle) {
  currentServoAngle = constrain(angle, SWEEP_MIN, SWEEP_MAX);
  scannerServo.write(currentServoAngle);
}

void resetSystem() {
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

// This is called only after the Jetson sends TRIGGER_STROBE. Radar or
// ultrasonic proximity alone must never authorize the deterrent.
void fireDeterrentSequence() {
  Serial.println(F("[DETERRENT] Jetson-authorized strobe sequence started."));

  for (int burst = 0; burst < 4; ++burst) {
    if (!updateDarkMode(analogRead(ldrPin))) {
      Serial.println(F("[DAYTIME OVERRIDE] Strobe aborted."));
      resetSystem();
      return;
    }

    digitalWrite(relayPin, LOW);
    delay(80);
    digitalWrite(relayPin, HIGH);
    delay(50);

    digitalWrite(relayPin, LOW);
    delay(80);
    digitalWrite(relayPin, HIGH);
    delay(60);

    digitalWrite(relayPin, LOW);
    delay(150);
    digitalWrite(relayPin, HIGH);
    delay(70);

    digitalWrite(relayPin, LOW);
    delay(60);
    digitalWrite(relayPin, HIGH);
    delay(60);
    digitalWrite(relayPin, LOW);
    delay(60);
    digitalWrite(relayPin, HIGH);

    delay(random(100, 250));
  }

  stopStrobe();
}

void handleCommand(const String &command) {
  if (command == "JETSON_ONLINE") {
    jetsonOnline = true;
    resetSystem();
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

  if (command == "TRIGGER_STROBE") {
    if (!systemActive) {
      Serial.println(F("[NACK] TRIGGER_STROBE requires an active radar window."));
      return;
    }

    Serial.println(F("[ACK] Jetson person confirmation accepted."));
    sweepEnabled = false;
    fireDeterrentSequence();
    resetSystem();
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
