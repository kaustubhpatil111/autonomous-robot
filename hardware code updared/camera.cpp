#include "esp_camera.h"
#include <WiFi.h>
#include <WebSocketsClient.h>

// ===== WiFi Credentials =====
// CHANGE THESE TO MATCH YOUR Wi-Fi 2 NETWORK
const char* ssid = "JioFi3_230593";
const char* password = "kpKP2005@";
const char* server_ip = "192.168.225.117";     // Your laptop IP from ipconfig (Wi-Fi 2)
const uint16_t server_port = 8765;

WebSocketsClient webSocket;

// ===== Camera Pins (AI-Thinker ESP32-CAM) =====
#define PWDN_GPIO_NUM    32
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM     0
#define SIOD_GPIO_NUM    26
#define SIOC_GPIO_NUM    27
#define Y9_GPIO_NUM      35
#define Y8_GPIO_NUM      34
#define Y7_GPIO_NUM      39
#define Y6_GPIO_NUM      36
#define Y5_GPIO_NUM      21
#define Y4_GPIO_NUM      19
#define Y3_GPIO_NUM      18
#define Y2_GPIO_NUM       5
#define VSYNC_GPIO_NUM   25
#define HREF_GPIO_NUM    23
#define PCLK_GPIO_NUM    22

// ===== UART to STM32 =====
#define STM32_BAUD 115200
// ESP32-CAM UART pins: RX=GPIO3 (connect to STM32 TX), TX=GPIO1 (connect to STM32 RX)

// ===== Flash LED (GPIO4) for status indication =====
#define FLASH_LED 4

void setupCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_QVGA;   // 320x240 - good for streaming
  config.jpeg_quality = 12;                // 0-63 lower = better quality
  config.fb_count     = 1;
  config.grab_mode    = CAMERA_GRAB_LATEST;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    // Blink flash LED rapidly to indicate camera error
    for(int i = 0; i < 10; i++) {
      digitalWrite(FLASH_LED, HIGH);
      delay(100);
      digitalWrite(FLASH_LED, LOW);
      delay(100);
    }
    ESP.restart();
  }
  Serial.println("Camera ready");
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.println("WebSocket disconnected");
      digitalWrite(FLASH_LED, LOW); // Turn off LED when disconnected
      break;
      
    case WStype_CONNECTED:
      Serial.println("WebSocket connected to server");
      digitalWrite(FLASH_LED, HIGH); // Turn on LED when connected
      break;
      
    case WStype_TEXT:
      // Forward JSON command to STM32
      Serial1.println((char*)payload);
      Serial.print("Forward to STM32: ");
      Serial.println((char*)payload);
      break;
      
    case WStype_BIN:
      // We don't expect binary data from server
      break;
      
    default:
      break;
  }
}

void setup() {
  // Initialize Serial for debugging
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n\nESP32-CAM Robot Controller Starting...");
  
  // Setup flash LED for status
  pinMode(FLASH_LED, OUTPUT);
  digitalWrite(FLASH_LED, LOW);
  
  // Blink once to show startup
  digitalWrite(FLASH_LED, HIGH);
  delay(500);
  digitalWrite(FLASH_LED, LOW);
  
  // Initialize UART to STM32
  Serial1.begin(STM32_BAUD, SERIAL_8N1, 3, 1); // RX=GPIO3, TX=GPIO1
  Serial.println("UART to STM32 initialized");
  
  // Connect to WiFi
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  
  int wifi_attempts = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    wifi_attempts++;
    
    // Blink LED slowly while connecting
    digitalWrite(FLASH_LED, HIGH);
    delay(100);
    digitalWrite(FLASH_LED, LOW);
    
    if (wifi_attempts > 40) { // 20 seconds timeout
      Serial.println("\nWiFi connection failed!");
      // Fast blink to indicate WiFi error
      for(int i = 0; i < 20; i++) {
        digitalWrite(FLASH_LED, HIGH);
        delay(200);
        digitalWrite(FLASH_LED, LOW);
        delay(200);
      }
      ESP.restart();
    }
  }
  
  Serial.println("\nWiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
  
  // Quick double blink to indicate WiFi success
  digitalWrite(FLASH_LED, HIGH);
  delay(200);
  digitalWrite(FLASH_LED, LOW);
  delay(200);
  digitalWrite(FLASH_LED, HIGH);
  delay(200);
  digitalWrite(FLASH_LED, LOW);
  
  // Initialize camera
  setupCamera();
  
  // Connect to WebSocket server
  Serial.print("Connecting to WebSocket server at ");
  Serial.print(server_ip);
  Serial.print(":");
  Serial.println(server_port);
  
  webSocket.begin(server_ip, server_port, "/");
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000); // Try to reconnect every 5 seconds
  
  Serial.println("Setup complete!");
}

void loop() {
  webSocket.loop();
  
  // Send camera frame at ~10 fps
  static unsigned long lastFrame = 0;
  if (millis() - lastFrame > 100) { // 100ms = 10fps
    camera_fb_t * fb = esp_camera_fb_get();
    if (fb) {
      webSocket.sendBIN(fb->buf, fb->len);
      esp_camera_fb_return(fb);
    }
    lastFrame = millis();
  }
  
  // Forward sensor data from STM32 to WebSocket
  if (Serial1.available()) {
    String line = Serial1.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      webSocket.sendTXT(line);
      Serial.print("Sensor data: ");
      Serial.println(line);
    }
  }
  
  // Small delay to prevent watchdog issues
  delay(10);
}