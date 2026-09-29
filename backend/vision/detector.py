import cv2
import numpy as np
import torch
import threading
import time

class PersonDetector:
    def __init__(self):
        self.model = None
        self.target_class = 0 
        self.conf_threshold = 0.5
        
        try:
            from ultralytics import YOLO
            # 1. QUICK WIN: Posture (Switch to YOLO11n-Pose)
            self.model = YOLO("yolo11n-pose.pt")
            print("[INFO] YOLO11-Pose loaded successfully.")
        except Exception as e:
            print(f"[WARNING] YOLO11 offline: {e}")

        # 6. CUSTOM DISASTER MODEL (Fire, Smoke)
        self.disaster_model = None
        try:
            import os
            if os.path.exists("disaster_yolo.pt"):
                self.disaster_model = YOLO("disaster_yolo.pt")
                print("[INFO] Custom Disaster YOLO loaded successfully.")
        except Exception as e:
            print(f"[WARNING] Custom Disaster YOLO failed to load: {e}")

        # 7. CUSTOM STRUCTURAL MODEL (Debris, Cracks)
        self.structural_model = None
        try:
            if os.path.exists("structural_yolo.pt"):
                self.structural_model = YOLO("structural_yolo.pt")
                print("[INFO] Custom Structural YOLO loaded successfully.")
        except Exception as e:
            print(f"[WARNING] Custom Structural YOLO failed to load: {e}")

        # 5. HEAVY COMPUTATIONAL: MiDaS Depth Estimation
        self.midas = None
        self.midas_transform = None
        self.device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        try:
            print("[INFO] Loading MiDaS Depth Model...")
            self.midas = torch.hub.load("intel-isl/MiDaS", "MiDaS_small", trust_repo=True).to(self.device)
            self.midas.eval()
            midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms", trust_repo=True)
            self.midas_transform = midas_transforms.small_transform
            print(f"[INFO] MiDaS Depth Model loaded successfully on {self.device}.")
        except Exception as e:
            print(f"[WARNING] MiDaS offline: {e}")

        # --- ASYNC MULTITHREADING STATE ---
        self.current_frame = None
        self.latest_pip = None
        self.latest_disaster_boxes = []
        self.latest_structural_boxes = []
        self.latest_person_boxes = []
        self.latest_vis_status = ("NORMAL", 0, 0)
        self.running = True
        
        # Spin up a dedicated AI background thread so the video feed never lags
        self.thread = threading.Thread(target=self._ai_worker_loop, daemon=True)
        self.thread.start()

    def _ai_worker_loop(self):
        frame_idx = 0
        while self.running:
            if self.current_frame is None:
                time.sleep(0.01)
                continue
                
            frame = self.current_frame.copy()
            frame_idx += 1
            
            try:
                lum, clr, vis_status = self.analyze_visibility(frame)
                self.latest_vis_status = (vis_status, lum, clr)
                
                if self.midas and frame_idx % 3 == 0:
                    depth_colormap = self.process_depth(frame)
                    if depth_colormap is not None:
                        h, w = frame.shape[:2]
                        pip_w, pip_h = int(w * 0.35), int(h * 0.35)
                        self.latest_pip = cv2.resize(depth_colormap, (pip_w, pip_h))
                        
                if self.disaster_model and frame_idx % 2 == 0:
                    results = self.disaster_model.predict(frame, conf=0.4, verbose=False)
                    boxes_to_save = []
                    for r in results:
                        if r.boxes is not None:
                            for box in r.boxes:
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                conf = round(float(box.conf[0]), 2)
                                cls_id = int(box.cls[0])
                                name = self.disaster_model.names[cls_id].upper()
                                if "HUMAN" in name or "PERSON" in name: continue
                                boxes_to_save.append((x1, y1, x2, y2, conf, name))
                    self.latest_disaster_boxes = boxes_to_save
                    
                if self.structural_model and frame_idx % 2 == 1:
                    results = self.structural_model.predict(frame, conf=0.4, verbose=False)
                    boxes_to_save = []
                    for r in results:
                        if r.boxes is not None:
                            for box in r.boxes:
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                conf = round(float(box.conf[0]), 2)
                                cls_id = int(box.cls[0])
                                name = self.structural_model.names[cls_id].upper()
                                if "HUMAN" in name or "PERSON" in name: continue
                                boxes_to_save.append((x1, y1, x2, y2, conf, name))
                    self.latest_structural_boxes = boxes_to_save
                    
                if self.model:
                    results = self.model.track(frame, classes=[self.target_class], conf=self.conf_threshold, persist=True, tracker="bytetrack.yaml", verbose=False)
                    boxes_to_save = []
                    for r in results:
                        if r.boxes is not None:
                            for box in r.boxes:
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                conf = round(float(box.conf[0]), 2)
                                track_id = int(box.id[0]) if box.id is not None else "?"
                                width, height = x2 - x1, y2 - y1
                                posture = "STANDING"
                                if width > height * 1.2: posture = "LYING_DOWN"
                                elif width > height * 0.8: posture = "CROUCHING"
                                boxes_to_save.append((x1, y1, x2, y2, conf, track_id, posture))
                    self.latest_person_boxes = boxes_to_save
                    
            except Exception as e:
                print(f"[AI THREAD ERROR] {e}")
                
            time.sleep(0.01)

    def analyze_visibility(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        status = "NORMAL"
        if brightness < 40: status = "LOW_LIGHT"
        elif laplacian_var < 50: status = "DUST/SMOKE_OBSCURATION"
        return brightness, laplacian_var, status

    def process_depth(self, frame):
        if self.midas is None or self.midas_transform is None: return None
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        input_batch = self.midas_transform(img).to(self.device)
        with torch.no_grad():
            prediction = self.midas(input_batch)
            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1), size=img.shape[:2], mode="bicubic", align_corners=False,
            ).squeeze()
        depth_map = prediction.cpu().numpy()
        depth_map = cv2.normalize(depth_map, None, 0, 255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        depth_colormap = cv2.applyColorMap(depth_map, cv2.COLORMAP_INFERNO)
        return depth_colormap

    def detect_and_draw(self, frame):
        if frame is None: return frame, []
            
        self.current_frame = frame.copy()  # COPY frame so AI thread does not see UI overlays (like the INFERNO Depth Map)
        incidents = []
        vis_status, lum, clr = self.latest_vis_status
        
        cv2.putText(frame, f"VISIBILITY: {vis_status}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"LUM: {int(lum)} | CLR: {int(clr)}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

        if self.latest_pip is not None:
            h, w = frame.shape[:2]
            pip_w, pip_h = self.latest_pip.shape[1], self.latest_pip.shape[0]
            margin = 15
            frame[h-pip_h-margin:h-margin, w-pip_w-margin:w-margin] = self.latest_pip
            cv2.rectangle(frame, (w-pip_w-margin, h-pip_h-margin), (w-margin, h-margin), (255, 255, 255), 2)
            cv2.putText(frame, "DEPTH MAP (MiDaS)", (w-pip_w-margin+5, h-pip_h-margin+15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,255), 1)

        for (x1, y1, x2, y2, conf, name) in self.latest_disaster_boxes:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255), 2) # Orange for Fire/Smoke
            label = f"HAZARD: {name} {conf}"
            t_size = cv2.getTextSize(label, 0, fontScale=0.5, thickness=1)[0]
            cv2.rectangle(frame, (x1, y1 - t_size[1] - 3), (x1 + t_size[0], y1 + 3), (0, 165, 255), -1)
            cv2.putText(frame, label, (x1, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
            incidents.append({"type": f"HAZARD_{name}", "confidence": conf})
            
        for (x1, y1, x2, y2, conf, name) in self.latest_structural_boxes:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2) # Red for Debris/Cracks
            label = f"DAMAGE: {name} {conf}"
            t_size = cv2.getTextSize(label, 0, fontScale=0.5, thickness=1)[0]
            cv2.rectangle(frame, (x1, y1 - t_size[1] - 3), (x1 + t_size[0], y1 + 3), (0, 0, 255), -1)
            cv2.putText(frame, label, (x1, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            incidents.append({"type": f"DAMAGE_{name}", "confidence": conf})
            
        for (x1, y1, x2, y2, conf, track_id, posture) in self.latest_person_boxes:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)
            label = f"Survivor #{track_id} | {posture} {conf}"
            t_size = cv2.getTextSize(label, 0, fontScale=0.5, thickness=1)[0]
            cv2.rectangle(frame, (x1, y1 - t_size[1] - 3), (x1 + t_size[0], y1 + 3), (255, 255, 255), -1)
            cv2.putText(frame, label, (x1, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
            incidents.append({"type": f"Survivor_{posture}", "id": track_id, "confidence": conf})

        return frame, incidents
