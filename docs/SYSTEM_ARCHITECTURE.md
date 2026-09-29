# ANVESH Ground Station - Core Architecture

This document outlines the core architecture of the ANVESH Disaster Response Rover Ground Station, built for the **Smart India Hackathon (SIH)**.

## High-Level System Design

The system is completely decoupled, ensuring that heavy AI processing does not bottleneck the live hardware telemetry or video feeds. 

```mermaid
graph TD
    subgraph Frontend [React.js Dashboard]
        UI[Mission Control UI]
        Cam[Live Video Stream]
        Map[LiDAR Map Canvas]
        Relay[Relay Network State]
    end

    subgraph Backend [FastAPI Server]
        API[REST APIs]
        WS[WebSocket Manager]
        AI[AI Vision Thread]
        HW[Hardware Serial Link]
    end

    subgraph Edge_Hardware [Physical Rover]
        ESP[ESP32 Microcontroller]
        LDR[RPLidar Sensor]
        Motors[Drive System]
        Drop[Relay Drop Servo]
    end

    %% Connections
    UI <-->|HTTP/WS| API
    Cam <-->|HTTP Stream| AI
    Map <-->|WS| WS
    Relay <-->|REST| HW

    API <--> WS
    WS <--> HW
    HW <--> ESP
    
    ESP --> Motors
    ESP --> Drop
    LDR --> WS
```

## Core Components
1. **Frontend (React + Tailwind):** A tactical dark-mode interface designed for high-stress disaster response environments.
2. **Backend (FastAPI):** Python-based asynchronous server that bridges the web dashboard with the physical rover hardware.
3. **Hardware Link (PySerial):** Bi-directional communication pipeline speaking a custom `CMD:ACTION:VAL` protocol to the ESP32.
