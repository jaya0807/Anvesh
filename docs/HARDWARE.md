# 🔌 ANVESH M-1: Hardware Setup & Bill of Materials

This document outlines the physical hardware required to build the ANVESH M-1 Rover and the LoRa Breadcrumb Mesh Network.

## 1. Bill of Materials (BOM)

### The Rover (Edge Node)
| Component | Purpose |
| :--- | :--- |
| **Raspberry Pi 5 (8GB)** | The main brain. Runs ROS2, LiDAR SLAM, and YOLO11 locally. |
| **RPLiDAR A1/A2** | Generates the 2D cavern map for SLAM navigation. |
| **USB Camera** | Captures frames for YOLO11 human/hazard detection. |
| **BME680 Sensor** | Detects toxic gases, temperature, and humidity. |
| **ESP32 + LoRa (Transmitter)**| Wired to the Pi 5 via Serial. Transmits the compressed AI text data. |
| **Motor Driver (L298N)** | Drives the 4-wheel chassis. |

### The Breadcrumb Mesh Nodes (Repeaters)
| Component | Purpose |
| :--- | :--- |
| **ESP32 + LoRa Modules** | Dropped by the rover at corners to bounce the radio signal back to the entrance. Powered by small LiPo batteries. |

### The Ground Station (Command Node)
| Component | Purpose |
| :--- | :--- |
| **Laptop** | Runs the React Dashboard and FastAPI Backend locally. |
| **ESP32 + LoRa (Receiver)** | Plugged into the laptop via USB (`COM3` / `ttyUSB0`) to catch the final radio bounce. |

---

## 2. System Wiring Architecture

### Rover Data Flow
1. The **USB Camera** passes video frames to the **Pi 5**.
2. **YOLO11** (running on the Pi) scans the frame. If it sees a human, it creates a JSON string: `{"type": "PERSON", "confidence": 0.96}`.
3. The Pi 5 sends this JSON string over GPIO/Serial to the attached **ESP32 Transmitter**.
4. The ESP32 blasts it out over 900MHz LoRa radio.

### Ground Station Data Flow
1. The **ESP32 Receiver** (plugged into the laptop) catches the LoRa radio wave.
2. It pushes the JSON string over the USB Serial cable to the laptop.
3. The **FastAPI Backend** (`serial_link.py`) reads the USB port, updates the **React UI**, and seamlessly forwards a copy to **AWS DynamoDB**.
