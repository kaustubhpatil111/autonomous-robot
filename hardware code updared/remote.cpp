#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);
const byte address[6] = "NODE1";

const int JOY1_X = A0, JOY1_Y = A1, JOY1_SW = 2;
const int JOY2_X = A2, JOY2_Y = A3, JOY2_SW = 3;
#define DEADBAND 20

struct DataPacket {
  int16_t x, y, baseAngle, rightArmAngle, leftArmAngle, gripperAngle;
  bool joy1Button, joy2Button, mode;
} data;

bool currentMode = false;
unsigned long lastButtonPress = 0;
const unsigned long debounceDelay = 300;
bool gripperState = false, lastGripperButton = false;

int applyDeadband(int val) {
  if (abs(val - 512) < DEADBAND) return 512;
  return val;
}

void setup() {
  Serial.begin(9600);
  pinMode(JOY1_SW, INPUT_PULLUP);
  pinMode(JOY2_SW, INPUT_PULLUP);
  radio.begin();
  radio.setPALevel(RF24_PA_HIGH);
  radio.setDataRate(RF24_250KBPS);
  radio.openWritingPipe(address);
  radio.stopListening();
  data.mode = false;
}

void loop() {
  data.x = applyDeadband(analogRead(JOY1_X));
  data.y = applyDeadband(analogRead(JOY1_Y));
  data.baseAngle = applyDeadband(analogRead(JOY2_X));
  data.rightArmAngle = applyDeadband(analogRead(JOY2_Y));

  bool joy1Pressed = !digitalRead(JOY1_SW);
  bool joy2Pressed = !digitalRead(JOY2_SW);

  data.joy1Button = joy1Pressed;
  data.joy2Button = joy2Pressed;

  if (joy1Pressed && (millis() - lastButtonPress) > debounceDelay) {
    currentMode = !currentMode;
    data.mode = currentMode;
    lastButtonPress = millis();
  }

  if (currentMode) {
    // ARM MODE: left arm and gripper from JOY1
    data.leftArmAngle = data.y;
    data.gripperAngle = data.x;
  } else {
    // DRIVE MODE: left arm angle unused, gripper toggles with JOY2
    data.leftArmAngle = 512;
    if (joy2Pressed && !lastGripperButton) {
      gripperState = !gripperState;
      data.gripperAngle = gripperState ? 1023 : 0;
    }
  }

  lastGripperButton = joy2Pressed;
  radio.write(&data, sizeof(data));
  delay(30);
}