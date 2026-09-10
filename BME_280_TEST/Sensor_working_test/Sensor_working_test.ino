#include <Wire.h>

#define BME280_ADDR 0x76

#define SDA_PIN 21
#define SCL_PIN 22

// Calibration coefficients
uint16_t dig_T1;
int16_t  dig_T2, dig_T3;

uint16_t dig_P1;
int16_t  dig_P2, dig_P3, dig_P4, dig_P5;
int16_t  dig_P6, dig_P7, dig_P8, dig_P9;

uint8_t  dig_H1;
int16_t  dig_H2;
uint8_t  dig_H3;
int16_t  dig_H4, dig_H5;
int8_t   dig_H6;

int32_t t_fine;

// --------------------------------------------------
// Read one byte from a register
// --------------------------------------------------
uint8_t readRegister(uint8_t reg)
{
  Wire.beginTransmission(BME280_ADDR);
  Wire.write(reg);
  Wire.endTransmission();

  Wire.requestFrom(BME280_ADDR, 1);

  if (Wire.available())
    return Wire.read();

  return 0;
}

// --------------------------------------------------
// Read multiple bytes
// --------------------------------------------------
void readRegisters(uint8_t reg, uint8_t *buffer, uint8_t length)
{
  Wire.beginTransmission(BME280_ADDR);
  Wire.write(reg);
  Wire.endTransmission();

  Wire.requestFrom(BME280_ADDR, length);

  for (uint8_t i = 0; i < length && Wire.available(); i++)
  {
    buffer[i] = Wire.read();
  }
}

// --------------------------------------------------
// Write to a register
// --------------------------------------------------
void writeRegister(uint8_t reg, uint8_t value)
{
  Wire.beginTransmission(BME280_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

// --------------------------------------------------
// Read calibration data
// --------------------------------------------------
void readCalibration()
{
  uint8_t data[26];

  readRegisters(0x88, data, 24);

  dig_T1 = (data[1] << 8) | data[0];
  dig_T2 = (data[3] << 8) | data[2];
  dig_T3 = (data[5] << 8) | data[4];

  dig_P1 = (data[7] << 8) | data[6];
  dig_P2 = (data[9] << 8) | data[8];
  dig_P3 = (data[11] << 8) | data[10];
  dig_P4 = (data[13] << 8) | data[12];
  dig_P5 = (data[15] << 8) | data[14];
  dig_P6 = (data[17] << 8) | data[16];
  dig_P7 = (data[19] << 8) | data[18];
  dig_P8 = (data[21] << 8) | data[20];
  dig_P9 = (data[23] << 8) | data[22];

  dig_H1 = readRegister(0xA1);

  readRegisters(0xE1, data, 7);

  dig_H2 = (data[1] << 8) | data[0];
  dig_H3 = data[2];

  dig_H4 = (data[3] << 4) | (data[4] & 0x0F);
  dig_H5 = (data[5] << 4) | (data[4] >> 4);

  dig_H6 = data[6];

  Serial.println("Calibration data read successfully.");
}

// --------------------------------------------------
// Temperature compensation
// --------------------------------------------------
float compensateTemperature(int32_t adc_T)
{
  float var1, var2;

  var1 = (((float)adc_T / 16384.0) -
          ((float)dig_T1 / 1024.0)) *
         ((float)dig_T2);

  var2 = (((float)adc_T / 131072.0) -
          ((float)dig_T1 / 8192.0));

  var2 = var2 * var2 * ((float)dig_T3);

  t_fine = (int32_t)(var1 + var2);

  float temperature = (var1 + var2) / 5120.0;

  return temperature;
}

// --------------------------------------------------
// Pressure compensation
// --------------------------------------------------
float compensatePressure(int32_t adc_P)
{
  float var1, var2, p;

  var1 = ((float)t_fine / 2.0) - 64000.0;

  var2 = var1 * var1 * ((float)dig_P6) / 32768.0;

  var2 = var2 + var1 * ((float)dig_P5) * 2.0;

  var2 = (var2 / 4.0) + ((float)dig_P4 * 65536.0);

  var1 = (((float)dig_P3 * var1 * var1 / 524288.0) +
          ((float)dig_P2 * var1)) / 524288.0;

  var1 = (1.0 + var1 / 32768.0) * ((float)dig_P1);

  if (var1 == 0)
    return 0;

  p = 1048576.0 - (float)adc_P;

  p = (p - (var2 / 4096.0)) * 6250.0 / var1;

  var1 = ((float)dig_P9 * p * p) / 2147483648.0;

  var2 = p * ((float)dig_P8) / 32768.0;

  p = p + (var1 + var2 + ((float)dig_P7)) / 16.0;

  return p / 100.0;   // hPa
}

// --------------------------------------------------
// Humidity compensation
// --------------------------------------------------
float compensateHumidity(int32_t adc_H)
{
  float h;

  h = ((float)t_fine) - 76800.0;

  h = (adc_H -
       (((float)dig_H4 * 64.0) +
        ((float)dig_H5 / 16384.0) * h)) *
      (((float)dig_H2 / 65536.0) *
       (1.0 + ((float)dig_H6 / 67108864.0) * h *
       (1.0 + ((float)dig_H3 / 67108864.0) * h)));

  h = h * (1.0 - ((float)dig_H1 * h / 524288.0));

  if (h > 100.0)
    h = 100.0;

  if (h < 0.0)
    h = 0.0;

  return h;
}

// --------------------------------------------------
// Setup
// --------------------------------------------------
void setup()
{
  Serial.begin(115200);
  delay(1000);

  Wire.begin(SDA_PIN, SCL_PIN);

  Serial.println();
  Serial.println("================================");
  Serial.println("BME280 DIRECT REGISTER TEST");
  Serial.println("================================");

  // Check chip ID
  uint8_t chipID = readRegister(0xD0);

  Serial.print("Chip ID: 0x");
  Serial.println(chipID, HEX);

  if (chipID != 0x60)
  {
    Serial.println("ERROR: BME280 not detected!");
    while (1);
  }

  Serial.println("BME280 detected!");

  // Read calibration coefficients
  readCalibration();

  // Humidity oversampling x1
  writeRegister(0xF2, 0x01);

  // Temperature x1
  // Pressure x1
  // Normal mode
  writeRegister(0xF4, 0x27);

  // Standby 1000 ms
  // Filter off
  writeRegister(0xF5, 0xA0);

  Serial.println("Sensor configured.");
  Serial.println();
}

// --------------------------------------------------
// Main loop
// --------------------------------------------------
void loop()
{
  uint8_t data[8];

  // Read pressure, temperature and humidity registers
  readRegisters(0xF7, data, 8);

  int32_t adc_P =
      ((uint32_t)data[0] << 12) |
      ((uint32_t)data[1] << 4) |
      (data[2] >> 4);

  int32_t adc_T =
      ((uint32_t)data[3] << 12) |
      ((uint32_t)data[4] << 4) |
      (data[5] >> 4);

  int32_t adc_H =
      ((uint32_t)data[6] << 8) |
      data[7];

  // Convert raw values
  float temperature = compensateTemperature(adc_T);
  float pressure = compensatePressure(adc_P);
  float humidity = compensateHumidity(adc_H);

  // Print raw values
  Serial.println("--------------------------------");

  Serial.print("RAW TEMPERATURE : ");
  Serial.println(adc_T);

  Serial.print("RAW PRESSURE    : ");
  Serial.println(adc_P);

  Serial.print("RAW HUMIDITY    : ");
  Serial.println(adc_H);

  Serial.println();

  // Print compensated values
  Serial.print("TEMPERATURE : ");
  Serial.print(temperature, 2);
  Serial.println(" °C");

  Serial.print("PRESSURE    : ");
  Serial.print(pressure, 2);
  Serial.println(" hPa");

  Serial.print("HUMIDITY    : ");
  Serial.print(humidity, 2);
  Serial.println(" %");

  delay(2000);
}