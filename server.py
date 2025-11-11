# server.py
import os
import io
import json
import time
import base64
import threading
from PIL import Image
import numpy as np
import face_recognition
import paho.mqtt.client as mqtt
import requests
from twilio.rest import Client as TwilioClient
from flask import Flask, request

# --- CONFIG ---
MQTT_BROKER = "192.168.1.100"
MQTT_PORT = 1883
MQTT_USER = None
MQTT_PASS = None

TOPIC_IMAGE = "esp32cam/image"
TOPIC_CAM_COMMAND = "esp32cam/command"
TOPIC_LOCKER = "locker/command"

KNOWN_FACES_DIR = "known_faces"  # each file named <name>_<num>.jpg
TOLERANCE = 0.5

# Twilio WhatsApp
TWILIO_SID = "YOUR_TWILIO_SID"
TWILIO_TOKEN = "YOUR_TWILIO_TOKEN"
TWILIO_FROM = "whatsapp:+1415XXXXXXX"  # Twilio sandbox or approved number
PRESIDENT_NUMBER = "whatsapp:+216XXXXXXXX"  # president's whatsapp

# Blynk
BLYNK_WRITE_URL = "https://blynk.cloud/external/api/update?token=YOUR_BLYNK_TOKEN&"  # use official Blynk HTTP API pattern
# you might use e.g. pin V1 to receive approval -> Blynk will call your server or you poll it.

# --- Load known faces ---
print("Loading known faces...")
known_encodings = []
known_names = []
for filename in os.listdir(KNOWN_FACES_DIR):
    if filename.lower().endswith((".jpg", ".jpeg", ".png")):
        path = os.path.join(KNOWN_FACES_DIR, filename)
        name = os.path.splitext(filename)[0]
        # optionally strip trailing _# etc
        enc_img = face_recognition.load_image_file(path)
        encs = face_recognition.face_encodings(enc_img)
        if encs:
            known_encodings.append(encs[0])
            known_names.append(name)
            print("Loaded", name)
        else:
            print("No face found in", filename)

# --- MQTT client ---
client = mqtt.Client()
if MQTT_USER:
    client.username_pw_set(MQTT_USER, MQTT_PASS)

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT:", rc)
    client.subscribe(TOPIC_IMAGE)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8')
        data = json.loads(payload)
        print("Image message received from", data.get("camera"))
        img_b64 = data.get("image_base64")
        handle_image(img_b64, data.get("camera"))
    except Exception as e:
        print("Error processing message:", e)

client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# --- Twilio client ---
twilio = TwilioClient(TWILIO_SID, TWILIO_TOKEN)

# Flask to receive Blynk webhook if needed
app = Flask(__name__)

# In-memory pending notifications: id -> metadata
pending = {}

def send_whatsapp_with_blynk(image_bytes, msg_id):
    # Upload image to Twilio? Twilio requires a publicly accessible URL for media.
    # Easiest: save image temporarily on server and serve via public URL (need ngrok or public server).
    # For demo, we will send message without media or assume media_url is accessible.
    body = f"Visage inconnu détecté. ID: {msg_id}. Cliquez sur Blynk pour autoriser l'ouverture."
    try:
        twilio.messages.create(
            body=body,
            from_=TWILIO_FROM,
            to=PRESIDENT_NUMBER
            # media_url=[media_url]  # if you have a public URL
        )
        print("WhatsApp notification sent to president")
    except Exception as e:
        print("Twilio send error:", e)

def publish_mqtt(topic, message):
    client.publish(topic, message)
    print(f"Published {message} to {topic}")

def handle_image(img_b64, camera_id):
    # decode
    img_data = base64.b64decode(img_b64)
    image = face_recognition.load_image_file(io.BytesIO(img_data))
    face_locations = face_recognition.face_locations(image)
    face_encodings = face_recognition.face_encodings(image, face_locations)
    print("Detected faces:", len(face_encodings))
    if not face_encodings:
        return

    for enc in face_encodings:
        matches = face_recognition.compare_faces(known_encodings, enc, tolerance=TOLERANCE)
        name = "Unknown"
        if True in matches:
            first_match_index = matches.index(True)
            name = known_names[first_match_index]
            print("Match:", name)
            # authorize: open door + optional open locker
            publish_mqtt(TOPIC_CAM_COMMAND, "OPEN_DOOR")
            # If you want to open locker too for this member:
            # publish_mqtt(TOPIC_LOCKER, "OPEN_LOCKER")
        else:
            # Unknown face: notify president via WhatsApp and wait for action
            uid = str(int(time.time()))
            pending[uid] = {"camera": camera_id, "time": time.time()}
            # Save image for reference
            fname = f"unknown_{uid}.jpg"
            with open(fname, "wb") as f:
                f.write(img_data)
            # Send WhatsApp with instruction and link to Blynk (or include a custom approval link)
            send_whatsapp_with_blynk(img_data, uid)
            print("Unknown face -> notified president, waiting approval.")

# Example endpoint Blynk could call when president approves (or you can poll Blynk)
@app.route("/approve", methods=["POST"])
def approve():
    data = request.json or request.form
    uid = data.get("id")
    action = data.get("action")  # "open_door" or "open_locker"
    if not uid or uid not in pending:
        return {"status":"error","msg":"unknown id"}, 400
    if action == "open_door":
        publish_mqtt(TOPIC_CAM_COMMAND, "OPEN_DOOR")
    elif action == "open_locker":
        publish_mqtt(TOPIC_LOCKER, "OPEN_LOCKER")
    else:
        return {"status":"error","msg":"unknown action"}, 400
    del pending[uid]
    return {"status":"ok"}

if __name__ == "__main__":
    # Start flask in a thread if you want to receive webhook from Blynk or external
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000, debug=False), daemon=True).start()
    print("Server ready. Listening for images on MQTT.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        client.loop_stop()
