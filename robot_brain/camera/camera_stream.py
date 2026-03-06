import cv2
import numpy as np
import requests
import threading
import time

class CameraStream:
    def __init__(self, url):
        self.url = url
        self.frame = None
        self.bytes_data = b""
        self.running = True
        self.stream = None
        self.connected = False
        self.reconnect_delay = 1
        self.last_frame_time = 0
        self.frame_timeout = 2.0
        
        print(f"🔌 Connecting to ESP32 camera at {url}")
        threading.Thread(target=self._update, daemon=True).start()

    def _connect(self):
        while self.running:
            try:
                print(f"Attempting to connect to {self.url}...")
                self.stream = requests.get(self.url, stream=True, timeout=5)
                self.connected = True
                self.reconnect_delay = 1
                print("✅ ESP32 Camera connected")
                return
            except requests.exceptions.ConnectionError:
                print(f"⚠️ Connection refused - ESP32 may not be running camera server")
                time.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, 30)
            except Exception as e:
                print(f"⚠️ Connection failed: {e}, retrying in {self.reconnect_delay}s")
                time.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, 30)

    def _update(self):
        self._connect()
        while self.running:
            try:
                for chunk in self.stream.iter_content(chunk_size=1024):
                    self.bytes_data += chunk
                    a = self.bytes_data.find(b'\xff\xd8')
                    b = self.bytes_data.find(b'\xff\xd9')
                    if a != -1 and b != -1:
                        jpg = self.bytes_data[a:b+2]
                        self.bytes_data = self.bytes_data[b+2:]
                        img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if img is not None:
                            img = cv2.resize(img, (640, 480))
                            img = cv2.flip(img, 1)
                            self.frame = img
                            self.last_frame_time = time.time()
                            if not self.connected:
                                self.connected = True
                                print("✅ ESP32 Camera stream active")
            except Exception as e:
                print(f"📡 ESP32 stream lost: {e}, reconnecting...")
                self.connected = False
                self._connect()

    def get_frame(self):
        # If no recent frame, return placeholder with connection status
        if time.time() - self.last_frame_time > self.frame_timeout:
            placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
            if not self.connected:
                status = f"Connecting to ESP32 at {self.url}..."
            else:
                status = "Waiting for ESP32 stream..."
            cv2.putText(placeholder, status, (50, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(placeholder, f"URL: {self.url}", (50, 280),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            return placeholder
        return self.frame

    def is_connected(self):
        return self.connected and (time.time() - self.last_frame_time < self.frame_timeout)

    def stop(self):
        self.running = False
        if self.stream:
            self.stream.close()