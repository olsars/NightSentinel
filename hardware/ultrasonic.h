#ifndef NIGHTSENTINEL_ULTRASONIC_H
#define NIGHTSENTINEL_ULTRASONIC_H

#include <Arduino.h>

// JSN-SR04T trigger/echo driver for the Arduino Nano (ATmega328P).
//
// Defaults assume TRIG on D6 and ECHO on D7. Pass different pins to the
// constructor if the integrated firmware or final wiring uses those pins.
// update() schedules readings with millis(), but pulseIn() can still block for
// up to echoTimeoutUs (30 ms by default) while it waits for an echo.
class UltrasonicSensor {
 public:
  UltrasonicSensor(uint8_t triggerPin = 6,
                   uint8_t echoPin = 7,
                   unsigned long measurementIntervalMs = 250UL,
                   float nearThresholdCm = 100.0f,
                   float clearThresholdCm = 130.0f,
                   uint8_t nearConfirmationCount = 3,
                   float minimumDistanceCm = 25.0f,
                   float maximumDistanceCm = 450.0f,
                   unsigned long echoTimeoutUs = 30000UL)
      : triggerPin_(triggerPin),
        echoPin_(echoPin),
        measurementIntervalMs_(measurementIntervalMs),
        nearThresholdCm_(nearThresholdCm),
        clearThresholdCm_(clearThresholdCm),
        nearConfirmationCount_(nearConfirmationCount == 0
                                   ? 1
                                   : nearConfirmationCount),
        minimumDistanceCm_(minimumDistanceCm),
        maximumDistanceCm_(maximumDistanceCm),
        echoTimeoutUs_(echoTimeoutUs),
        lastMeasurementMs_(0),
        nearReadingCount_(0),
        proximityNear_(false),
        hasMeasured_(false) {}

  void begin() {
    pinMode(triggerPin_, OUTPUT);
    pinMode(echoPin_, INPUT);
    digitalWrite(triggerPin_, LOW);
  }

  // Call once on every loop() pass. Returns true only when a measurement was
  // attempted, which can be useful to a future integrated firmware loop.
  bool update() {
    const unsigned long now = millis();
    if (hasMeasured_ &&
        static_cast<unsigned long>(now - lastMeasurementMs_) <
            measurementIntervalMs_) {
      return false;
    }

    hasMeasured_ = true;
    lastMeasurementMs_ = now;

    float distanceCm = 0.0f;
    if (!measureDistanceCm(distanceCm)) {
      Serial.println(F("DISTANCE_CM:INVALID"));

      // Invalid input breaks consecutive valid near readings. Once proximity
      // is confirmed, retain it until a valid reading reaches clearThreshold.
      if (!proximityNear_) {
        nearReadingCount_ = 0;
      }
      return true;
    }

    Serial.print(F("DISTANCE_CM:"));
    Serial.println(distanceCm, 1);
    updateProximityState(distanceCm);
    return true;
  }

  bool isProximityNear() const { return proximityNear_; }

 private:
  bool measureDistanceCm(float &distanceCm) {
    digitalWrite(triggerPin_, LOW);
    delayMicroseconds(2);
    digitalWrite(triggerPin_, HIGH);
    delayMicroseconds(10);
    digitalWrite(triggerPin_, LOW);

    const unsigned long echoDurationUs =
        pulseIn(echoPin_, HIGH, echoTimeoutUs_);
    if (echoDurationUs == 0) {
      return false;
    }

    // Approximate speed of sound at room temperature: 0.0343 cm/us. The echo
    // covers a round trip, so divide by two for the one-way distance.
    distanceCm = static_cast<float>(echoDurationUs) * 0.0343f / 2.0f;
    return distanceCm >= minimumDistanceCm_ &&
           distanceCm <= maximumDistanceCm_;
  }

  void updateProximityState(float distanceCm) {
    if (proximityNear_) {
      if (distanceCm >= clearThresholdCm_) {
        proximityNear_ = false;
        nearReadingCount_ = 0;
        Serial.println(F("EVENT:PROXIMITY_CLEARED"));
      }
      return;
    }

    if (distanceCm <= nearThresholdCm_) {
      if (nearReadingCount_ < nearConfirmationCount_) {
        ++nearReadingCount_;
      }
      if (nearReadingCount_ >= nearConfirmationCount_) {
        proximityNear_ = true;
        Serial.println(F("EVENT:PROXIMITY_NEAR"));
      }
    } else {
      nearReadingCount_ = 0;
    }
  }

  const uint8_t triggerPin_;
  const uint8_t echoPin_;
  const unsigned long measurementIntervalMs_;
  const float nearThresholdCm_;
  const float clearThresholdCm_;
  const uint8_t nearConfirmationCount_;
  const float minimumDistanceCm_;
  const float maximumDistanceCm_;
  const unsigned long echoTimeoutUs_;

  unsigned long lastMeasurementMs_;
  uint8_t nearReadingCount_;
  bool proximityNear_;
  bool hasMeasured_;
};

#endif  // NIGHTSENTINEL_ULTRASONIC_H
