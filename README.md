# Secure-Entry


## Overview

This project implements a **smart access control system** for an association office using an **ESP32-CAM**, **ESP32 locker module**, and a **PC server** running facial recognition.

### Key Features
-  Recognizes authorized members using **facial recognition**.  
-  Automatically opens the office door if a recognized face is detected.  
-  Sends **WhatsApp notification** to the president if an unknown person is detected.  
-  President can authorize opening via **Blynk**.  
-  Controls a separate locker via **ESP32 + relay** using MQTT.

---


---

## ⚙️ Components

### 🔩 Hardware
- **ESP32-CAM (AI-Thinker)**  
  - Captures images and sends via MQTT.  
  - Controls door relay.

- **ESP32 (Locker Module)**  
  - Controls locker relay.  
  - Subscribes to MQTT topic for locker commands.

- **Relay modules** for door and locker (5V).  
- Optional: **PIR sensor** or **button** for triggering ESP32-CAM.

---

### 💻Software

#### PC Server (Python 3.8+)
- Uses:
  - `face_recognition` → facial detection and recognition  
  - `paho-mqtt` → MQTT communication  
  - `Flask` → webhook endpoint for Blynk approval  
  - `pywhatkit` → WhatsApp notification system  
  - `opencv-python`, `numpy`, `Pillow` → image processing  

#### ESP32-CAM Code (Arduino IDE)
- Captures and encodes image.  
- Publishes via MQTT to the server.  
- Waits for MQTT command to open the door.

#### ESP32 Locker Code (Arduino IDE)
- Subscribes to MQTT topic.  
- Controls locker relay based on received commands.

---

## Installation

### 🖥️ PC Server

1. Install **Python 3.8+**
2. Install dependencies:
   ```bash
   pip install paho-mqtt face_recognition opencv-python numpy Pillow Flask pywhatkit


