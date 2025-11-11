import os
import io
import json
import time
import base64
import threading
from PIL import Image
import face_recognition
import paho.mqtt.client as mqtt
import pywhatkit
from flask import Flask, request

# --- CONFIGURATION ---
MQTT_BROKER = "192.168.1.50"  # PC's IP address
MQTT_PORT = 1883
TOPIC_IMAGE = "esp32cam/image"         # topic where ESP32-CAM sends images
TOPIC_CAM_COMMAND = "esp32cam/command" # topic to command ESP32-CAM relay
TOPIC_LOCKER = "locker/command"        # topic to command locker ESP32

KNOWN_FACES_DIR = "known_faces"  # folder with authorized faces
TOLERANCE = 0.5                  # face recognition tolerance

PRESIDENT_NUMBER = "+216XXXXXXXX"  # president's WhatsApp number

# --- LOAD KNOWN FACES ---
known_encodings = []
known_names = []
for filename in os.listdir(KNOWN_FACES_DIR):
    if filename.lower().endswith((".jpg",".png")):
        img = face_recognition.load_image_file(os.path.join(KNOWN_FACES_DIR, filename))
        encs = face_recognition.face_encodings(img)
        if encs:
            known_encodings.append(encs[0])
            known_names.append(os.path.splitext(filename)[0])
print("Known faces loaded:", known_names)

# --- MQTT CLIENT ---
client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    print("MQTT connected with code", rc)
    client.subscribe(TOPIC_IMAGE)  # subscribe to image topic

def on_message(client, userdata, msg):
    try:
        # Decode JSON payload received from ESP32-CAM
        data = json.loads(msg.payload.decode('utf-8'))
        img_b64 = data.get("image_base64")
        handle_image(img_b64, data.get("camera"))
    except Exception as e:
        print("Error processing MQTT message:", e)

client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()  # start MQTT loop in background

# --- FLASK SERVER TO RECEIVE BLYNK APPROVAL ---
app = Flask(__name__)
pending = {}  # dict to store pending unknown faces {id: metadata}

@app.route("/approve", methods=["POST"])
def approve():
    """
    Endpoint for Blynk approval button.
    Expects form data: 'id' and 'action' ('open_door' or 'open_locker')
    """
    uid = request.form.get("id")
    action = request.form.get("action")
    if uid not in pending:
        return {"status":"error"}, 400
    if action=="open_door":
        client.publish(TOPIC_CAM_COMMAND, "OPEN_DOOR")
    elif action=="open_locker":
        client.publish(TOPIC_LOCKER, "OPEN_LOCKER")
    # remove from pending after approval
    del pending[uid]
    return {"status":"ok"}

# --- FUNCTIONS ---

def handle_image(img_b64, camera_id):
    """
    Handle image received from ESP32-CAM.
    - Decode base64
    - Detect faces
    - Compare with known faces
    - Open door if recognized
    - Notify president via WhatsApp if unknown
    """
    img_data = base64.b64decode(img_b64)
    image = face_recognition.load_image_file(io.BytesIO(img_data))
    encodings = face_recognition.face_encodings(image)
    if not encodings:
        print("No face detected in image")
        return

    for enc in encodings:
        matches = face_recognition.compare_faces(known_encodings, enc, tolerance=TOLERANCE)
        if True in matches:
            # Face recognized: open door
            idx = matches.index(True)
            name = known_names[idx]
            print("Recognized face:", name)
            client.publish(TOPIC_CAM_COMMAND, "OPEN_DOOR")
        else:
            # Face unknown: notify president via WhatsApp and wait for approval
            uid = str(int(time.time()))
            pending[uid] = {"camera": camera_id}
            fname = f"unknown_{uid}.jpg"
            with open(fname,"wb") as f:
                f.write(img_data)
            print("Unknown face detected, sending WhatsApp notification...")
            # Send WhatsApp message using pywhatkit
            pywhatkit.sendwhatmsg_instantly(PRESIDENT_NUMBER, f"Unknown face detected. ID: {uid}")

# --- MAIN LOOP ---
if __name__=="__main__":
    # Run Flask server in a separate thread for Blynk webhooks
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000), daemon=True).start()
    print("Server running on PC, listening for MQTT images...")

    try:
        while True:
            time.sleep(1)  # keep main thread alive
    except KeyboardInterrupt:
        client.loop_stop()
