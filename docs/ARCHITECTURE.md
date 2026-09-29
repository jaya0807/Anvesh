# ANVESH M-1: Systems & Software Architecture

This document outlines the software structure and the final systems architecture for the ANVESH M-1 Subterranean Safety Rover. We utilize a **Hybrid Edge-Cloud Architecture** (sometimes called "Sync & Survive") to guarantee 100% offline survivability while maintaining global command visibility.

## 1. The Core Philosophy
Underground environments (collapsed mines, caves) are RF-denied, meaning Wi-Fi and 4G signals cannot reach the rover. A pure cloud architecture would fail instantly. 
Our solution splits the software into two synchronized environments using a single, unified codebase:
1. **The Edge (Ground Station):** A local laptop running the dashboard completely offline at the cave entrance.
2. **The Cloud (AWS):** An EC2 server running a global mirror of the dashboard.

---

## 2. The Hardware & Data Pipeline
### A. The Rover (Edge AI)
- **Hardware:** Raspberry Pi 5 (8GB) + ESP32.
- **Compute:** The Pi 5 runs ROS2, LiDAR SLAM, and YOLO11 Vision AI entirely *locally*.
- **Transmission:** The rover compresses incident alerts and SLAM coordinates into tiny text payloads and transmits them via **LoRa Radio Telemetry** (a Breadcrumb Mesh Network).

### B. The Ground Station (Local Laptop)
- The Ground Station laptop sits at the safe entrance of the cave.
- A LoRa receiver is plugged into the laptop via USB (`COM3` or `/dev/ttyUSB0`).
- The laptop reads the raw radio waves and displays the ANVESH OS dashboard to the local rescue team with **zero internet required**.

### C. The Cloud Sync (AWS EC2)
- If the Ground Station laptop is connected to Starlink or a mobile hotspot, the local FastAPI backend activates its **Forwarding Engine**.
- It silently pushes copies of all LoRa telemetry up to the AWS EC2 server.
- Global commanders in remote cities can log into the AWS URL to monitor the mission live.

---

## 3. Directory Structure (Monorepo)

To ensure the codebase remains maintainable, the project is strictly divided into a decoupled **Frontend (React)** and **Backend (FastAPI)**.

```text
sih-1.0/
├── start_station.sh          # One-click boot script for the whole app
├── README.md                 # Professional landing page
├── docs/                     # Hackathon presentation docs (Pitch, AWS, Hardware)
│
├── firmware/                 # Edge Hardware Code
│   ├── pi_vision_node.py     # Raspberry Pi edge compute script
│   ├── esp32_lora_tx.ino     # Rover LoRa radio
│   └── esp32_lora_rx.ino     # Ground Station LoRa radio
│
├── backend/                  # Python FastAPI Server
│   ├── api/                  # API Routes (telemetry, stream, control)
│   ├── hardware/             # Physical Serial/LoRa link logic
│   ├── vision/               # OpenCV & YOLO11 inference logic
│   ├── core/                 # Environment configurations
│   ├── main.py               # Application entry point
│   └── requirements.txt      # Python dependencies
│
└── frontend/                 # React, Vite, Tailwind UI
    ├── src/
    │   ├── components/       # UI Dashboard components & modals
    │   ├── App.jsx           # Root layout and global state
    │   └── index.css         # Tailwind & Glassmorphism styles
    └── package.json
```

---

## 4. How to Deploy (The Code)

Because we engineered the system to use a single codebase, you do not need to manage two different apps. You simply change the `.env` file depending on where you are running the code.

### Step 1: Start the AWS Server (Cloud Mode)
SSH into your AWS EC2 instance. In your `backend` folder, edit the `.env` file:
```ini
SYSTEM_MODE=CLOUD
```
Run the backend:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Step 2: Start the Ground Station (Local Mode)
On your laptop at the cave entrance, plug in the LoRa USB receiver. Edit the `.env` file:
```ini
SYSTEM_MODE=LOCAL
SERIAL_PORT=COM3 # or /dev/ttyUSB0
AWS_CLOUD_URL=http://YOUR_AWS_PUBLIC_IP:8000
```
Run the backend:
```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

### Step 3: Run the React UI
Run `./start_station.sh` locally, or `npm run dev`. 
The UI will dynamically render a **[MODE: LOCAL]** or **[MODE: CLOUD]** badge in the tactical footer so you always know which command center you are looking at.
