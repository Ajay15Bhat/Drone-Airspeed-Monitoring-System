/*
  Week-1 airspeed CSV source for ESP32.

  Confirmed from the working project sketches:
    BME280: I2C 0x76, chip-ID register 0xD0 must read 0x60
    MPU-6500 (used through the MPU6050 board): I2C 0x68, WHO_AM_I 0x75 reads 0x70

  Honeywell ABP2MRRN004NDSA3XE:
    ±4 inH2O differential, SPI mode 0, 3.3 V, 10–90 % of 24-bit transfer function.
    Set USE_MOCK_ABP2 to false after wiring it. SPI pins below are ESP32 defaults;
    change only the pin constants if your board wiring is different.
*/

#include <Wire.h>
#include <SPI.h>
#include <Adafruit_BME280.h>

constexpr bool USE_MOCK_ABP2 = true;  // Keep true until the ABP2 is installed.

constexpr uint8_t BME280_ADDR = 0x76;
constexpr uint8_t BME280_CHIP_ID_REG = 0xD0;
constexpr uint8_t BME280_CHIP_ID = 0x60;
constexpr uint8_t MPU_ADDR = 0x68;
constexpr uint8_t MPU_WHO_AM_I_REG = 0x75;
constexpr uint8_t MPU_CHIP_ID = 0x70;  // Actual value reported by MPU6050_TEST.

constexpr int SDA_PIN = 21;
constexpr int SCL_PIN = 22;
constexpr int ABP2_SCLK_PIN = 18;
constexpr int ABP2_MISO_PIN = 19;
constexpr int ABP2_MOSI_PIN = 23;
constexpr int ABP2_CS_PIN = 5;

constexpr float ABP2_PMIN_INH2O = -4.0F;
constexpr float ABP2_PMAX_INH2O = 4.0F;
constexpr float ABP2_OUTPUT_MIN = 1677722.0F;   // 10 % of 2^24
constexpr float ABP2_OUTPUT_MAX = 15099494.0F;  // 90 % of 2^24
constexpr float INH2O_TO_PA = 249.08891F;
constexpr uint32_t SAMPLE_PERIOD_MS = 100;

// Leave these at unity/zero until Week-3 calibration produces a curve.
constexpr float AIRSPEED_CAL_GAIN = 1.0F;
constexpr float AIRSPEED_CAL_OFFSET_MPS = 0.0F;

Adafruit_BME280 bme;
uint32_t nextSampleMs = 0;

uint8_t readI2CRegister(uint8_t address, uint8_t reg) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0 || Wire.requestFrom(address, (uint8_t)1) != 1 || !Wire.available()) {
    return 0xFF;
  }
  return Wire.read();
}

bool writeMPURegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool readMPUFrame(int16_t &ax, int16_t &ay, int16_t &az, int16_t &gx, int16_t &gy, int16_t &gz) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);  // ACCEL_XOUT_H
  if (Wire.endTransmission(false) != 0 || Wire.requestFrom(MPU_ADDR, (uint8_t)14) != 14) return false;
  ax = (Wire.read() << 8) | Wire.read();
  ay = (Wire.read() << 8) | Wire.read();
  az = (Wire.read() << 8) | Wire.read();
  Wire.read(); Wire.read();  // MPU internal temperature; not logged.
  gx = (Wire.read() << 8) | Wire.read();
  gy = (Wire.read() << 8) | Wire.read();
  gz = (Wire.read() << 8) | Wire.read();
  return true;
}

float abp2CountsToInH2O(uint32_t counts) {
  return ((counts - ABP2_OUTPUT_MIN) * (ABP2_PMAX_INH2O - ABP2_PMIN_INH2O) /
          (ABP2_OUTPUT_MAX - ABP2_OUTPUT_MIN)) + ABP2_PMIN_INH2O;
}

bool readABP2(uint32_t &pressureCounts, float &pressureInH2O, float &sensorTempC, uint8_t &status) {
  if (USE_MOCK_ABP2) {
    const float elapsedS = millis() / 1000.0F;
    pressureInH2O = 0.7F + 0.35F * sinf(elapsedS * 0.8F);
    pressureCounts = (uint32_t)(ABP2_OUTPUT_MIN +
      (pressureInH2O - ABP2_PMIN_INH2O) * (ABP2_OUTPUT_MAX - ABP2_OUTPUT_MIN) /
      (ABP2_PMAX_INH2O - ABP2_PMIN_INH2O));
    sensorTempC = 25.0F;
    status = 0x40;  // Powered, not busy, no error.
    return true;
  }

  uint8_t data[7];
  SPI.beginTransaction(SPISettings(200000, MSBFIRST, SPI_MODE0));
  digitalWrite(ABP2_CS_PIN, LOW);
  SPI.transfer(0xAA); SPI.transfer(0x00); SPI.transfer(0x00);  // Measurement command.
  digitalWrite(ABP2_CS_PIN, HIGH);
  delay(5);  // Datasheet conversion wait.
  digitalWrite(ABP2_CS_PIN, LOW);
  data[0] = SPI.transfer(0xF0);  // NOP; returned byte is the status byte.
  for (uint8_t i = 1; i < 7; ++i) data[i] = SPI.transfer(0x00);
  digitalWrite(ABP2_CS_PIN, HIGH);
  SPI.endTransaction();

  status = data[0];
  pressureCounts = ((uint32_t)data[1] << 16) | ((uint32_t)data[2] << 8) | data[3];
  const uint32_t tempCounts = ((uint32_t)data[4] << 16) | ((uint32_t)data[5] << 8) | data[6];
  pressureInH2O = abp2CountsToInH2O(pressureCounts);
  sensorTempC = (tempCounts * 200.0F / 16777215.0F) - 50.0F;
  return (status & 0x65) == 0x40;  // powered; not busy; no memory/math error.
}

float humidAirDensity(float tempC, float pressureHpa, float humidityPct) {
  const float temperatureK = tempC + 273.15F;
  const float totalPressurePa = pressureHpa * 100.0F;
  const float saturationVaporPa = 610.94F * expf((17.625F * tempC) / (tempC + 243.04F));
  const float vaporPa = constrain(humidityPct, 0.0F, 100.0F) / 100.0F * saturationVaporPa;
  return (totalPressurePa - vaporPa) / (287.05F * temperatureK) + vaporPa / (461.495F * temperatureK);
}

void setup() {
  Serial.begin(115200);
  Wire.begin(SDA_PIN, SCL_PIN);

  if (readI2CRegister(BME280_ADDR, BME280_CHIP_ID_REG) != BME280_CHIP_ID || !bme.begin(BME280_ADDR, &Wire)) {
    Serial.println("# ERROR: BME280 expected at 0x76 with chip ID 0x60");
    while (true) delay(1000);
  }
  if (readI2CRegister(MPU_ADDR, MPU_WHO_AM_I_REG) != MPU_CHIP_ID) {
    Serial.println("# ERROR: MPU expected at 0x68 with WHO_AM_I 0x70");
    while (true) delay(1000);
  }
  writeMPURegister(0x6B, 0x00);  // Wake MPU-6500.
  writeMPURegister(0x1C, 0x10);  // ±8 g: 4096 LSB/g.
  writeMPURegister(0x1B, 0x08);  // ±500 deg/s: 65.5 LSB/(deg/s).

  if (!USE_MOCK_ABP2) {
    SPI.begin(ABP2_SCLK_PIN, ABP2_MISO_PIN, ABP2_MOSI_PIN, ABP2_CS_PIN);
    pinMode(ABP2_CS_PIN, OUTPUT);
    digitalWrite(ABP2_CS_PIN, HIGH);
  }
  Serial.println("timestamp_ms,source,temp_C,pressure_hPa,humidity_pct,accel_x_g,accel_y_g,accel_z_g,gyro_x_dps,gyro_y_dps,gyro_z_dps,diff_pressure_counts,diff_pressure_inH2O,diff_pressure_Pa,abp_temperature_C,abp_status,airspeed_raw_mps,airspeed_calibrated_mps,reference_speed_mps");
}

void loop() {
  if ((int32_t)(millis() - nextSampleMs) < 0) return;
  nextSampleMs = millis() + SAMPLE_PERIOD_MS;

  const float tempC = bme.readTemperature();
  const float pressureHpa = bme.readPressure() / 100.0F;
  const float humidityPct = bme.readHumidity();
  int16_t ax, ay, az, gx, gy, gz;
  if (!readMPUFrame(ax, ay, az, gx, gy, gz)) return;

  uint32_t pressureCounts;
  float pressureInH2O, abpTempC;
  uint8_t abpStatus;
  if (!readABP2(pressureCounts, pressureInH2O, abpTempC, abpStatus)) return;

  const float pressurePa = pressureInH2O * INH2O_TO_PA;
  const float rawAirspeedMps = sqrtf(2.0F * max(pressurePa, 0.0F) / 1.225F);
  const float density = humidAirDensity(tempC, pressureHpa, humidityPct);
  const float calibratedAirspeedMps = sqrtf(2.0F * max(pressurePa, 0.0F) / density) * AIRSPEED_CAL_GAIN + AIRSPEED_CAL_OFFSET_MPS;

  Serial.printf("%lu,%s,%.2f,%.2f,%.2f,%.4f,%.4f,%.4f,%.3f,%.3f,%.3f,%lu,%.5f,%.3f,%.2f,0x%02X,%.3f,%.3f,\n",
    millis(), USE_MOCK_ABP2 ? "mock" : "live", tempC, pressureHpa, humidityPct,
    ax / 4096.0F, ay / 4096.0F, az / 4096.0F, gx / 65.5F, gy / 65.5F, gz / 65.5F,
    pressureCounts, pressureInH2O, pressurePa, abpTempC, abpStatus, rawAirspeedMps, calibratedAirspeedMps);
}
