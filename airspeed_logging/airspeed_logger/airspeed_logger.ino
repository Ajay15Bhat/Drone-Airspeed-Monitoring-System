/*
  ESP32 airspeed data logger.

  Sensors on the shared I2C bus (SDA GPIO21, SCL GPIO22 at 100 kHz):
    BME280 at 0x76, chip ID 0x60
    MPU-6500-compatible board at 0x68, WHO_AM_I 0x70
    Honeywell ABP3 at 0x6C

  Before powering the ESP32, leave the ABP3 SENSE+ and SENSE- ports at equal
  pressure. setup() uses 32 ABP3 single-shot readings to establish a tare.
  The ABP3 pressure scale has not yet been calibrated, so this sketch records
  counts only. It deliberately leaves pressure-in-Pa and airspeed CSV fields
  blank until a known-pressure calibration supplies Pa/count.
*/

#include <Wire.h>
#include <Adafruit_BME280.h>

constexpr uint8_t BME280_ADDR = 0x76;
constexpr uint8_t BME280_CHIP_ID_REG = 0xD0;
constexpr uint8_t BME280_CHIP_ID = 0x60;
constexpr uint8_t MPU_ADDR = 0x68;
constexpr uint8_t MPU_WHO_AM_I_REG = 0x75;
constexpr uint8_t MPU_CHIP_ID = 0x70;

constexpr uint8_t ABP3_ADDR = 0x6C;
constexpr uint8_t ABP3_COMMAND_REG = 0x22;
constexpr uint8_t ABP3_DATA_REG = 0x2E;
constexpr uint16_t ABP3_START_SINGLE_SHOT = 0x8B93;
constexpr uint16_t ABP3_CONVERSION_WAIT_MS = 10;
constexpr uint8_t ABP3_TARE_SAMPLES = 32;

constexpr int SDA_PIN = 21;
constexpr int SCL_PIN = 22;
constexpr uint32_t I2C_CLOCK_HZ = 100000;
constexpr uint32_t SAMPLE_PERIOD_MS = 100;

Adafruit_BME280 bme;
uint32_t nextSampleMs = 0;
int32_t abp3TareCounts = 0;

uint8_t readI2CRegister(uint8_t address, uint8_t reg) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0 || Wire.requestFrom(address, (uint8_t)1) != 1 || !Wire.available()) {
    return 0xFF;
  }
  return Wire.read();
}

bool probeI2CDevice(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
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

bool writeABP3Register16(uint8_t reg, uint16_t value) {
  Wire.beginTransmission(ABP3_ADDR);
  Wire.write(reg);
  Wire.write((uint8_t)(value & 0xFF));         // ABP3 command words are LSB first.
  Wire.write((uint8_t)((value >> 8) & 0xFF));
  return Wire.endTransmission(true) == 0;
}

bool readABP3Bytes(uint8_t reg, uint8_t *buffer, uint8_t length) {
  Wire.beginTransmission(ABP3_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0 || Wire.requestFrom(ABP3_ADDR, length, true) != length) return false;
  for (uint8_t i = 0; i < length; ++i) buffer[i] = Wire.read();
  return true;
}

bool readABP3(int16_t &pressureRawCounts, float &temperatureC, uint16_t &status) {
  if (!writeABP3Register16(ABP3_COMMAND_REG, ABP3_START_SINGLE_SHOT)) return false;
  delay(ABP3_CONVERSION_WAIT_MS);

  uint8_t data[6];
  if (!readABP3Bytes(ABP3_DATA_REG, data, sizeof(data))) return false;

  const uint16_t temperatureWord = ((uint16_t)data[1] << 8) | data[0];
  const uint16_t pressureWord = ((uint16_t)data[3] << 8) | data[2];
  status = ((uint16_t)data[5] << 8) | data[4];  // STATUS_SYNC register.
  const int16_t temperatureCounts = (int16_t)temperatureWord;
  pressureRawCounts = (int16_t)pressureWord;
  temperatureC = (temperatureCounts + 16485.0F) / 387.88F;
  return true;
}

bool tareABP3() {
  int32_t totalCounts = 0;
  for (uint8_t i = 0; i < ABP3_TARE_SAMPLES; ++i) {
    int16_t pressureRawCounts;
    float temperatureC;
    uint16_t status;
    if (!readABP3(pressureRawCounts, temperatureC, status)) return false;
    totalCounts += pressureRawCounts;
  }
  // Round to the nearest whole count, including negative averages.
  abp3TareCounts = totalCounts >= 0 ?
    (totalCounts + ABP3_TARE_SAMPLES / 2) / ABP3_TARE_SAMPLES :
    (totalCounts - ABP3_TARE_SAMPLES / 2) / ABP3_TARE_SAMPLES;
  return true;
}

void setup() {
  Serial.begin(115200);
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(I2C_CLOCK_HZ);

  if (readI2CRegister(BME280_ADDR, BME280_CHIP_ID_REG) != BME280_CHIP_ID || !bme.begin(BME280_ADDR, &Wire)) {
    Serial.println("# ERROR: BME280 expected at 0x76 with chip ID 0x60");
    while (true) delay(1000);
  }
  if (readI2CRegister(MPU_ADDR, MPU_WHO_AM_I_REG) != MPU_CHIP_ID) {
    Serial.println("# ERROR: MPU expected at 0x68 with WHO_AM_I 0x70");
    while (true) delay(1000);
  }
  if (!probeI2CDevice(ABP3_ADDR)) {
    Serial.println("# ERROR: ABP3 expected at 0x6C");
    while (true) delay(1000);
  }

  writeMPURegister(0x6B, 0x00);  // Wake MPU-6500.
  writeMPURegister(0x1C, 0x10);  // +/-8 g: 4096 LSB/g.
  writeMPURegister(0x1B, 0x08);  // +/-500 deg/s: 65.5 LSB/(deg/s).

  Serial.println("# ABP3 startup tare: keep SENSE+ and SENSE- at equal pressure.");
  if (!tareABP3()) {
    Serial.println("# ERROR: ABP3 tare failed");
    while (true) delay(1000);
  }
  Serial.printf("# ABP3 tare_counts=%ld samples=%u\n", (long)abp3TareCounts, ABP3_TARE_SAMPLES);
  Serial.println("timestamp_ms,source,temp_C,pressure_hPa,humidity_pct,accel_x_g,accel_y_g,accel_z_g,gyro_x_dps,gyro_y_dps,gyro_z_dps,abp3_pressure_raw_counts,abp3_pressure_zeroed_counts,abp3_temperature_C,abp3_status,diff_pressure_Pa,airspeed_raw_mps,airspeed_calibrated_mps,reference_speed_mps");
}

void loop() {
  if ((int32_t)(millis() - nextSampleMs) < 0) return;
  nextSampleMs = millis() + SAMPLE_PERIOD_MS;

  const float tempC = bme.readTemperature();
  const float pressureHpa = bme.readPressure() / 100.0F;
  const float humidityPct = bme.readHumidity();
  int16_t ax, ay, az, gx, gy, gz;
  if (!readMPUFrame(ax, ay, az, gx, gy, gz)) return;

  int16_t pressureRawCounts;
  float abp3TempC;
  uint16_t abp3Status;
  if (!readABP3(pressureRawCounts, abp3TempC, abp3Status)) return;
  const int32_t pressureZeroedCounts = (int32_t)pressureRawCounts - abp3TareCounts;

  // Pa/count is intentionally unknown. The final four CSV fields remain empty.
  Serial.printf("%lu,live,%.2f,%.2f,%.2f,%.4f,%.4f,%.4f,%.3f,%.3f,%.3f,%d,%ld,%.2f,0x%04X,,,,\n",
    millis(), tempC, pressureHpa, humidityPct,
    ax / 4096.0F, ay / 4096.0F, az / 4096.0F, gx / 65.5F, gy / 65.5F, gz / 65.5F,
    pressureRawCounts, (long)pressureZeroedCounts, abp3TempC, abp3Status);
}
