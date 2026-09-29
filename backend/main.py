from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.stream import router as stream_router
from api.telemetry import router as telemetry_router
from api.control import router as control_router
from hardware.serial_link import esp32_link

app = FastAPI(title="ANVESH Command Center API")

# Allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Start hardware connections when server boots
@app.on_event("startup")
def startup_event():
    esp32_link.start()

@app.on_event("shutdown")
def shutdown_event():
    esp32_link.stop()

# Register API routes
app.include_router(stream_router, prefix="/api", tags=["Video Stream"])
app.include_router(telemetry_router, prefix="/api", tags=["Sensors"])
app.include_router(control_router, prefix="/api", tags=["Teleop"])

import psutil

from core.config import settings



from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import random

@app.websocket("/api/ws/lidar")
async def websocket_lidar(websocket: WebSocket):
    await websocket.accept()
    
    # Attempt to connect to physical hardware first
    hardware_connected = False
    try:
        from rplidar import RPLidar
        # Default ports: /dev/ttyUSB0 (Linux/Pi), /dev/cu.usbserial-0001 (Mac), COM3 (Windows)
        lidar = RPLidar('/dev/ttyUSB0', timeout=3)
        hardware_connected = True
        print("[INFO] Physical LiDAR connected successfully.")
    except Exception as e:
        print(f"[WARNING] Physical LiDAR not found. Falling back to Simulation sweep. ({e})")

    try:
        if hardware_connected:
            # 1. LIVE HARDWARE STREAM
            for scan in lidar.iter_scans():
                points = []
                for (_, angle, distance) in scan:
                    points.append({"a": angle, "d": distance})
                
                await websocket.send_json({"type": "sweep", "data": points})
                await asyncio.sleep(0.01)
        else:
            # 2. SIMULATED DEMO STREAM (Fallback)
            angle = 0
            while True:
                points = []
                for i in range(15):
                    a = (angle + i * 2) % 360
                    dist = 3000 + random.randint(-50, 50)
                    if 80 < a < 100 or 260 < a < 280:
                        dist = 1000 + random.randint(-20, 20)
                    if 170 < a < 190:
                        dist = 500 + random.randint(-10, 10)
                    points.append({"a": a, "d": dist})
                    
                angle = (angle + 30) % 360
                await websocket.send_json({"type": "sweep", "data": points})
                await asyncio.sleep(0.05)
                
    except WebSocketDisconnect:
        print("LiDAR Client disconnected")
        if hardware_connected:
            lidar.stop()
            lidar.disconnect()

@app.get("/api/system/stats")


def get_system_stats():
    # cpu_percent(interval=None) returns immediate reading (non-blocking)
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()
    
    return {
        "mode": settings.SYSTEM_MODE,
        "cpu_percent": round(cpu),
        "ram_used_gb": round(ram.used / (1024**3), 1),
        "ram_total_gb": round(ram.total / (1024**3), 1)
    }

from pydantic import BaseModel
class SystemConfig(BaseModel):
    serial_port: str
    baud_rate: int
    ai_threshold: int

@app.post("/api/system/config")
def update_system_config(config: SystemConfig):
    # Update AI Threshold (Scale 10-95 to 0.1-0.95)
    from api.stream import detector
    detector.conf_threshold = config.ai_threshold / 100.0
    
    # Update Hardware Serial Connection
    esp32_link.update_config(config.serial_port, config.baud_rate)
    
    return {"status": "success", "message": "Configuration updated successfully"}

@app.get("/")
def read_root():
    return {"status": "ANVESH Backend is running"}
