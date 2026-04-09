# 🅿️ Vision-Based Smart Parking System

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Raspberry%20Pi%204-red?style=for-the-badge&logo=raspberrypi"/>
  <img src="https://img.shields.io/badge/Vision-OpenCV-blue?style=for-the-badge&logo=opencv"/>
  <img src="https://img.shields.io/badge/OCR-Tesseract-green?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Dashboard-Flask-black?style=for-the-badge&logo=flask"/>
  <img src="https://img.shields.io/badge/IoT-ESP8266-orange?style=for-the-badge"/>
</p>

<p align="center">
  A fully automated parking management system built on <strong>Raspberry Pi 4</strong> that uses computer vision to detect vehicle number plates, allocates parking slots in real time, and displays live status on a web dashboard — with zero manual intervention.
</p>

---

## 🎯 Overview

| Feature | Details |
|---|---|
| Platform | Raspberry Pi 4 |
| Camera | Pi Camera Module V2 |
| Sensor | HC-SR04 Ultrasonic via ESP8266 |
| Language | Python 3 |
| Dashboard | Flask Web App |
| Storage | Excel (.xlsx) + JSON |

---

## ⚙️ How It Works

### 1. Camera Captures Frame
The Pi Camera V2 streams video via a **GStreamer + libcamera pipeline** into OpenCV at 20–40 FPS.

### 2. Number Plate Detection
Each frame is processed through a computer vision pipeline:
- Grayscale → Gaussian Blur → Canny Edge Detection
- Contour detection + aspect ratio filtering (1.8–6.0) to isolate the plate region
- Stability check — plate must hold position for **10 consecutive frames** before OCR triggers

### 3. OCR Extracts Plate Number
- Tesseract OCR reads the plate text
- Character corrections applied: `O→0, I→1, S→5, B→8`
- Regex validates Indian plate format: `XX00X0000`

### 4. Ultrasonic Confirmation
- ESP8266 reads HC-SR04 sensor every 200ms
- Object within **20cm for 2.5 seconds** → sends `VEHICLE_DETECTED` over UART
- Pi receives via PySerial in a background thread → slot moves **Pending → Occupied**

### 5. Entry / Exit Logic
- **Entry:** Plate logged, slot allocated (Pending), awaits ultrasonic confirmation
- **Exit:** Same plate detected again → fee calculated → slot freed → waiting queue checked

### 6. Live Dashboard
Flask web app at `http://<Pi-IP>:5000` — auto-refreshes every 5 seconds with live slot status, fees, and management panels.

---

## ✨ Features

- 🔍 **Automatic Number Plate Recognition** — OpenCV + Tesseract OCR
- 🅿️ **Real-Time Slot Allocation** — auto-assigns on vehicle entry
- ✅ **Ultrasonic Confirmation** — ESP8266 confirms physical vehicle presence
- 💰 **Parking Fee Calculator** — Rs. 10/hour, minimum Rs. 10
- 📅 **Slot Reservation** — pre-book a slot before arriving
- ⚠️ **Overstay Alert** — flags vehicles parked over 2 hours
- 🚫 **Blacklist System** — block specific plates from entering
- ✅ **Whitelist System** — mark trusted/staff vehicles
- ⏳ **Waiting Queue** — auto-assigns slot when parking is full
- 📊 **Live Dashboard** — Flask web UI with color-coded slot cards

---

## 🎨 Dashboard Slot Colors

| Color | Status | Meaning |
|---|---|---|
| 🟢 Green | Free | Slot is empty |
| 🟡 Yellow | Pending | Plate detected, awaiting ultrasonic |
| 🔴 Red | Occupied | Vehicle confirmed by ultrasonic |
| 🟣 Purple | Reserved | Pre-booked via dashboard |
| 🟠 Orange badge | Overstay | Parked more than 2 hours |

---

## 🔌 Hardware Setup

```
Pi Camera V2  ──CSI──►  Raspberry Pi 4
                              │
                         USB Cable
                              │
                         ESP8266 (NodeMCU)
                              │
                         GPIO pins
                              │
                        HC-SR04 Ultrasonic Sensor
```

### Wiring — ESP8266 to HC-SR04

| HC-SR04 Pin | ESP8266 Pin |
|---|---|
| VCC | 3.3V |
| GND | GND |
| TRIG | D5 |
| ECHO | D6 |

---

## 📦 Installation

### 1. Flash Raspberry Pi OS (32-bit)
Use **Raspberry Pi Imager** — enable SSH and set WiFi credentials before flashing.

### 2. Connect via SSH and Update
```bash
sudo apt update && sudo apt upgrade -y
```

### 3. Install Dependencies
```bash
sudo apt install -y libcamera-apps gstreamer1.0-tools \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-libcamera python3-opencv tesseract-ocr python3-pip

pip3 install pytesseract flask pandas openpyxl pyserial --break-system-packages
```

### 4. Clone the Repository
```bash
git clone https://github.com/Abhijith911/smart-parking-system.git
cd smart-parking-system
```

### 5. Flash ESP8266
Upload `esp8266_ultrasonic.ino` to your NodeMCU using Arduino IDE — set board to **NodeMCU 1.0**.

---

## ▶️ Running the System

Open **two terminals** and run both from the project root:

**Terminal 1 — Camera & Detection:**
```bash
cd smart_parking_final
python3 main.py
```

**Terminal 2 — Web Dashboard:**
```bash
cd smart_parking_final
python3 ui/app.py
```

Open your browser at `http://<your-pi-ip>:5000`. To find your Pi's IP:
```bash
hostname -I
```

---

## 🗂️ Project Structure

```
smart_parking_final/
├── main.py               # Camera, OCR, entry/exit logic, serial listener
├── slot_manager.py       # Slot allocation, reservation, blacklist, queue
├── parking_slots.json    # Live slot states + waiting queue
├── parking_data.xlsx     # Vehicle entry/exit history + fees
├── vehicle_lists.json    # Blacklist and whitelist
└── ui/
    ├── app.py            # Flask web server + all routes
    ├── static/
    │   └── style.css     # Dashboard styling
    └── templates/
        └── dashboard.html  # Live dashboard UI
```

---

## 📁 Data Storage

**`parking_data.xlsx` — CURRENT_VEHICLES sheet:**
| Vehicle Number | Entry Time | Fee |
|---|---|---|
| KL47F1234 | 2026-03-27 10:30:00 | |

**`parking_data.xlsx` — HISTORY_LOG sheet:**
| Vehicle Number | Entry Time | Exit Time | Fee |
|---|---|---|---|
| KL47F1234 | 2026-03-27 10:30:00 | 2026-03-27 11:45:00 | Rs. 12.5 |

---

## 🔧 Configuration

| Setting | File | Variable | Default |
|---|---|---|---|
| Fee rate | `main.py` | `FEE_RATE_PER_HOUR` | `10` (Rs/hr) |
| Overstay limit | `ui/app.py` | `OVERSTAY_HOURS` | `2` |
| Ultrasonic distance | ESP8266 code | `distance < 20` | `20` cm |
| Confirmation time | ESP8266 code | `CONFIRMATION_TIME` | `2500` ms |
| Dashboard refresh | `dashboard.html` | `setInterval` | `5000` ms |
| Total slots | `parking_slots.json` | slots array | `10` |

---

## 🛠️ Tech Stack

| Category | Technology |
|---|---|
| Language | Python 3 |
| Computer Vision | OpenCV |
| OCR | Tesseract + pytesseract |
| Camera Pipeline | GStreamer + libcamera |
| Web Framework | Flask |
| Data Storage | Pandas + openpyxl (Excel) |
| Serial Communication | PySerial |
| Hardware | Raspberry Pi 4, Pi Camera V2, ESP8266, HC-SR04 |
| Frontend | HTML, CSS, Bootstrap 5 |
| Microcontroller Firmware | Arduino C++ |

---

## ⚠️ Known Limitations

- OCR accuracy depends on lighting conditions and camera angle
- Single camera — entry/exit distinguished by software logic only
- Ultrasonic sensor may occasionally detect non-vehicle objects (handled by 2.5s time filter)

---

## 🚀 Future Improvements

- Multi-camera support for separate entry/exit lanes
- Replace Tesseract with EasyOCR or a deep learning model for better accuracy
- Mobile app integration
- Cloud database (SQLite / Firebase) instead of Excel
- AI-based vehicle type classification
- Smart navigation to free slots

---
