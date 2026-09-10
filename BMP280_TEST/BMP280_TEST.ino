#include <Wire.h>

#define BMP_ADDR 0x76

uint8_t readReg(uint8_t reg) {
  Wire.beginTransmission(BMP_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);

  Wire.requestFrom(BMP_ADDR, 1);

  if (Wire.available()) {
    return Wire.read();
  }

  return 0xFF;
}

void writeReg(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(BMP_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);

  delay(500);

  Serial.println("BMP280 PRESSURE TEST");
  Serial.println("--------------------");

  // Temperature x1
  // Pressure x1
  // Normal mode
  writeReg(0xF4, 0x27);

  delay(100);

  Serial.print("CTRL_MEAS = 0x");
  Serial.println(readReg(0xF4), HEX);

  Serial.print("STATUS    = 0x");
  Serial.println(readReg(0xF3), HEX);
}

void loop() {

  uint8_t p1 = readReg(0xF7);
  uint8_t p2 = readReg(0xF8);
  uint8_t p3 = readReg(0xF9);

  uint8_t t1 = readReg(0xFA);
  uint8_t t2 = readReg(0xFB);
  uint8_t t3 = readReg(0xFC);

  Serial.print("PRESS RAW = 0x");
  if (p1 < 0x10) Serial.print("0");
  Serial.print(p1, HEX);

  if (p2 < 0x10) Serial.print("0");
  Serial.print(p2, HEX);

  if (p3 < 0x10) Serial.print("0");
  Serial.println(p3, HEX);

  Serial.print("TEMP RAW  = 0x");
  if (t1 < 0x10) Serial.print("0");
  Serial.print(t1, HEX);

  if (t2 < 0x10) Serial.print("0");
  Serial.print(t2, HEX);

  if (t3 < 0x10) Serial.print("0");
  Serial.println(t3, HEX);

  Serial.println();

  delay(1000);
}