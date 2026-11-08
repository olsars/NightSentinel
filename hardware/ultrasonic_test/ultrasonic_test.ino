#include "../ultrasonic.h"

// Standalone JSN-SR04T test only. Confirm the sensor revision and inspect the
// repaired wiring before powering the circuit.
constexpr uint8_t ULTRASONIC_TRIGGER_PIN = 6;
constexpr uint8_t ULTRASONIC_ECHO_PIN = 7;

UltrasonicSensor ultrasonic(
    ULTRASONIC_TRIGGER_PIN,
    ULTRASONIC_ECHO_PIN,
    250UL,   // Measurement interval (ms)
    100.0f,  // Near threshold (cm)
    130.0f,  // Clear threshold (cm)
    3        // Consecutive valid near readings required
);

void setup() {
  Serial.begin(9600);
  ultrasonic.begin();
  Serial.println(F("[ULTRASONIC TEST] JSN-SR04T initialized"));
}

void loop() {
  ultrasonic.update();
}
