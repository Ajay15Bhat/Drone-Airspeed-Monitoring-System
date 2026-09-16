/*
  Honeywell ABP2MRRN004NDSA3XE standalone SPI test

  Test-PCB to ESP32 wiring:
    POWER+   -> 3V3
    GND      -> GND
    SDA/MOSI -> GPIO 23
    SCL/SCLK -> GPIO 18
    EOC/MISO -> GPIO 19
    NC/SS    -> GPIO 5

  Leave SENSE+ and SENSE- disconnected.
*/

#include <SPI.h>

constexpr int SCLK_PIN = 18;
constexpr int MISO_PIN = 19;
constexpr int MOSI_PIN = 23;
constexpr int CS_PIN = 5;

constexpr float PMIN_INH2O = -4.0F;
constexpr float PMAX_INH2O = 4.0F;
constexpr float OUTPUT_MIN = 1677722.0F;   // 10% of 2^24
constexpr float OUTPUT_MAX = 15099494.0F;  // 90% of 2^24
constexpr float INH2O_TO_PA = 249.08891F;

void printHexByte(uint8_t value) {
  if (value < 0x10) Serial.print('0');
  Serial.print(value, HEX);
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nABP2 SPI standalone test");
  Serial.println("Expected healthy status: 0x40 (powered, ready, no errors)");

  SPI.begin(SCLK_PIN, MISO_PIN, MOSI_PIN, CS_PIN);
  pinMode(CS_PIN, OUTPUT);
  digitalWrite(CS_PIN, HIGH);

  // Safe initial SS pulse; Honeywell specifies this for a shared SPI bus.
  digitalWrite(CS_PIN, LOW);
  delayMicroseconds(250);
  digitalWrite(CS_PIN, HIGH);
  delay(10);
}

void loop() {
  uint8_t data[7];

  SPI.beginTransaction(SPISettings(200000, MSBFIRST, SPI_MODE0));

  // Start one compensated pressure/temperature conversion.
  digitalWrite(CS_PIN, LOW);
  SPI.transfer(0xAA);
  SPI.transfer(0x00);
  SPI.transfer(0x00);
  digitalWrite(CS_PIN, HIGH);

  delay(10);  // More than the 5 ms minimum conversion time.

  // Read status + 24-bit pressure + 24-bit temperature.
  digitalWrite(CS_PIN, LOW);
  data[0] = SPI.transfer(0xF0);  // NOP; sensor returns status here.
  for (uint8_t i = 1; i < 7; ++i) data[i] = SPI.transfer(0x00);
  digitalWrite(CS_PIN, HIGH);
  SPI.endTransaction();

  const uint8_t status = data[0];
  const uint32_t pressureCounts = ((uint32_t)data[1] << 16) | ((uint32_t)data[2] << 8) | data[3];
  const uint32_t tempCounts = ((uint32_t)data[4] << 16) | ((uint32_t)data[5] << 8) | data[6];
  const float pressureInH2O = ((pressureCounts - OUTPUT_MIN) * (PMAX_INH2O - PMIN_INH2O) /
                              (OUTPUT_MAX - OUTPUT_MIN)) + PMIN_INH2O;
  const float sensorTempC = (tempCounts * 200.0F / 16777215.0F) - 50.0F;

  Serial.print("raw: ");
  for (uint8_t i = 0; i < 7; ++i) {
    Serial.print("0x");
    printHexByte(data[i]);
    if (i < 6) Serial.print(' ');
  }
  Serial.println();

  Serial.print("status: 0x");
  printHexByte(status);
  Serial.print(" | powered="); Serial.print((status & 0x40) ? "yes" : "no");
  Serial.print(" busy="); Serial.print((status & 0x20) ? "yes" : "no");
  Serial.print(" memory_error="); Serial.print((status & 0x04) ? "yes" : "no");
  Serial.print(" math_saturation="); Serial.println((status & 0x01) ? "yes" : "no");

  Serial.print("pressure counts: "); Serial.println(pressureCounts);
  Serial.print("pressure: "); Serial.print(pressureInH2O, 5); Serial.print(" inH2O | ");
  Serial.print(pressureInH2O * INH2O_TO_PA, 2); Serial.println(" Pa");
  Serial.print("sensor temperature: "); Serial.print(sensorTempC, 2); Serial.println(" C");
  Serial.println("---");
  delay(1000);
}
