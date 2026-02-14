# 🔧 Hardware Architecture

## Main Components

- ESP32-CAM (Video + WiFi)
- STM32 BlackPill (Motor + Sensors)
- TB6612 Motor Driver
- NRF24L01 Remote Control
- ICM-20948 IMU
- Wheel Encoders
- VL53L0X Lidar (servo mounted)

## Power Architecture

Battery → Buck Converter → 5V Rail → Servos + ESP32  
STM32 runs on 3.3V logic.
