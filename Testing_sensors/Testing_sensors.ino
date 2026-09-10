#include <Wire.h>
void setup() {
  Wire.begin();
  Serial.begin(115200);
  Serial.println("Scanning I2C bus...");
}
void loop() {
  byte error, address;
  int count = 0;
  for (address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();
    if (error == 0) {
      Serial.print("Device found at 0x");
      Serial.println(address, HEX);
      count++;
    }
  }
  if (count == 0) Serial.println("No I2C devices found");
  delay(5000);
}
