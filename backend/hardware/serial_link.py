import serial
import threading
import time
import json
import random
import requests
from core.config import settings

class SerialLink:
    def __init__(self):
        self.port = settings.SERIAL_PORT
        self.baud = settings.BAUD_RATE
        self.is_mock = settings.MOCK_SERIAL
        self.mode = settings.SYSTEM_MODE
        self.aws_url = settings.AWS_CLOUD_URL
        self.ser = None
        self.running = False
        
        # Latest telemetry cache to serve the API
        self.latest_telemetry = {
            "temperature": 0.0,
            "humidity": 0.0,
            "pressure": 0.0,
            "gas_resistance": 0.0,
            "status": "UNKNOWN",
            "hardware_connected": False
        }
        
        # Real AI incidents received from edge hardware
        self.live_incidents = []

    def start(self):
        if self.mode == "CLOUD":
            print("[INFO] Started in CLOUD mode. USB hardware disabled. Waiting for ground station to ingest data.")
            self.running = True
            return # Do not start the serial loop in the cloud

        print(f"[INFO] Started in LOCAL mode (Ground Station).")
        if not self.is_mock:
            try:
                self.ser = serial.Serial(self.port, self.baud, timeout=1)
                print(f"[INFO] Connected to LoRa/ESP32 on {self.port}")
            except Exception as e:
                print(f"[ERROR] Serial connection failed: {e}. Falling back to MOCK mode.")
                self.is_mock = True
        else:
            print("[INFO] Starting Serial Link in MOCK mode.")
            
        self.running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.ser:
            self.ser.close()

    def update_config(self, new_port, new_baud):
        if self.mode == "CLOUD":
            return
        
        self.port = new_port
        self.baud = int(new_baud)
        
        # Re-initialize serial
        if self.ser:
            self.ser.close()
            
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            self.is_mock = False
            print(f"[INFO] Reconnected to LoRa/ESP32 on {self.port} at {self.baud} baud")
        except Exception as e:
            print(f"[ERROR] New Serial connection failed: {e}. Falling back to MOCK mode.")
            self.is_mock = True

    def _forward_to_cloud(self, data):
        """Silently pushes data up to AWS in the background"""
        if self.aws_url == "http://YOUR_AWS_PUBLIC_IP:8000":
            return # Don't forward if AWS IP hasn't been configured yet
            
        try:
            requests.post(f"{self.aws_url}/api/telemetry/ingest", json=data, timeout=1)
        except requests.exceptions.RequestException:
            pass # Ignore connection errors if local laptop loses internet

    def _log_to_csv(self, data):
        import os
        import csv
        try:
            file_exists = os.path.isfile("blackbox_flight_log.csv")
            with open("blackbox_flight_log.csv", mode="a", newline='') as f:
                # Add timestamp to the keys
                keys = ["timestamp"] + list(data.keys())
                writer = csv.DictWriter(f, fieldnames=keys)
                if not file_exists:
                    writer.writeheader()
                
                row = data.copy()
                row["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow(row)
        except Exception:
            pass

    def _read_loop(self):
        while self.running:
            if self.is_mock:
                self._generate_mock_data()
                self._forward_to_cloud(self.latest_telemetry)
                self._log_to_csv(self.latest_telemetry)
                time.sleep(1)
            else:
                if self.ser and self.ser.in_waiting > 0:
                    try:
                        line = self.ser.readline().decode('utf-8').strip()
                        data = json.loads(line)
                        data["hardware_connected"] = True
                        
                        # Check if this is an AI Incident Payload
                        if "type" in data and "confidence" in data:
                            # It's an incident
                            incident = {
                                "id": int(time.time() * 1000),
                                "type": f"AI DETECTED: {data['type']}",
                                "time": time.strftime("%H:%M:%S"),
                                "conf": str(data["confidence"])
                            }
                            self.live_incidents.insert(0, incident)
                            self.live_incidents = self.live_incidents[:50] # Keep last 50
                            self._log_to_csv(data)
                        else:
                            # It's regular environmental telemetry
                            self.latest_telemetry.update(data)
                            self._log_to_csv(self.latest_telemetry)
                        
                        # Instantly push the new data to AWS
                        threading.Thread(target=self._forward_to_cloud, args=(data,), daemon=True).start()
                    except json.JSONDecodeError:
                        print(f"[SERIAL RAW] {line}")
                    except Exception as e:
                        print(f"[SERIAL ERR] {e}")

    def send_command(self, cmd_str):
        print(f"[SERIAL TX] {cmd_str}")
        if not self.is_mock and self.ser:
            self.ser.write(f"{cmd_str}\n".encode('utf-8'))

    def _generate_mock_data(self):
        gas = round(random.uniform(45000.0, 50000.0), 0)
        status = "NORMAL" if gas > 46000 else "WARNING"
        
        self.latest_telemetry = {
            "temperature": round(random.uniform(22.0, 26.0), 1),
            "humidity": round(random.uniform(40.0, 60.0), 1),
            "pressure": round(random.uniform(1000.0, 1020.0), 1),
            "gas_resistance": gas,
            "status": status,
            "hardware_connected": False
        }

# Global singleton instance to be shared across FastAPI routes
esp32_link = SerialLink()
