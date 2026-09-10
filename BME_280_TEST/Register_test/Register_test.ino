#include <Wire.h>

#define BME280_ADDR 0x76
#define SDA_PIN 21
#define SCL_PIN 22

void setup() {
  Serial.begin(115200);
  delay(1000);

  Wire.begin(SDA_PIN, SCL_PIN);

  Serial.println();
  Serial.println("BME280 Register Test");
  Serial.println("--------------------");

  // Select register 0xD0 (chip ID)
  Wire.beginTransmission(BME280_ADDR);
  Wire.write(0xD0);

  if (Wire.endTransmission() != 0) {
    Serial.println("ERROR: Could not communicate with sensor!");
    return;
  }

  // Request 1 byte from register 0xD0
  Wire.requestFrom(BME280_ADDR, 1);

  if (Wire.available()) {
    byte chipID = Wire.read();

    Serial.print("Chip ID: 0x");

    if (chipID < 0x10) {
      Serial.print("0");
    }

    Serial.println(chipID, HEX);

    Serial.println();

    if (chipID == 0x60) {
      Serial.println("SUCCESS: This is a genuine BME280!");
    }
    else if (chipID == 0x56 || chipID == 0x57 || chipID == 0x58) {
      Serial.println("This appears to be a BMP280, not a BME280.");
    }
    else {
      Serial.println("Unknown chip ID.");
    }
  }
  else {
    Serial.println("ERROR: No data received!");
  }
}

void loop() {
}