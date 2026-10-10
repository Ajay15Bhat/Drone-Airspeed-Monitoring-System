/*
  ESP32 airspeed data logger.

  Sensors on the shared I2C bus (SDA GPIO21, SCL GPIO22 at 100 kHz):
    BME280 at 0x76, chip ID 0x60
    MPU-6500-compatible board at 0x68, WHO_AM_I 0x70
    Honeywell ABP3 at 0x6C

  Before powering the ESP32, leave the ABP3 SENSE+ and SENSE- ports at equal
  pressure. setup() uses 32 ABP3 single-shot readings to establish a tare.
  The ABP3 uses the mentor-provided standard 10 % to 90 % digital transfer
  function for this +/-1 kPa differential configuration:
    -25600 counts = -1 kPa, +25600 counts = +1 kPa.
  After startup tare, zeroed counts are converted to differential pressure,
  then to standard-density and BME280-density-compensated Bernoulli airspeed.
*/

#include <Wire.h>
#include <Adafruit_BME280.h>
#include <math.h>

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
constexpr float ABP3_FULL_SCALE_PRESSURE_PA = 1000.0F;
constexpr float ABP3_TRANSFER_COUNTS_AT_FULL_SCALE = 25600.0F;
constexpr float ABP3_PA_PER_COUNT =
  ABP3_FULL_SCALE_PRESSURE_PA / ABP3_TRANSFER_COUNTS_AT_FULL_SCALE;  // 0.0390625 Pa/count.

constexpr float STANDARD_AIR_DENSITY_KG_M3 = 1.225F;
constexpr float DRY_AIR_GAS_CONSTANT = 287.058F;
constexpr float WATER_VAPOR_GAS_CONSTANT = 461.495F;

constexpr int SDA_PIN = 21;
constexpr int SCL_PIN = 22;
constexpr uint32_t I2C_CLOCK_HZ = 100000;
constexpr uint32_t SAMPLE_PERIOD_MS = 100;
constexpr uint16_t ABP3_FAULT_MASK = 0x0D80; // CRC, saturation, bridge check/supply.
constexpr float KALMAN_Q_RATE = 4.0F; // Pa^2/s; experimental, not calibrated.
constexpr float KALMAN_R = 121.0F;    // Pa^2; experimental.
bool filterReady = false;
float filteredPressure = 0, filterVariance = KALMAN_R;
uint32_t filterTimeMs = 0;

float updatePressureFilter(float measurement, uint32_t now) {
  if (!isfinite(measurement)) { filterReady = false; return NAN; }
  if (!filterReady || (uint32_t)(now - filterTimeMs) > 1000) {
    filteredPressure = measurement;
    filterVariance = KALMAN_R;
    filterReady = true;
  } else {
    float predicted = filterVariance + KALMAN_Q_RATE * ((uint32_t)(now - filterTimeMs) / 1000.0F);
    float gain = predicted / (predicted + KALMAN_R);
    filteredPressure += gain * (measurement - filteredPressure);
    filterVariance = (1.0F - gain) * predicted;
  }
  filterTimeMs = now;
  return filteredPressure;
}

Adafruit_BME280 bme;
uint32_t nextSampleMs = 0;
int32_t abp3TareCounts = 0;

float calculateMoistAirDensity(float temperatureC, float pressureHpa, float humidityPct) {
  const float temperatureK = temperatureC + 273.15F;
  if (!isfinite(temperatureC) || !isfinite(pressureHpa) || !isfinite(humidityPct) ||
      temperatureC < -40 || temperatureC > 85 || pressureHpa < 300 || pressureHpa > 1100 ||
      humidityPct < 0 || humidityPct > 100) return NAN;

  const float boundedHumidityPct = constrain(humidityPct, 0.0F, 100.0F);
  const float saturationVaporPressurePa =
    6.1078F * powf(10.0F, (7.5F * temperatureC) / (temperatureC + 237.3F)) * 100.0F;
  const float vaporPressurePa = (boundedHumidityPct / 100.0F) * saturationVaporPressurePa;
  const float dryAirPressurePa = max(0.0F, pressureHpa * 100.0F - vaporPressurePa);
  return dryAirPressurePa / (DRY_AIR_GAS_CONSTANT * temperatureK) +
    vaporPressurePa / (WATER_VAPOR_GAS_CONSTANT * temperatureK);
}

float pressurePaToAirspeedMps(float differentialPressurePa, float densityKgM3) {
  if (!isfinite(differentialPressurePa) || !isfinite(densityKgM3) || densityKgM3 <= 0.0F) return NAN;
  if (differentialPressurePa <= 0.0F) return 0.0F;
  return sqrtf((2.0F * differentialPressurePa) / densityKgM3);
}

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
    if (!readABP3(pressureRawCounts, temperatureC, status) || (status & ABP3_FAULT_MASK) || !(status & 0x08)) return false;
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

  if (!writeMPURegister(0x6B, 0x00) || !writeMPURegister(0x1C, 0x10) || !writeMPURegister(0x1B, 0x08)) {
    Serial.println("# ERROR: MPU configuration failed");
    while (true) delay(1000);
  }

  Serial.println("# ABP3 startup tare: keep SENSE+ and SENSE- at equal pressure.");
  if (!tareABP3()) {
    Serial.println("# ERROR: ABP3 tare failed");
    while (true) delay(1000);
  }
  Serial.printf("# ABP3 tare_counts=%ld samples=%u\n", (long)abp3TareCounts, ABP3_TARE_SAMPLES);
  Serial.println("# schema=2 accuracy=unvalidated filter=pressure_random_walk Q=4Pa2/s R=121Pa2 no_IMU_fusion");
  Serial.println("timestamp_ms,source,temp_C,pressure_hPa,humidity_pct,accel_x_g,accel_y_g,accel_z_g,gyro_x_dps,gyro_y_dps,gyro_z_dps,abp3_pressure_raw_counts,abp3_pressure_zeroed_counts,abp3_temperature_C,abp3_status,diff_pressure_Pa,airspeed_raw_mps,airspeed_calibrated_mps,reference_speed_mps,density_kg_m3,kalman_pressure_Pa,kalman_speed_mps,sample_valid,imu_valid,kalman_q_Pa2_per_s,kalman_r_Pa2,validation_state");
}

void loop() {
  if ((int32_t)(millis() - nextSampleMs) < 0) return;
  nextSampleMs = millis() + SAMPLE_PERIOD_MS;

  const float tempC = bme.readTemperature();
  const float pressureHpa = bme.readPressure() / 100.0F;
  const float humidityPct = bme.readHumidity();
  int16_t ax=0, ay=0, az=0, gx=0, gy=0, gz=0;
  const bool imuValid = readMPUFrame(ax, ay, az, gx, gy, gz);

  int16_t pressureRawCounts=0;
  float abp3TempC=NAN;
  uint16_t abp3Status=0xFFFF;
  const bool abpRead = readABP3(pressureRawCounts, abp3TempC, abp3Status);
  const bool pressureValid = abpRead && !(abp3Status & ABP3_FAULT_MASK) && (abp3Status & 0x08);
  const int32_t pressureZeroedCounts = (int32_t)pressureRawCounts - abp3TareCounts;
  const float differentialPressurePa = pressureValid ? pressureZeroedCounts * ABP3_PA_PER_COUNT : NAN;
  const float airDensityKgM3 = calculateMoistAirDensity(tempC, pressureHpa, humidityPct);
  const float airspeedRawMps = pressurePaToAirspeedMps(differentialPressurePa, STANDARD_AIR_DENSITY_KG_M3);
  const float airspeedDensityCompensatedMps = pressurePaToAirspeedMps(differentialPressurePa, airDensityKgM3);
  const bool sampleValid = pressureValid && isfinite(airDensityKgM3);
  const uint32_t now = millis();
  const float kalmanPressure = updatePressureFilter(sampleValid ? differentialPressurePa : NAN, now);
  const float kalmanSpeed = pressurePaToAirspeedMps(kalmanPressure, airDensityKgM3);
  if (!sampleValid || !imuValid) Serial.println("# WARNING: invalid sensor sample; inspect validity/status columns");

  // The "calibrated" CSV field now means BME280 density-compensated Bernoulli
  // airspeed. It is not yet an empirically corrected Pitot/anemometer value.
  Serial.printf("%lu,live,%.2f,%.2f,%.2f,%.4f,%.4f,%.4f,%.3f,%.3f,%.3f,%.0f,%.0f,%.2f,0x%04X,%.4f,%.4f,%.4f,",
    now, tempC, pressureHpa, humidityPct,
    imuValid ? ax / 4096.0F : NAN, imuValid ? ay / 4096.0F : NAN, imuValid ? az / 4096.0F : NAN,
    imuValid ? gx / 65.5F : NAN, imuValid ? gy / 65.5F : NAN, imuValid ? gz / 65.5F : NAN,
    abpRead ? (float)pressureRawCounts : NAN, abpRead ? (float)pressureZeroedCounts : NAN, abp3TempC, abp3Status,
    differentialPressurePa, airspeedRawMps, airspeedDensityCompensatedMps);
  Serial.printf(",%.5f,%.4f,%.4f,%u,%u,%.2f,%.2f,unvalidated\n",
    airDensityKgM3, kalmanPressure, kalmanSpeed, sampleValid, imuValid, KALMAN_Q_RATE, KALMAN_R);
}
