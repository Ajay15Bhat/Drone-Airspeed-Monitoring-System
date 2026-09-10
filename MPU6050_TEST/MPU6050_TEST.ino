#include <Wire.h>

#define MPU_ADDR 0x68

#define PWR_MGMT_1   0x6B
#define WHO_AM_I     0x75
#define ACCEL_CONFIG 0x1C
#define GYRO_CONFIG  0x1B
#define ACCEL_XOUT_H 0x3B

void writeRegister(byte reg, byte value) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

byte readRegister(byte reg) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);

  Wire.requestFrom(MPU_ADDR, 1);

  if (Wire.available()) {
    return Wire.read();
  }

  return 0xFF;
}

void setup() {

  Serial.begin(115200);
  delay(1000);

  Wire.begin(21, 22);

  Serial.println();
  Serial.println("======================================");
  Serial.println("     MPU-6500 ADAFRUIT-STYLE TEST");
  Serial.println("======================================");

  // Check chip identity
  byte chipID = readRegister(WHO_AM_I);

  Serial.print("I2C Address: 0x");
  Serial.println(MPU_ADDR, HEX);

  Serial.print("WHO_AM_I: 0x");
  Serial.println(chipID, HEX);

  if (chipID == 0x70) {
    Serial.println("MPU-6500 detected!");
  } 
  else {
    Serial.println("Unexpected chip ID!");
    while (1) {
      delay(1000);
    }
  }

  // Wake sensor
  writeRegister(PWR_MGMT_1, 0x00);
  delay(100);

  // Accelerometer ±8G
  writeRegister(ACCEL_CONFIG, 0x10);

  // Gyroscope ±500 deg/s
  writeRegister(GYRO_CONFIG, 0x08);

  Serial.println("Sensor initialized!");
  Serial.println();
}

void loop() {

  int16_t ax, ay, az;
  int16_t tempRaw;
  int16_t gx, gy, gz;

  // Start reading from accelerometer
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(ACCEL_XOUT_H);
  Wire.endTransmission(false);

  Wire.requestFrom(MPU_ADDR, 14);

  if (Wire.available() == 14) {

    ax = (Wire.read() << 8) | Wire.read();
    ay = (Wire.read() << 8) | Wire.read();
    az = (Wire.read() << 8) | Wire.read();

    tempRaw = (Wire.read() << 8) | Wire.read();

    gx = (Wire.read() << 8) | Wire.read();
    gy = (Wire.read() << 8) | Wire.read();
    gz = (Wire.read() << 8) | Wire.read();

    // ±8G = 4096 LSB/g
    float ax_g = ax / 4096.0;
    float ay_g = ay / 4096.0;
    float az_g = az / 4096.0;

    // ±500 deg/s = 65.5 LSB/(deg/s)
    float gx_dps = gx / 65.5;
    float gy_dps = gy / 65.5;
    float gz_dps = gz / 65.5;

    // MPU-6500 temperature formula
    float temperature = (tempRaw / 333.87) + 21.0;

    Serial.println("--------------------------------------");

    Serial.print("Acceleration X: ");
    Serial.print(ax_g, 3);
    Serial.print(" g, Y: ");
    Serial.print(ay_g, 3);
    Serial.print(" g, Z: ");
    Serial.print(az_g, 3);
    Serial.println(" g");

    Serial.print("Rotation X: ");
    Serial.print(gx_dps, 2);
    Serial.print(" deg/s, Y: ");
    Serial.print(gy_dps, 2);
    Serial.print(" deg/s, Z: ");
    Serial.print(gz_dps, 2);
    Serial.println(" deg/s");

    Serial.print("Temperature: ");
    Serial.print(temperature, 2);
    Serial.println(" degC");
  }

  delay(500);
}