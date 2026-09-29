# 🍓 Raspberry Pi 5 - Edge Compute Guide

This document outlines the exact software stack and scripts that must run on the **Raspberry Pi 5** physically mounted to the ANVESH M-1 rover. 

The Pi 5 acts as the "Edge Brain." Its entire job is to process heavy data (LiDAR, Video) locally, and compress it into tiny JSON strings to be transmitted over the LoRa radios.

## 1. System Requirements
- **OS:** Ubuntu 22.04 LTS or Ubuntu 24.04 (Do not use standard Raspberry Pi OS if you want ROS2 to work easily).
- **Middleware:** ROS2 (Humble or Iron).
- **Python Libraries:** `pip install ultralytics opencv-python-headless pyserial`

---

## 2. The RPLiDAR SLAM Node (Terminal 1)
You do not need to write custom code for the LiDAR. You will use standard open-source ROS2 packages to handle the mapping.

```bash
# 1. Start the RPLiDAR node to read the physical laser spinner
ros2 launch rplidar_ros rplidar_a2m12_launch.py

# 2. Start the SLAM Toolbox to generate the 2D floorplan
ros2 launch slam_toolbox online_async_launch.py
```
*(This will generate coordinate data and a 2D map that you can later extract).*

---

## 3. The YOLO11 Edge AI Script (Terminal 2)
This is the custom Python script (`vision_node.py`) that reads your USB camera, runs **YOLO11 Nano**, and outputs a JSON string when it detects a human.

**Create `vision_node.py` on your Pi 5:**
```python
import cv2
import json
import time
from ultralytics import YOLO
import serial

# 1. Initialize YOLO11 Nano
# PRO-TIP: Run model.export(format='ncnn') once to make this 5x faster on the Pi!
model = YOLO('yolo11n.pt') 

# 2. Connect to the ESP32 LoRa Transmitter (via USB or GPIO Serial)
# Change '/dev/ttyUSB0' to '/dev/ttyS0' if using GPIO pins
try:
    lora_serial = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
except:
    lora_serial = None
    print("WARNING: LoRa radio not connected.")

# 3. Open the USB Webcam
cap = cv2.VideoCapture(0)

print("ANVESH M-1 AI VISION ONLINE.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Run YOLO11 inference (Class 0 is 'Person')
    results = model.predict(frame, classes=[0], conf=0.6, verbose=False)
    
    for r in results:
        for box in r.boxes:
            confidence = round(float(box.conf[0]), 2)
            
            # Create the exact JSON payload the Ground Station expects
            payload = {
                "type": "PERSON",
                "confidence": confidence,
                "timestamp": time.time()
            }
            
            json_string = json.dumps(payload) + "\n"
            print(f"[DETECTED] {json_string.strip()}")
            
            # Transmit the heavy AI detection as lightweight text over LoRa!
            if lora_serial:
                lora_serial.write(json_string.encode('utf-8'))
                
    time.sleep(0.1) # Throttle to save CPU
```

## 4. How to Run It
When the hackathon timer starts, you just boot up the Pi 5 and run:
```bash
python3 vision_node.py
```

The camera will turn on, the YOLO11 AI will scan the room, and the second it sees a person, it will fire a JSON string into your ESP32 transmitter. 

Your laptop (at the cave entrance) will receive that JSON, the React dashboard will instantly update, and the AWS backend will sync the data!
