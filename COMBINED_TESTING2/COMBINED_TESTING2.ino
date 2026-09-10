#include <Wire.h>
#include <Adafruit_BME280.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// ---------------- I2C ----------------
#define SDA_PIN 21
#define SCL_PIN 22

// ---------------- BME280 ----------------
Adafruit_BME280 bme;

// ---------------- MPU6050 / MPU6500 ----------------
Adafruit_MPU6050 mpu;

void setup() {

  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("========================================");
  Serial.println("   ESP32 - BME280 + MPU Sensor Test");
  Serial.println("========================================");

  // Start I2C
  Wire.begin(SDA_PIN, SCL_PIN);

  // ---------------- BME280 ----------------
  Serial.println();
  Serial.println("Initializing BME280...");

  if (!bme.begin(0x76, &Wire)) {
    Serial.println("ERROR: BME280 not found!");
    while (1) {
      delay(10);
    }
  }

  Serial.println("BME280 FOUND!");

  // ---------------- MPU ----------------
  Serial.println();
  Serial.println("Initializing MPU sensor...");

  if (!mpu.begin(0x68, &Wire)) {
    Serial.println("ERROR: MPU sensor not found!");
    while (1) {
      delay(10);
    }
  }

  Serial.println("MPU sensor FOUND!");

  // MPU configuration
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

  Serial.println();
  Serial.println("Both sensors initialized successfully!");
  Serial.println("----------------------------------------");
}


void loop() {

  // ==================================================
  // BME280
  // ==================================================

  float bmeTemperature = bme.readTemperature();
  float pressure = bme.readPressure() / 100.0F;  // Pa → hPa
  float humidity = bme.readHumidity();


  // ==================================================
  // MPU
  // ==================================================

  sensors_event_t accel;
  sensors_event_t gyro;
  sensors_event_t mpuTemperature;

  mpu.getEvent(&accel, &gyro, &mpuTemperature);


  // ==================================================
  // PRINT EVERYTHING
  // ==================================================

  Serial.println();

  Serial.println("------------- BME280 -------------");

  Serial.print("Temperature : ");
  Serial.print(bmeTemperature);
  Serial.println(" °C");

  Serial.print("Pressure    : ");
  Serial.print(pressure);
  Serial.println(" hPa");

  Serial.print("Humidity    : ");
  Serial.print(humidity);
  Serial.println(" %");


  Serial.println();
  Serial.println("------------- MPU ----------------");

  Serial.print("Acceleration X: ");
  Serial.print(accel.acceleration.x);
  Serial.print("  Y: ");
  Serial.print(accel.acceleration.y);
  Serial.print("  Z: ");
  Serial.print(accel.acceleration.z);
  Serial.println(" m/s²");

  Serial.print("Rotation X: ");
  Serial.print(gyro.gyro.x);
  Serial.print("  Y: ");
  Serial.print(gyro.gyro.y);
  Serial.print("  Z: ");
  Serial.print(gyro.gyro.z);
  Serial.println(" rad/s");

  Serial.print("Temperature : ");
  Serial.print(mpuTemperature.temperature);
  Serial.println(" °C");

  Serial.println("----------------------------------------");

  delay(500);
}
