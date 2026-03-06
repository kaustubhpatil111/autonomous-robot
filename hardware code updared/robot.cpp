#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <SPI.h>
#include <RF24.h>
#include <ICM_20948.h>
#include <Adafruit_VL53L0X.h>
#include <SoftwareSerial.h>

// ========== VERSION AND DEBUG ==========
#define FIRMWARE_VERSION "2.1.1"
#define DEBUG_ENABLED true

// ========== PIN DEFINITIONS ==========
// Motor Driver (TB6612FNG)
#define PWMA   PA8
#define AIN1   PB12
#define AIN2   PB13
#define PWMB   PA15
#define BIN1   PB14
#define BIN2   PB15
#define STBY   PB3

// NRF24L01
#define CE     PA4
#define CSN    PB1

// Encoders
#define LEFT_ENC_PIN  PA0
#define RIGHT_ENC_PIN PA2

// Sensors
#define XSHUT_PIN     PA1  // VL53L0X shutdown pin

// Debug Serial (PB8=RX, PB9=TX)
SoftwareSerial debug(PB8, PB9);

// ESP32 UART
#define ESP_BAUD 115200

// ========== SERVO CONFIGURATION ==========
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();
#define SERVO_FREQ 50  // 50Hz servos
#define SERVO_MIN 150  // ~0.5ms pulse (0 degrees)
#define SERVO_MAX 600  // ~2.5ms pulse (180 degrees)

// Servo Channels (PCA9685)
#define BASE_SERVO    1
#define RIGHT_ARM     3
#define LEFT_ARM      8
#define GRIPPER       11
#define TOF_SERVO     5

// Servo Angle Limits
#define BASE_MIN   0
#define BASE_MAX   180
#define RIGHT_MIN  30
#define RIGHT_MAX  180
#define LEFT_MIN   0
#define LEFT_MAX   120
#define GRIP_MIN   100
#define GRIP_MAX   170
#define TOF_MIN    0
#define TOF_MAX    180

// Default positions
#define BASE_DEFAULT    90
#define RIGHT_DEFAULT   90
#define LEFT_DEFAULT    90
#define GRIP_DEFAULT    120
#define TOF_DEFAULT     90

// ========== NRF24L01 CONFIGURATION ==========
RF24 radio(CE, CSN);
const byte nrfAddress[6] = "ROBOT";
const uint8_t nrfChannel = 100;
const rf24_datarate_e nrfDataRate = RF24_250KBPS;
const rf24_pa_dbm_e nrfPowerLevel = RF24_PA_HIGH;

struct DataPacket {
  int16_t x;              // Joystick 1 X (0-1023)
  int16_t y;              // Joystick 1 Y (0-1023)
  int16_t baseAngle;      // Joystick 2 X (0-1023) mapped to base angle
  int16_t rightArmAngle;  // Joystick 2 Y (0-1023) mapped to right arm
  int16_t leftArmAngle;   // For future use
  int16_t gripperAngle;   // For future use
  bool joy1Button;        // Mode toggle
  bool joy2Button;        // Reset/Gripper toggle
  bool mode;              // false=drive, true=arm
} received;

bool nrfAvailable = false;
unsigned long lastNRFTime = 0;
const unsigned long NRF_TIMEOUT = 300;  // ms

// ========== ICM20948 IMU ==========
ICM_20948_I2C icm;
bool imuAvailable = false;
float imuData[9] = {0};  // ax, ay, az, gx, gy, gz, mx, my, mz
unsigned long lastIMUDebug = 0;

// ========== VL53L0X TOF Sensor ==========
Adafruit_VL53L0X lox = Adafruit_VL53L0X();
bool tofAvailable = false;
int tofDistance = 0;
unsigned long lastTofRead = 0;
const unsigned long TOF_INTERVAL = 50;  // ms
unsigned long lastTofReinit = 0;

// ========== ENCODERS ==========
volatile long leftEncCount = 0;
volatile long rightEncCount = 0;
unsigned long lastEncTime = 0;
float leftSpeed = 0;
float rightSpeed = 0;

// ========== CONTROL VARIABLES ==========
// Motor speeds
int targetLeftSpeed = 0;
int targetRightSpeed = 0;
int currentLeftSpeed = 0;
int currentRightSpeed = 0;

// Servo angles
float targetBaseAngle = BASE_DEFAULT;
float targetRightAngle = RIGHT_DEFAULT;
float targetLeftAngle = LEFT_DEFAULT;
float targetGripAngle = GRIP_DEFAULT;
float targetTofAngle = TOF_DEFAULT;

// Control mode (0=NRF, 1=WiFi)
int controlMode = 0;
unsigned long lastCmdTime = 0;
const unsigned long WIFI_TIMEOUT = 500;  // ms

// System state
bool systemReady = false;
unsigned long lastHeartbeat = 0;
unsigned long lastSensorSend = 0;
const unsigned long SENSOR_INTERVAL = 100;  // ms

// ========== INTERRUPT SERVICE ROUTINES ==========
void leftEncoderISR() { 
  leftEncCount++; 
}

void rightEncoderISR() { 
  rightEncCount++; 
}

// ========== UTILITY FUNCTIONS ==========
void printSeparator() {
  debug.println("========================================");
}

// ========== I2C SCANNER ==========
void scanI2CDevices() {
  debug.println("\n🔍 I2C Scanner - Scanning for devices...");
  byte error, address;
  int nDevices = 0;
  
  for (address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();
    
    if (error == 0) {
      debug.print("✅ Device found at 0x");
      if (address < 16) debug.print("0");
      debug.print(address, HEX);
      
      // Identify common devices
      if (address == 0x68 || address == 0x69) {
        debug.print(" (ICM20948 IMU)");
      } else if (address == 0x29) {
        debug.print(" (VL53L0X ToF)");
      } else if (address == 0x40) {
        debug.print(" (PCA9685 Servo Driver)");
      } else if (address == 0x70) {
        debug.print(" (PCA9685 Sub-address)");
      }
      debug.println();
      nDevices++;
    }
  }
  
  if (nDevices == 0) {
    debug.println("❌ No I2C devices found! Check wiring and pull-up resistors.");
  } else {
    debug.print("✅ Found ");
    debug.print(nDevices);
    debug.println(" I2C devices\n");
  }
}

// ========== MOTOR CONTROL FUNCTIONS ==========
void setLeftMotor(int speed) {
  speed = constrain(speed, -255, 255);
  
  if (speed > 0) {
    digitalWrite(BIN1, HIGH);
    digitalWrite(BIN2, LOW);
    analogWrite(PWMB, speed);
  } else if (speed < 0) {
    digitalWrite(BIN1, LOW);
    digitalWrite(BIN2, HIGH);
    analogWrite(PWMB, -speed);
  } else {
    digitalWrite(BIN1, LOW);
    digitalWrite(BIN2, LOW);
    analogWrite(PWMB, 0);
  }
  
  currentLeftSpeed = speed;
}

void setRightMotor(int speed) {
  speed = constrain(speed, -255, 255);
  
  if (speed > 0) {
    digitalWrite(AIN1, HIGH);
    digitalWrite(AIN2, LOW);
    analogWrite(PWMA, speed);
  } else if (speed < 0) {
    digitalWrite(AIN1, LOW);
    digitalWrite(AIN2, HIGH);
    analogWrite(PWMA, -speed);
  } else {
    digitalWrite(AIN1, LOW);
    digitalWrite(AIN2, LOW);
    analogWrite(PWMA, 0);
  }
  
  currentRightSpeed = speed;
}

void stopMotors() {
  setLeftMotor(0);
  setRightMotor(0);
}

void emergencyStop() {
  stopMotors();
  digitalWrite(STBY, LOW);  // Disable motor driver
  delay(10);
  digitalWrite(STBY, HIGH); // Re-enable
  if (DEBUG_ENABLED) debug.println("🚨 EMERGENCY STOP!");
}

// ========== SERVO CONTROL FUNCTIONS ==========
void setServo(int channel, float angle) {
  angle = constrain(angle, 0, 180);
  int pulse = map(angle, 0, 180, SERVO_MIN, SERVO_MAX);
  pwm.setPWM(channel, 0, pulse);
}

void setAllServos() {
  setServo(BASE_SERVO, targetBaseAngle);
  setServo(RIGHT_ARM, targetRightAngle);
  setServo(LEFT_ARM, targetLeftAngle);
  setServo(GRIPPER, targetGripAngle);
  setServo(TOF_SERVO, targetTofAngle);
}

void resetServos() {
  targetBaseAngle = BASE_DEFAULT;
  targetRightAngle = RIGHT_DEFAULT;
  targetLeftAngle = LEFT_DEFAULT;
  targetGripAngle = GRIP_DEFAULT;
  targetTofAngle = TOF_DEFAULT;
  setAllServos();
  if (DEBUG_ENABLED) debug.println("🔄 Servos reset to defaults");
}

void testServos() {
  if (DEBUG_ENABLED) debug.println("🔄 Testing servos...");
  
  // Sweep base
  for (int i = BASE_MIN; i <= BASE_MAX; i += 10) {
    setServo(BASE_SERVO, i);
    delay(100);
  }
  setServo(BASE_SERVO, BASE_DEFAULT);
  
  // Test other servos briefly
  setServo(RIGHT_ARM, RIGHT_MAX);
  delay(300);
  setServo(RIGHT_ARM, RIGHT_DEFAULT);
  
  setServo(GRIPPER, GRIP_MAX);
  delay(300);
  setServo(GRIPPER, GRIP_DEFAULT);
  
  if (DEBUG_ENABLED) debug.println("✅ Servo test complete");
}

// ========== NRF24L01 FUNCTIONS ==========
void initNRF() {
  if (!radio.begin()) {
    if (DEBUG_ENABLED) debug.println("❌ NRF24L01 init failed!");
    return;
  }
  
  if (!radio.isChipConnected()) {
    if (DEBUG_ENABLED) debug.println("❌ NRF24L01 chip not connected!");
    return;
  }
  
  radio.setChannel(nrfChannel);
  radio.setPALevel(nrfPowerLevel);
  radio.setDataRate(nrfDataRate);
  radio.setPayloadSize(sizeof(DataPacket));
  radio.setRetries(5, 15);
  radio.openReadingPipe(0, nrfAddress);
  radio.startListening();
  
  if (DEBUG_ENABLED) {
    debug.println("✅ NRF24L01 initialized");
    debug.print("   Channel: "); debug.println(nrfChannel);
    debug.print("   Address: "); debug.println((char*)nrfAddress);
  }
}

void processNRF() {
  if (!nrfAvailable) return;
  
  if (!received.mode) {  // Drive mode
    // Joystick to differential drive
    int x = received.x - 512;  // Center at 0
    int y = received.y - 512;
    
    // Apply deadband
    const int DEADBAND = 20;
    if (abs(x) < DEADBAND) x = 0;
    if (abs(y) < DEADBAND) y = 0;
    
    // Map to motor speeds
    int forward = map(y, -512, 512, -255, 255);
    int turn = map(x, -512, 512, -255, 255);
    
    targetLeftSpeed = forward + turn;
    targetRightSpeed = forward - turn;
    
    // Constrain speeds
    targetLeftSpeed = constrain(targetLeftSpeed, -255, 255);
    targetRightSpeed = constrain(targetRightSpeed, -255, 255);
  } else {  // Arm mode
    targetLeftSpeed = 0;
    targetRightSpeed = 0;
    
    // Map joystick values to servo angles
    float speed = 1.5;  // Adjustment speed
    
    // Joystick 1 controls left arm and gripper
    float j1x = (received.x - 512) / 512.0;
    float j1y = (received.y - 512) / 512.0;
    
    // Joystick 2 controls base and right arm
    float j2x = (received.baseAngle - 512) / 512.0;
    float j2y = (received.rightArmAngle - 512) / 512.0;
    
    targetLeftAngle += j1y * speed;
    targetGripAngle += j1x * speed;
    targetBaseAngle += j2x * speed;
    targetRightAngle += j2y * speed;
    
    // Apply limits
    targetBaseAngle = constrain(targetBaseAngle, BASE_MIN, BASE_MAX);
    targetRightAngle = constrain(targetRightAngle, RIGHT_MIN, RIGHT_MAX);
    targetLeftAngle = constrain(targetLeftAngle, LEFT_MIN, LEFT_MAX);
    targetGripAngle = constrain(targetGripAngle, GRIP_MIN, GRIP_MAX);
  }
  
  // Handle buttons
  static bool lastReset = false;
  if (received.joy2Button && !lastReset) {
    resetServos();
    if (DEBUG_ENABLED) debug.println("🔄 NRF Reset triggered");
  }
  lastReset = received.joy2Button;
}

// ========== IMU FUNCTIONS ==========
void initIMU() {
  if (DEBUG_ENABLED) debug.println("🔄 Initializing ICM20948...");
  
  // Try both possible addresses with explicit checking
  bool found = false;
  
  Wire.beginTransmission(0x68);
  if (Wire.endTransmission() == 0) {
    icm.begin(Wire, 0x68);
    found = true;
    if (DEBUG_ENABLED) debug.println("   ICM20948 found at 0x68");
  } else {
    Wire.beginTransmission(0x69);
    if (Wire.endTransmission() == 0) {
      icm.begin(Wire, 0x69);
      found = true;
      if (DEBUG_ENABLED) debug.println("   ICM20948 found at 0x69");
    }
  }
  
  if (!found) {
    if (DEBUG_ENABLED) debug.println("❌ ICM20948 not found on I2C bus!");
    imuAvailable = false;
    return;
  }
  
  // Wait for sensor to initialize
  delay(100);
  
  if (icm.status != ICM_20948_Stat_Ok) {
    if (DEBUG_ENABLED) {
      debug.print("❌ ICM20948 init failed. Status: ");
      debug.println(icm.status);
    }
    imuAvailable = false;
    return;
  }
  
  // Initialize the sensor (without DMP for compatibility)
  imuAvailable = true;
  
  if (DEBUG_ENABLED) {
    debug.println("✅ ICM20948 initialized successfully!");
    uint8_t whoami = icm.getWhoAmI();
    debug.print("   WhoAmI: 0x"); debug.println(whoami, HEX);
  }
}

void readIMU() {
  if (!imuAvailable) {
    // Try to reinitialize if not available
    if (millis() - lastIMUDebug > 5000) {
      initIMU();
      lastIMUDebug = millis();
    }
    return;
  }
  
  // Check if data is ready
  if (icm.dataReady()) {
    icm.getAGMT();
    
    // Validate and convert readings
    if (!isnan(icm.accX()) && !isinf(icm.accX()) && abs(icm.accX()) < 20000) {
      imuData[0] = icm.accX() / 1000.0 * 9.81;  // Convert to m/s²
    }
    
    if (!isnan(icm.accY()) && !isinf(icm.accY()) && abs(icm.accY()) < 20000) {
      imuData[1] = icm.accY() / 1000.0 * 9.81;
    }
    
    if (!isnan(icm.accZ()) && !isinf(icm.accZ()) && abs(icm.accZ()) < 20000) {
      imuData[2] = icm.accZ() / 1000.0 * 9.81;
    }
    
    if (!isnan(icm.gyrX()) && !isinf(icm.gyrX()) && abs(icm.gyrX()) < 2000) {
      imuData[3] = icm.gyrX();  // °/s
    }
    
    if (!isnan(icm.gyrY()) && !isinf(icm.gyrY()) && abs(icm.gyrY()) < 2000) {
      imuData[4] = icm.gyrY();
    }
    
    if (!isnan(icm.gyrZ()) && !isinf(icm.gyrZ()) && abs(icm.gyrZ()) < 2000) {
      imuData[5] = icm.gyrZ();
    }
    
    // Magnetometer readings (if available)
    if (!isnan(icm.magX()) && !isinf(icm.magX()) && abs(icm.magX()) < 10000) {
      imuData[6] = icm.magX();  // µT
      imuData[7] = icm.magY();
      imuData[8] = icm.magZ();
    }
    
    // Print debug info every second
    if (DEBUG_ENABLED && millis() - lastIMUDebug > 1000) {
      debug.print("📊 IMU - Acc: ");
      debug.print(imuData[0], 2); debug.print(", ");
      debug.print(imuData[1], 2); debug.print(", ");
      debug.print(imuData[2], 2);
      debug.print(" | Gyro: ");
      debug.print(imuData[3], 2); debug.print(", ");
      debug.print(imuData[4], 2); debug.print(", ");
      debug.println(imuData[5], 2);
      lastIMUDebug = millis();
    }
  }
}

// ========== TOF SENSOR FUNCTIONS ==========
void initTOF() {
  if (DEBUG_ENABLED) debug.println("🔄 Initializing VL53L0X...");
  
  // Proper reset sequence
  pinMode(XSHUT_PIN, OUTPUT);
  digitalWrite(XSHUT_PIN, LOW);
  delay(100);
  digitalWrite(XSHUT_PIN, HIGH);
  delay(100);
  
  // Try to initialize
  if (lox.begin(0x30)) {
    tofAvailable = true;
    
    // Configure for better performance
    lox.configSensor(Adafruit_VL53L0X::VL53L0X_SENSE_DEFAULT);
    lox.setMeasurementTimingBudgetMicroSeconds(33000); // 33ms timing
    
    // Start continuous ranging
    lox.startRangeContinuous();
    
    if (DEBUG_ENABLED) {
      debug.println("✅ VL53L0X initialized!");
    }
  } else {
    if (DEBUG_ENABLED) {
      debug.println("❌ VL53L0X init failed!");
      debug.println("   Check wiring:");
      debug.println("     VCC → 3.3V");
      debug.println("     GND → GND");
      debug.println("     SDA → PB7 (with 4.7k pull-up)");
      debug.println("     SCL → PB6 (with 4.7k pull-up)");
      debug.println("     XSHUT → PA1");
    }
    tofAvailable = false;
  }
}

void readTOF() {
  if (!tofAvailable) {
    // Try to reinitialize every 5 seconds
    if (millis() - lastTofReinit > 5000) {
      initTOF();
      lastTofReinit = millis();
    }
    return;
  }
  
  if (millis() - lastTofRead >= TOF_INTERVAL) {
    if (lox.isRangeComplete()) {
      uint16_t range = lox.readRangeResult();
      
      // Check for valid range (65535 is error)
      if (range < 4000) {  // Valid range up to ~4 meters
        tofDistance = range;
        
        if (DEBUG_ENABLED && (millis() % 2000 < 100)) {
          debug.print("📏 ToF Distance: ");
          debug.print(tofDistance);
          debug.println(" mm");
        }
      } else {
        tofDistance = 0;  // Invalid reading
      }
      
      lastTofRead = millis();
    }
  }
}

// ========== ENCODER FUNCTIONS ==========
void updateEncoderSpeeds() {
  static long lastLeftCount = 0;
  static long lastRightCount = 0;
  static unsigned long lastTime = 0;
  
  unsigned long now = millis();
  float dt = (now - lastTime) / 1000.0;  // seconds
  
  if (dt >= 0.1) {  // Update every 100ms
    leftSpeed = (leftEncCount - lastLeftCount) / dt;
    rightSpeed = (rightEncCount - lastRightCount) / dt;
    
    lastLeftCount = leftEncCount;
    lastRightCount = rightEncCount;
    lastTime = now;
  }
}

// ========== JSON COMMAND PARSING ==========
void parseJSON(String json) {
  json.trim();
  if (json.length() == 0) return;
  
  if (DEBUG_ENABLED && (millis() % 1000 < 100)) {
    debug.print("📨 Parsing JSON: ");
    debug.println(json);
  }
  
  int cmdIndex = json.indexOf("\"cmd\"");
  if (cmdIndex < 0) return;
  
  int colon = json.indexOf(':', cmdIndex);
  if (colon < 0) return;
  
  int q1 = json.indexOf('"', colon);
  if (q1 < 0) return;
  
  int q2 = json.indexOf('"', q1 + 1);
  if (q2 < 0) return;
  
  String cmd = json.substring(q1 + 1, q2);
  
  if (cmd == "move") {
    parseMoveCommand(json);
  }
  else if (cmd == "servo") {
    parseServoCommand(json);
  }
  else if (cmd == "mode") {
    parseModeCommand(json);
  }
  else if (cmd == "reset") {
    resetServos();
    if (DEBUG_ENABLED) debug.println("🔄 Reset command received");
  }
  else if (cmd == "status") {
    sendStatus();
  }
  else if (cmd == "test") {
    testServos();
  }
  
  lastCmdTime = millis();
}

void parseMoveCommand(String json) {
  int left = extractIntValue(json, "left");
  int right = extractIntValue(json, "right");
  
  if (left != -999 && right != -999) {
    targetLeftSpeed = constrain(left, -255, 255);
    targetRightSpeed = constrain(right, -255, 255);
    
    if (DEBUG_ENABLED && (millis() % 500 < 100)) {
      debug.print("🚗 Move: L="); debug.print(targetLeftSpeed);
      debug.print(" R="); debug.println(targetRightSpeed);
    }
  }
}

void parseServoCommand(String json) {
  int ch = extractIntValue(json, "ch");
  int angle = extractIntValue(json, "angle");
  
  if (ch != -999 && angle != -999) {
    switch (ch) {
      case 1: targetBaseAngle = constrain(angle, BASE_MIN, BASE_MAX); break;
      case 3: targetRightAngle = constrain(angle, RIGHT_MIN, RIGHT_MAX); break;
      case 8: targetLeftAngle = constrain(angle, LEFT_MIN, LEFT_MAX); break;
      case 11: targetGripAngle = constrain(angle, GRIP_MIN, GRIP_MAX); break;
      case 5: targetTofAngle = constrain(angle, TOF_MIN, TOF_MAX); break;
    }
    
    if (DEBUG_ENABLED && (millis() % 500 < 100)) {
      debug.print("🦾 Servo ch"); debug.print(ch);
      debug.print(" = "); debug.println(angle);
    }
  }
}

void parseModeCommand(String json) {
  int modeIndex = json.indexOf("\"mode\"");
  if (modeIndex < 0) return;
  
  int colon = json.indexOf(':', modeIndex);
  if (colon < 0) return;
  
  int q1 = json.indexOf('"', colon);
  int q2 = json.indexOf('"', q1 + 1);
  
  if (q1 > 0 && q2 > 0) {
    String mode = json.substring(q1 + 1, q2);
    controlMode = (mode == "auto" || mode == "wifi") ? 1 : 0;
    
    if (DEBUG_ENABLED) {
      debug.print("⚙️ Mode set to: ");
      debug.println(controlMode ? "WiFi" : "NRF");
    }
  }
}

int extractIntValue(String json, String key) {
  int keyIndex = json.indexOf("\"" + key + "\"");
  if (keyIndex < 0) return -999;
  
  int colon = json.indexOf(':', keyIndex);
  if (colon < 0) return -999;
  
  int start = colon + 1;
  while (start < json.length() && json[start] == ' ') start++;
  
  int end = start;
  while (end < json.length() && json[end] != ',' && json[end] != '}' && json[end] != ' ') end++;
  
  if (end > start) {
    return json.substring(start, end).toInt();
  }
  
  return -999;
}

void processSerialCommands() {
  static String line = "";
  
  while (Serial1.available()) {
    char c = Serial1.read();
    if (c == '\n') {
      parseJSON(line);
      line = "";
    } else if (c != '\r') {
      line += c;
    }
  }
}

// ========== DATA TRANSMISSION ==========
void sendSensorData() {
  // Update all sensor readings
  readIMU();
  readTOF();
  updateEncoderSpeeds();
  
  // Build CSV string
  String data = "";
  data += String(millis()) + ",";
  data += String(leftEncCount) + ",";
  data += String(rightEncCount) + ",";
  data += String(imuData[0], 2) + ",";
  data += String(imuData[1], 2) + ",";
  data += String(imuData[2], 2) + ",";
  data += String(imuData[3], 2) + ",";
  data += String(imuData[4], 2) + ",";
  data += String(imuData[5], 2) + ",";
  data += String(imuData[6], 2) + ",";
  data += String(imuData[7], 2) + ",";
  data += String(imuData[8], 2) + ",";
  data += String(tofDistance) + ",";
  data += String((int)targetTofAngle) + ",";
  data += String((int)targetBaseAngle) + ",";
  data += String((int)targetRightAngle) + ",";
  data += String((int)targetLeftAngle) + ",";
  data += String((int)targetGripAngle) + ",";
  data += String(controlMode) + "\n";
  
  Serial1.print(data);
  
  if (DEBUG_ENABLED && (millis() % 1000 < 100)) {
    debug.print("📤 Sent: ");
    debug.print(data);
  }
}

void sendStatus() {
  String status = "STATUS:IMU=";
  status += String(imuAvailable ? 1 : 0);
  status += ",TOF=" + String(tofAvailable ? 1 : 0);
  status += ",NRF=" + String(nrfAvailable ? 1 : 0);
  status += ",MODE=" + String(controlMode);
  status += ",T=" + String(millis()) + "\n";
  
  Serial1.print(status);
  if (DEBUG_ENABLED) debug.print(status);
}

void sendHeartbeat() {
  if (millis() - lastHeartbeat >= 1000) {
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    lastHeartbeat = millis();
  }
}

// ========== SYSTEM INITIALIZATION ==========
void initPins() {
  // Motor pins
  pinMode(PWMA, OUTPUT);
  pinMode(AIN1, OUTPUT);
  pinMode(AIN2, OUTPUT);
  pinMode(PWMB, OUTPUT);
  pinMode(BIN1, OUTPUT);
  pinMode(BIN2, OUTPUT);
  pinMode(STBY, OUTPUT);
  
  digitalWrite(STBY, HIGH);  // Enable motor driver
  stopMotors();
  
  // Encoder pins with interrupts
  pinMode(LEFT_ENC_PIN, INPUT_PULLUP);
  pinMode(RIGHT_ENC_PIN, INPUT_PULLUP);
  
  attachInterrupt(digitalPinToInterrupt(LEFT_ENC_PIN), leftEncoderISR, RISING);
  attachInterrupt(digitalPinToInterrupt(RIGHT_ENC_PIN), rightEncoderISR, RISING);
  
  // Built-in LED
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
  
  if (DEBUG_ENABLED) debug.println("✅ Pins initialized");
}

void initI2C() {
  Wire.begin();
  Wire.setClock(400000);  // 400kHz fast mode
  delay(100);
  
  if (DEBUG_ENABLED) {
    scanI2CDevices();  // Run I2C scanner
  }
}

void initServos() {
  pwm.begin();
  pwm.setPWMFreq(SERVO_FREQ);
  delay(10);
  
  resetServos();
  
  if (DEBUG_ENABLED) debug.println("✅ Servo driver initialized");
}

void printSystemInfo() {
  printSeparator();
  debug.println("🤖 STM32 Robot Controller");
  debug.println("   Firmware: v" + String(FIRMWARE_VERSION));
  debug.println("   Compiled: " + String(__DATE__) + " " + String(__TIME__));
  printSeparator();
  
  debug.println("\n📊 System Status:");
  debug.println("   Control Mode: " + String(controlMode ? "WiFi" : "NRF"));
  debug.println("   IMU: " + String(imuAvailable ? "✅ OK" : "❌ FAIL"));
  debug.println("   TOF: " + String(tofAvailable ? "✅ OK" : "❌ FAIL"));
  debug.println("   NRF: " + String(radio.isChipConnected() ? "✅ OK" : "❌ FAIL"));
  printSeparator();
  debug.println();
}

// ========== MAIN SETUP ==========
void setup() {
  // Initialize debug serial
  debug.begin(9600);
  debug.println("\n\n🚀 STM32 Robot Controller Starting...");
  delay(100);
  
  // Initialize all hardware
  initPins();
  initI2C();
  initServos();
  initIMU();
  initTOF();
  initNRF();
  
  // Initialize ESP32 UART
  Serial1.begin(ESP_BAUD);
  
  // System ready
  systemReady = true;
  
  // Print system info
  printSystemInfo();
  
  // Send initial status
  sendStatus();
  
  debug.println("✅ System ready!\n");
}

// ========== MAIN LOOP ==========
void loop() {
  // 1. Check NRF24L01 for data
  if (radio.available()) {
    radio.read(&received, sizeof(received));
    nrfAvailable = true;
    lastNRFTime = millis();
  }
  
  // Check NRF timeout
  if (millis() - lastNRFTime > NRF_TIMEOUT) {
    if (nrfAvailable) {
      nrfAvailable = false;
      if (DEBUG_ENABLED) debug.println("⚠️ NRF timeout");
    }
  }
  
  // 2. Process WiFi commands from ESP32
  processSerialCommands();
  
  // 3. Control logic based on mode
  if (controlMode == 0) {  // NRF mode
    if (nrfAvailable) {
      processNRF();
    } else {
      // No NRF signal, stop motors
      targetLeftSpeed = 0;
      targetRightSpeed = 0;
    }
  }
  
  // 4. Safety checks
  if (controlMode == 1) {  // WiFi mode
    if (millis() - lastCmdTime > WIFI_TIMEOUT) {
      // No command received, stop motors
      targetLeftSpeed = 0;
      targetRightSpeed = 0;
    }
  }
  
  // 5. Apply motor commands with slew rate limiting
  const int MAX_CHANGE = 50;
  currentLeftSpeed += constrain(targetLeftSpeed - currentLeftSpeed, -MAX_CHANGE, MAX_CHANGE);
  currentRightSpeed += constrain(targetRightSpeed - currentRightSpeed, -MAX_CHANGE, MAX_CHANGE);
  
  setLeftMotor(currentLeftSpeed);
  setRightMotor(currentRightSpeed);
  
  // 6. Update servos
  setAllServos();
  
  // 7. Send sensor data periodically
  if (millis() - lastSensorSend >= SENSOR_INTERVAL) {
    sendSensorData();
    lastSensorSend = millis();
  }
  
  // 8. Heartbeat (LED blink)
  sendHeartbeat();
  
  // Small delay
  delay(10);
}

// ========== EMERGENCY STOP ON CRASH ==========
void HardFault_Handler() {
  emergencyStop();
  while(1) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(100);
    digitalWrite(LED_BUILTIN, LOW);
    delay(100);
  }
}