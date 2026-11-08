#include <Servo.h>

// --- Pin Assignments ---
const int radarOutPin = 4;   // mmWave Radar 'OUT' pin -> HIGH = Presence detected
const int trigPin = 8;       // JSN-SR04T Ultrasonic Trigger pin
const int echoPin = 9;       // JSN-SR04T Ultrasonic Echo pin
const int ldrPin = A0;       // Photoresistor voltage divider input 
const int servoPin = 5;      // MG996R Servo signal pin
const int relayPin = 7;      // Connected to Relay 'IN'

Servo scannerServo;

// --- Configured Settings ---
const int DARK_THRESHOLD = 67;       // LDR threshold: below this is considered "Night"
const int SWEEP_MIN = 30;             // Sweep min set to 30°
const int SWEEP_MAX = 150;            // Sweep max set to 150°
const int SWEEP_STEP = 7;             // Sweep step set to 7°
const int SWEEP_DELAY = 130;          // Sweep delay set to 130 ms

// JSN-SR04T Range Limits: Ignore anything under 25 cm (blind spot) up to 150 cm max
const long MIN_VALID_DISTANCE_CM = 25; 
const long TARGET_DISTANCE_CM = 80;  

bool systemActive = false;
unsigned long activationTime = 0;
const unsigned long ACTIVE_TIMEOUT = 10000; // 10-second active window

// --- Forward Declarations / Helper Functions ---
void stopStrobe() {
  digitalWrite(relayPin, HIGH); // Relay OFF default
}

// --- Fast Relay-Safe Strobe Sequence with Daylight Safety Interlock ---
void fireDeterrentSequence() {
  Serial.println("[DEFCON 1] JSN target verified! Firing fast high-impact relay strobe!");

  for (int burst = 0; burst < 4; burst++) {
    
    // Safety check: If daylight hits mid-strobe, abort immediately!
    if (analogRead(ldrPin) > DARK_THRESHOLD) {
      Serial.println("[DAYTIME OVERRIDE] Light detected during strobe! Aborting immediately.");
      stopStrobe();
      systemActive = false;
      return;
    }

    digitalWrite(relayPin, LOW);  // Relay ON (Full brightness)
    delay(80);                    
    digitalWrite(relayPin, HIGH); // Relay OFF
    delay(50);                    
    
    digitalWrite(relayPin, LOW);  // Relay ON (Full brightness)
    delay(80);                   
    digitalWrite(relayPin, HIGH); // Relay OFF
    delay(60);

    digitalWrite(relayPin, LOW);    // ON (Maximum glare)
    delay(150);                     
    digitalWrite(relayPin, HIGH);   // OFF
    delay(70);

    digitalWrite(relayPin, LOW);  // ON
    delay(60);
    digitalWrite(relayPin, HIGH); // OFF
    delay(60);
    digitalWrite(relayPin, LOW);  // ON
    delay(60);
    digitalWrite(relayPin, HIGH); // OFF
    
    delay(random(100, 250));
  }

  stopStrobe();
}

// --- Read Distance from JSN-SR04T Sensor ---
long getJsnDistanceCm() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH, 30000);
  
  if (duration == 0) {
    return -1; 
  }
  
  long cm = duration * 0.034 / 2;
  return cm;
}
// Test
// --- Double-Check Distance to Prevent False 19cm Trips ---
bool isRealTargetDetected() {
  long d1 = getJsnDistanceCm();
  
  if (d1 >= MIN_VALID_DISTANCE_CM && d1 <= TARGET_DISTANCE_CM) {
    delay(30); 
    long d2 = getJsnDistanceCm();
    if (d2 >= MIN_VALID_DISTANCE_CM && d2 <= TARGET_DISTANCE_CM) {
      Serial.print("[JSN VERIFIED] Confirmed target at ");
      Serial.print(d2);
      Serial.println(" cm.");
      return true;
    }
  }
  return false;
}

// --- Helper: Handle Serial Commands Mid-Sweep ---
void handleSerialDuringSweep() {
  // Instant daylight check during sweep
  if (analogRead(ldrPin) > DARK_THRESHOLD) {
    stopStrobe();
    systemActive = false;
    scannerServo.write(90);
    return;
  }

  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "TRIGGER_STROBE") {
      Serial.println("[ACK] Jetson override target verified! Firing strobe!");
      fireDeterrentSequence();
    }
    else if (command == "RESET_SYSTEM") {
      systemActive = false;
      scannerServo.write(90);
      stopStrobe();
    }
  }
}

void setup() {
  Serial.begin(9600);
  
  pinMode(radarOutPin, INPUT);
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(ldrPin, INPUT);
  pinMode(relayPin, OUTPUT);
  
  stopStrobe(); 
  scannerServo.attach(servoPin);
  scannerServo.write(90); 

  Serial.println("--- NightSentinel Hardware: Instant Daylight Gating Active ---");
}

void loop() {
  // --- 1. Photoresistor (LDR) Ambient Light Check (Top Priority) ---
  int lightLevel = analogRead(ldrPin);

  if (lightLevel > DARK_THRESHOLD) {
    stopStrobe();
    systemActive = false;
    scannerServo.write(90);
    
    static unsigned long lastPrint = 0;
    if (millis() - lastPrint > 1000) {
      Serial.print("[DAYTIME MODE] LDR Light Level: ");
      Serial.print(lightLevel);
      Serial.println(" (System Locked OFF)");
      lastPrint = millis();
    }
    
    delay(100); 
    return; // Hard exit loop immediately
  }

  // --- 2. Listen for Incoming Serial Commands ---
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "TRIGGER_STROBE") {
      Serial.println("[ACK] Jetson camera target verified. Firing deterrent strobe!");
      fireDeterrentSequence(); 
    }
    else if (command == "RESET_SYSTEM") {
      Serial.println("[ACK] System resetting to standby.");
      systemActive = false;
      scannerServo.write(90);
      stopStrobe();
    }
  }

  // --- 3. Monitor Digital mmWave Pin ---
  int radarState = digitalRead(radarOutPin);

  if (radarState == HIGH && !systemActive) {
    systemActive = true;
    activationTime = millis();
    
    Serial.print("[RADAR TRIGGER] Motion detected on Pin 4! LDR: ");
    Serial.println(lightLevel);
    Serial.println("EVENT:RADAR_TRIPPED");
  }

  // --- 4. Active Sweeping & JSN Distance Scanning ---
  if (systemActive) {
    
    // Sweep forward
    for (int angle = SWEEP_MIN; angle <= SWEEP_MAX; angle += SWEEP_STEP) {
      scannerServo.write(angle);
      handleSerialDuringSweep();
      
      if (!systemActive) break; // Break out if daylight triggered mid-sweep
      
      if (isRealTargetDetected()) {
        Serial.println("EVENT:JSN_TRIGGERED");
        fireDeterrentSequence();
      }
      
      delay(SWEEP_DELAY);
    }
    
    // Sweep backward if still active
    if (systemActive) {
      for (int angle = SWEEP_MAX; angle >= SWEEP_MIN; angle -= SWEEP_STEP) {
        scannerServo.write(angle);
        handleSerialDuringSweep();
        
        if (!systemActive) break; // Break out if daylight triggered mid-sweep
        
        if (isRealTargetDetected()) {
          Serial.println("EVENT:JSN_TRIGGERED");
          fireDeterrentSequence();
        }
        
        delay(SWEEP_DELAY);
      }
    }

    // Timeout check
    if (millis() - activationTime > ACTIVE_TIMEOUT) {
      if (digitalRead(radarOutPin) == LOW) {
        Serial.println("[TIMEOUT] Returning to standby center.");
        systemActive = false;
        scannerServo.write(90);
        stopStrobe();
      } else {
        activationTime = millis(); 
      }
    }
  } else {
    scannerServo.write(90);
    stopStrobe();
    delay(50);
  }
} 