# ANVESH AI Pipeline Workflow

To maintain a flawless 30+ FPS video feed from the rover while running 4 complex Neural Networks simultaneously, ANVESH utilizes an **Asynchronous Thread Decoupling** architecture.

## Dual-YOLO + MiDaS Flow Diagram

```mermaid
sequenceDiagram
    participant Cam as Rover Camera
    participant Main as FastAPI Video Stream (Main Thread)
    participant AI as AI Worker (Background Thread)
    
    Cam->>Main: Read Raw Frame (30 FPS)
    
    loop Every Frame
        Main-->>AI: Copy Current Frame to RAM
        Main->>Main: Draw Cached Bounding Boxes
        Main->>Frontend: Yield Painted Frame to Browser
    end

    loop Background AI Loop
        AI->>AI: Run YOLO11-Pose (Survivors)
        AI->>AI: Run Disaster YOLO (Fire/Smoke)
        AI->>AI: Run Structural YOLO (Cracks/Debris)
        AI->>AI: Run MiDaS (Depth Mapping)
        AI-->>Main: Update Global Bounding Box Cache
    end
```

## Model Roster
* **YOLO11-Pose:** Dedicated to detecting human survivors and analyzing their posture (Standing, Crouching, Lying down).
* **Disaster YOLO (Custom):** Detects environmental threats like `FIRE` and `SMOKE`.
* **Structural YOLO (Custom):** Detects physical obstacles like `DEBRIS` and `CRACKS`.
* **MiDaS (PyTorch Hub):** Generates a real-time relative depth map (COLORMAP_INFERNO) to estimate distance to obstacles without relying solely on LiDAR.
