# 🤖 Autonomous AI Robot

An AI-powered mobile robot built using **ESP32-CAM, STM32 (BlackPill), Computer Vision and ROS2**.

This project documents the complete journey of building an autonomous robot from scratch.

---

## 🎯 Project Goals

- Remote controlled robot via WiFi
- Real-time video streaming using ESP32-CAM
- AI object detection using YOLOv8
- Vision-based navigation
- Sensor fusion (IMU + Encoders + Lidar)
- Autonomous navigation using ROS2

---

## 🧠 System Architecture

Robot has 3 brains:

| Device | Role |
|---|---|
| STM32 BlackPill | Real-time control (motors + sensors) |
| ESP32-CAM | Video streaming + WiFi bridge |
| Laptop (RTX4050) | AI + Navigation + Decision making |

---

## 🚀 Current Progress

- [x] ESP32-CAM streaming
- [x] Python video pipeline
- [x] YOLO object detection
- [x] Vision-based navigation prototype
- [ ] Encoder odometry
- [ ] IMU integration
- [ ] Lidar scanning
- [ ] ROS2 integration
- [ ] Autonomous navigation

---

## 📂 Project Structure

