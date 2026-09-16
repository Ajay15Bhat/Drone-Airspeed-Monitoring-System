#include <Wire.h>

// ==================================================
// ESP32 I2C PINS
// ==================================================

#define SDA_PIN 21
#define SCL_PIN 22

// ==================================================
// ABP3 I2C ADDRESS
// ==================================================

#define SENSOR_ADDR 0x6C

// ==================================================
// ABP3 REGISTERS
// ==================================================

#define TEMP_REGISTER_ADDR    0x2E
#define PRESS_REGISTER_ADDR   0x30
#define SYNC_REGISTER_ADDR    0x32
#define STATUS_REGISTER_ADDR  0x36
#define CMD_REGISTER_ADDR     0x22

// ==================================================
// ABP3 COMMAND
// ==================================================

#define CMD_START_SINGLESHOT 0x8B93

// ==================================================
// SENSOR PRESSURE CALIBRATION
// ==================================================
//
// Assuming:
//      Pressure range = -1 kPa to +1 kPa
//      Calibration    = 10% to 90% FSS
//
// ABP3 protocol:
//      10% FSS = -25600 counts
//      90% FSS = +25600 counts
//
// Therefore:
//
//      -1 kPa  -> -25600 counts
//       0 kPa  ->      0 counts
//      +1 kPa  -> +25600 counts
//
// ==================================================

#define PRESSURE_MIN_KPA  -1.0
#define PRESSURE_MAX_KPA   1.0

#define OUTPUT_MIN_COUNTS  -25600.0
#define OUTPUT_MAX_COUNTS   25600.0


// ==================================================
// WRITE 16-BIT VALUE TO REGISTER
// ==================================================
//
// ABP3 expects:
//      Register
//      LSB
//      MSB
//
// ==================================================

bool write16(uint8_t reg, uint16_t value)
{
  Wire.beginTransmission(SENSOR_ADDR);

  Wire.write(reg);

  // LSB first
  Wire.write((uint8_t)(value & 0xFF));

  // MSB second
  Wire.write((uint8_t)((value >> 8) & 0xFF));

  uint8_t error = Wire.endTransmission(true);

  return (error == 0);
}


// ==================================================
// READ MULTIPLE BYTES FROM REGISTER
// ==================================================

bool readBytes(uint8_t reg, uint8_t *buffer, uint8_t length)
{
  // Tell sensor which register we want
  Wire.beginTransmission(SENSOR_ADDR);
  Wire.write(reg);

  // Repeated START
  uint8_t error = Wire.endTransmission(false);

  if (error != 0)
  {
    return false;
  }

  // Request required number of bytes
  uint8_t received =
      Wire.requestFrom(SENSOR_ADDR, length, true);

  if (received != length)
  {
    return false;
  }

  // Read all bytes
  for (uint8_t i = 0; i < length; i++)
  {
    buffer[i] = Wire.read();
  }

  return true;
}


// ==================================================
// CONVERT TWO BYTES TO UNSIGNED 16-BIT VALUE
// ==================================================
//
// ABP3 sends LSB first.
//
// ==================================================

uint16_t make16(uint8_t lsb, uint8_t msb)
{
  return ((uint16_t)msb << 8) | lsb;
}


// ==================================================
// PRESSURE CONVERSION
// ==================================================

float countsToPressureKPa(int16_t counts)
{
  float pressure =
      ((counts - OUTPUT_MIN_COUNTS) *
       (PRESSURE_MAX_KPA - PRESSURE_MIN_KPA) /
       (OUTPUT_MAX_COUNTS - OUTPUT_MIN_COUNTS))
      + PRESSURE_MIN_KPA;

  return pressure;
}


// ==================================================
// STATUS DECODER
// ==================================================

void printStatus(uint16_t status)
{
  Serial.println();
  Serial.println("STATUS DETAILS");
  Serial.println("------------------------------");

  Serial.print("Raw Status : 0x");

  if (status < 0x1000)
    Serial.print("0");

  if (status < 0x0100)
    Serial.print("0");

  if (status < 0x0010)
    Serial.print("0");

  Serial.println(status, HEX);


  // Bit 15
  Serial.print("dsp_t_missed : ");
  Serial.println((status >> 15) & 1);


  // Bit 14
  Serial.print("dsp_s_missed : ");
  Serial.println((status >> 14) & 1);


  // Bit 11
  Serial.print("CRC error    : ");
  Serial.println((status >> 11) & 1);


  // Bit 10
  Serial.print("Saturation   : ");
  Serial.println((status >> 10) & 1);


  // Bit 8
  Serial.print("Bridge fail  : ");
  Serial.println((status >> 8) & 1);


  // Bit 7
  Serial.print("Bridge supply fail : ");
  Serial.println((status >> 7) & 1);


  // Bit 4
  Serial.print("dsp_t_up     : ");
  Serial.println((status >> 4) & 1);


  // Bit 3
  Serial.print("dsp_s_up     : ");
  Serial.println((status >> 3) & 1);


  // Bit 0
  Serial.print("Idle         : ");
  Serial.println((status >> 0) & 1);

  Serial.println("------------------------------");
}


// ==================================================
// SETUP
// ==================================================

void setup()
{
  Serial.begin(115200);

  Wire.begin(SDA_PIN, SCL_PIN);

  // Start conservatively at 100 kHz
  Wire.setClock(100000);

  delay(1000);

  Serial.println();
  Serial.println("==============================");
  Serial.println("ABP3 ESP32 TEST");
  Serial.println("==============================");

  Serial.println("I2C Address : 0x6C");
  Serial.println("SDA         : GPIO 21");
  Serial.println("SCL         : GPIO 22");
  Serial.println("I2C Speed   : 100 kHz");

  Serial.println();
  Serial.println("Pressure Range : -1 to +1 kPa");
  Serial.println("Calibration    : 10% to 90% FSS");
  Serial.println("Output Range   : -25600 to +25600 counts");
}


// ==================================================
// MAIN LOOP
// ==================================================

void loop()
{
  // ------------------------------------------------
  // Variables
  // ------------------------------------------------

  uint8_t data[6];

  uint16_t rawTemperature;
  uint16_t rawPressure;
  uint16_t rawStatus;

  int16_t temperatureCounts;
  int16_t pressureCounts;

  float temperature;
  float pressureKPa;
  float pressurePa;


  // =================================================
  // 1. TRIGGER SINGLE-SHOT MEASUREMENT
  // =================================================

  Serial.println();
  Serial.println("Starting measurement...");

  bool commandOK =
      write16(CMD_REGISTER_ADDR,
              CMD_START_SINGLESHOT);

  if (!commandOK)
  {
    Serial.println(
        "ERROR: Could not send START command!");

    delay(1000);
    return;
  }


  // =================================================
  // 2. WAIT FOR SENSOR CONVERSION
  // =================================================

  // Conservative delay.
  // Your previous 10 ms test was working.
  delay(10);


  // =================================================
  // 3. READ ALL 6 BYTES FROM 0x2E
  // =================================================
  //
  // According to ABP3 protocol:
  //
  // Byte 0 = Temperature LSB
  // Byte 1 = Temperature MSB
  //
  // Byte 2 = Pressure LSB
  // Byte 3 = Pressure MSB
  //
  // Byte 4 = STATUS_SYNC LSB
  // Byte 5 = STATUS_SYNC MSB
  //
  // =================================================

  if (!readBytes(TEMP_REGISTER_ADDR, data, 6))
  {
    Serial.println(
        "ERROR: Could not read 6-byte sensor data!");

    delay(1000);
    return;
  }


  // =================================================
  // 4. CONVERT RAW BYTES
  // =================================================

  rawTemperature =
      make16(data[0], data[1]);

  rawPressure =
      make16(data[2], data[3]);

  rawStatus =
      make16(data[4], data[5]);


  // =================================================
  // 5. CONVERT TO SIGNED 16-BIT
  // =================================================

  temperatureCounts =
      (int16_t)rawTemperature;

  pressureCounts =
      (int16_t)rawPressure;


  // =================================================
  // 6. TEMPERATURE CONVERSION
  // =================================================

  temperature =
      (temperatureCounts + 16485.0)
      / 387.88;


  // =================================================
  // 7. PRESSURE CONVERSION
  // =================================================

  pressureKPa =
      countsToPressureKPa(pressureCounts);

  pressurePa =
      pressureKPa * 1000.0;


  // =================================================
  // 8. PRINT RAW DATA
  // =================================================

  Serial.println();
  Serial.println("--------------------------------");

  Serial.println("RAW DATA");
  Serial.println("--------------------------------");

  Serial.print("Temperature Raw : 0x");
  Serial.println(rawTemperature, HEX);

  Serial.print("Pressure Raw    : 0x");
  Serial.println(rawPressure, HEX);

  Serial.print("Status Raw      : 0x");
  Serial.println(rawStatus, HEX);


  // =================================================
  // 9. PRINT SIGNED COUNTS
  // =================================================

  Serial.println();
  Serial.println("SIGNED COUNTS");
  Serial.println("--------------------------------");

  Serial.print("Temperature Counts : ");
  Serial.println(temperatureCounts);

  Serial.print("Pressure Counts    : ");
  Serial.println(pressureCounts);


  // =================================================
  // 10. PRINT TEMPERATURE
  // =================================================

  Serial.println();
  Serial.println("MEASUREMENTS");
  Serial.println("--------------------------------");

  Serial.print("Temperature : ");
  Serial.print(temperature, 2);
  Serial.println(" °C");


  // =================================================
  // 11. PRINT PRESSURE
  // =================================================

  Serial.print("Pressure    : ");
  Serial.print(pressureKPa, 6);
  Serial.println(" kPa");

  Serial.print("Pressure    : ");
  Serial.print(pressurePa, 2);
  Serial.println(" Pa");


  // =================================================
  // 12. STATUS INFORMATION
  // =================================================

  printStatus(rawStatus);


  // =================================================
  // 13. PRINT COMPLETE 6-BYTE FRAME
  // =================================================

  Serial.println("6-BYTE FRAME");
  Serial.println("--------------------------------");

  Serial.print("Bytes: ");

  for (int i = 0; i < 6; i++)
  {
    if (data[i] < 0x10)
      Serial.print("0");

    Serial.print(data[i], HEX);
    Serial.print(" ");
  }

  Serial.println();

  Serial.println("--------------------------------");


  // =================================================
  // WAIT BEFORE NEXT MEASUREMENT
  // =================================================

  delay(1000);
}