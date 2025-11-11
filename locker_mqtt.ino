// locker_mqtt.ino
#include <WiFi.h>
#include <PubSubClient.h>

const char* WIFI_SSID = "YOUR_SSID";
const char* WIFI_PASS = "YOUR_PASS";

const char* MQTT_BROKER = "192.168.1.100";
const uint16_t MQTT_PORT = 1883;
const char* MQTT_USER = "mqttuser";
const char* MQTT_PASS = "mqttpass";

const char* TOPIC_LOCKER = "locker/command";

const int RELAY_PIN = 16; // pin pour le relais du casier

WiFiClient espClient;
PubSubClient mqtt(espClient);

void openLocker() {
  Serial.println("Opening locker");
  digitalWrite(RELAY_PIN, HIGH);
  delay(3000);
  digitalWrite(RELAY_PIN, LOW);
  Serial.println("Locker closed");
}

void callback(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i=0;i<length;i++) msg += (char)payload[i];
  Serial.printf("MQTT recv [%s] %s\n", topic, msg.c_str());
  if (msg == "OPEN_LOCKER") openLocker();
}

void reconnect() {
  while (!mqtt.connected()) {
    Serial.print("Attempting MQTT...");
    if (mqtt.connect("locker01", MQTT_USER, MQTT_PASS)) {
      Serial.println("connected");
      mqtt.subscribe(TOPIC_LOCKER);
    } else {
      Serial.print("fail, rc=");
      Serial.println(mqtt.state());
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  mqtt.setCallback(callback);
}

void loop() {
  if (!mqtt.connected()) reconnect();
  mqtt.loop();
}
