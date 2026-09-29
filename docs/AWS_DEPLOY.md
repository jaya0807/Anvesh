# AWS Cloud Deployment Guide - ANVESH M-1

This guide covers the deployment of the **Cloud Node** of the ANVESH M-1 Hybrid Architecture. Because you have AWS Credits, this setup utilizes a dedicated EC2 instance to serve as the global command center and data sync point.

## ✅ Features That Need to be Implemented (Deployment Checklist)
Before your presentation, ensure these specific AWS features are fully configured:

- [ ] **1. Create DynamoDB Table:** 
  - Go to AWS DynamoDB Console.
  - Create table `AnveshTelemetry`.
  - Set Partition Key: `mission_id` (String).
  - Set Sort Key: `timestamp` (String).
- [ ] **2. Assign IAM Roles:** 
  - Create an IAM Role for your EC2 instance.
  - Attach the `AmazonDynamoDBFullAccess` policy so your FastAPI `boto3` code can write to the database securely without hardcoded API keys.
- [ ] **3. Configure Environment Variables (`.env`):**
  - Create the `.env` file on the EC2 instance.
  - Must contain `SYSTEM_MODE=CLOUD`.
  - Must contain `SERIAL_PORT=DISABLED`.
- [ ] **4. Configure Background Process (PM2 / Systemd):**
  - Instead of running FastAPI manually in the terminal, configure `PM2` or a `systemd` service so the backend automatically restarts if the server reboots.
- [ ] **5. SSL / HTTPS (Optional but Recommended):**
  - Connect a domain name using Route53.
  - Use `certbot` (Let's Encrypt) to generate a free SSL certificate. Browsers prefer HTTPS when dealing with WebSockets and mixed media.
- [ ] **6. Amazon S3 Image Storage (Future Scope):**
  - Create an S3 bucket to store cropped JPEG images of hazards/humans detected by YOLO11 so the AWS dashboard can display historical evidence.

---

## 1. Instance Selection
Do **not** use the Free Tier (`t2.micro`). Your AWS credits will easily cover a more powerful server for the hackathon.
*   **Recommended (CPU-Only, ~$5 for the weekend):** Choose **`t3.large`** (2 vCPUs, 8GB RAM). This is perfect since the heavy YOLO11 AI processing is happening locally on the Raspberry Pi 5, meaning the AWS server only needs to handle the React UI and database syncing.

## 2. Security Group Configuration
When launching the instance, open these inbound rules:
- **SSH (22)** - To access your server
- **HTTP (80)** - For the frontend web dashboard
- **Custom TCP (8000)** - For the FastAPI Backend & WebSockets

## 3. Server Setup
SSH into your EC2 instance and run:

```bash
# Update system and install dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv nginx git curl

# Install Node.js (v20)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

## 4. Run the Backend
Clone your code to the server, then start the backend:

```bash
cd ~/sih-1/backend

# Create virtual environment and install requirements
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn psutil boto3

# Run the backend in a detached screen session so it stays alive
screen -dmS backend uvicorn main:app --host 0.0.0.0 --port 8000
```

## 5. Build the Frontend
```bash
cd ~/sih-1/frontend
npm install
npm run build
sudo rm -rf /var/www/html/*
sudo cp -r dist/* /var/www/html/
```

## 6. Configure Nginx Reverse Proxy
```bash
sudo nano /etc/nginx/sites-available/default
```

Paste this exact configuration:
```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    root /var/www/html;
    index index.html;
    server_name _;

    # 1. React Router
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 2. API Proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
Restart Nginx: `sudo systemctl restart nginx`
