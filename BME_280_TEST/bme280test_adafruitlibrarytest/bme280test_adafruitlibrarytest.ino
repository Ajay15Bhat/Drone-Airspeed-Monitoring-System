#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>

#define SDA_PIN 21
#define SCL_PIN 22

Adafruit_BME280 bme;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("================================");
  Serial.println("BME280 ADAFRUIT LIBRARY TEST");
  Serial.println("================================");

  // Start I2C
  Wire.begin(SDA_PIN, SCL_PIN);

  // BME280 is at address 0x76
  if (!bme.begin(0x76, &Wire)) {
    Serial.println("ERROR: Could not find BME280!");
    Serial.println("Check wiring and I2C address.");
    while (1);
  }

  Serial.println("BME280 detected successfully!");
  Serial.println();
}

void loop() {

  Serial.println("--------------------------------");

  Serial.print("Temperature : ");
  Serial.print(bme.readTemperature(), 2);
  Serial.println(" °C");

  Serial.print("Pressure    : ");
  Serial.print(bme.readPressure() / 100.0F, 2);
  Serial.println(" hPa");

  Serial.print("Humidity    : ");
  Serial.print(bme.readHumidity(), 2);
  Serial.println(" %");

  delay(2000);
}