#include <Servo.h>

// --- Servo Pin Assignment ---
const int servoPin = 5;       // MG996R Servo signal pin

Servo scannerServo;

// --- Sweep Settings ---
const int SWEEP_MIN = 30;         // 60 to the left of center 
const int SWEEP_MAX = 150;        // 60 to the right of center 
const int SWEEP_STEP = 7;        // Step increment for smooth movement
const int SWEEP_DELAY = 140;     

void setup() {
  Serial.begin(9600);
  
  // Initial Centering
  scannerServo.attach(servoPin);
  scannerServo.write(90); 
  
  Serial.println("--- NightSentinel: Isolated Servo Sweep Test Initialized ---");
  delay(1000);
}

void loop() {
  // --- Sweep Forward: SWEEP_MIN (30°) to SWEEP_MAX (150°) ---
  Serial.println("Sweeping right...");
  for (int angle = SWEEP_MIN; angle <= SWEEP_MAX; angle += SWEEP_STEP) {
    scannerServo.write(angle);
    delay(SWEEP_DELAY); 
  }
  
  delay(500); // Brief pause at maximum extent

  // --- Sweep Backward: SWEEP_MAX (150°) to SWEEP_MIN (30°) ---
  Serial.println("Sweeping left...");
  for (int angle = SWEEP_MAX; angle >= SWEEP_MIN; angle -= SWEEP_STEP) {
    scannerServo.write(angle);
    delay(SWEEP_DELAY); 
  }
  
  delay(500); // Brief pause before restarting cycle
}