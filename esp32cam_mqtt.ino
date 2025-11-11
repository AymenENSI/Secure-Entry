// esp32cam_mqtt.ino
// Compile with Arduino core for ESP32, board "AI Thinker ESP32-CAM"

#include "esp_camera.h"
#include <WiFi.h>
#include <PubSubClient.h>
#include "Base64.h"

// --- CONFIG ---
const char* WIFI_SSID = "YOUR_SSID";
const char* WIFI_PASS = "YOUR_PASS";

const char* MQTT_BROKER = "192.168.1.100"; // ou hostname
const uint16_t MQTT_PORT = 1883;
const char* MQTT_USER = "mqttuser"; // si utilisé
const char* MQTT_PASS = "mqttpass";

const char* TOPIC_IMAGE = "esp32cam/image";
const char* TOPIC_COMMAND = "esp32cam/command";

const int RELAY_PIN = 12; // pin connectée au relais de la porte
const int BUTTON_PIN = 13; // optionnel : bouton pour prendre photo/trigger

WiFiClient espClient;
PubSubClient mqtt(espClient);

// --- Camera config (AI-Thinker) ---
camera_config_t config = {
  .pin_pwdn = 32,
  .pin_reset = -1,
  .pin_xclk = 0,
  .pin_sscb_sda = 26,
  .pin_sscb_scl = 27,
  .pin_d7 = 35,
  .pin_d6 = 34,
  .pin_d5 = 39,
  .pin_d4 = 36,
  .pin_d3 = 21,
  .pin_d2 = 19,
  .pin_d1 = 18,
  .pin_d0 = 5,
  .pin_vsync = 25,
  .pin_href = 23,
  .pin_pclk = 22,
  .xclk_freq_hz = 20000000,
  .ledc_timer = LEDC_TIMER_0,
  .ledc_channel = LEDC_CHANNEL_0,
  .pixel_format = PIXFORMAT_JPEG,
  .frame_size = FRAMESIZE_VGA,
  .jpeg_quality = 10,
  .fb_count = 1
};

void callback(char* topic, byte* payload, unsigned int length) {
  String t = String(topic);
  String msg;
  for (unsigned int i=0;i<length;i++) msg += (char)payload[i];

  Serial.printf("MQTT received [%s] %s\n", topic, msg.c_str());
  if (t == TOPIC_COMMAND) {
    if (msg == "OPEN_DOOR") {
      openDoor();
    }
  }
}

void reconnect() {
  while (!mqtt.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (mqtt.connect("esp32cam", MQTT_USER, MQTT_PASS)) {
      Serial.println("connected");
      mqtt.subscribe(TOPIC_COMMAND);
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqtt.state());
      Serial.println(" try again in 2s");
      delay(2000);
    }
  }
}

void setupCamera() {
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    while(true) delay(1000);
  }
}

void openDoor() {
  Serial.println("Opening door (relay ON)");
  digitalWrite(RELAY_PIN, HIGH);
  delay(3000); // open pulse, adapter selon serrure
  digitalWrite(RELAY_PIN, LOW);
  Serial.println("Door closed (relay OFF)");
}

void takeAndSendImage() {
  camera_fb_t * fb = esp_camera_fb_get();
  if(!fb) {
    Serial.println("Camera capture failed");
    return;
  }

  // encode to base64
  String imgBase64 = base64::encode(fb->buf, fb->len);
  esp_camera_fb_return(fb);

  // build JSON (simple)
  String payload = "{\"camera\":\"esp32cam01\",\"image_base64\":\"" + imgBase64 + "\"}";
  // publish in chunks if too large (some brokers have limits). Try directly:
  mqtt.publish(TOPIC_IMAGE, payload.c_str(), true);
  Serial.println("Image published to MQTT");
}

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" connected");
  setupCamera();

  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  mqtt.setCallback(callback);
}

unsigned long lastReconnectAttempt = 0;

void loop() {
  if (!mqtt.connected()) {
    unsigned long now = millis();
    if (now - lastReconnectAttempt > 2000) {
      lastReconnectAttempt = now;
      reconnect();
    }
  } else {
    mqtt.loop();
  }

  // trigger capture via button (pressed low)
  if (digitalRead(BUTTON_PIN) == LOW) {
    Serial.println("Button pressed -> capture");
    takeAndSendImage();
    delay(800); // debounce
  }

  delay(10);
}
