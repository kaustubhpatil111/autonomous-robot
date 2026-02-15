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

        threading.Thread(target=self.update, daemon=True).start()

    def connect(self):
        while True:
            try:
                print("Connecting to ESP32 camera ... ")
                self.stream = requests.get(self.url, stream=True, timeout=5)
                print("camera connected")
                return
            except:
                print("waiting for camera.....")
                time.sleep(2)

    def update(self):
        self.connect()

        while self.running:
            try:
                for chunk in self.stream.iter_content(chunk_size=1024):
                    self.bytes_data += chunk

                    a = self.bytes_data.find(b'\xff\xd8')
                    b = self.bytes_data.find(b'\xff\xd9')

                    if a != -1 and b != -1:
                        jpg = self.bytes_data[a:b + 2]
                        self.bytes_data = self.bytes_data[b + 2:]

                        img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                        img = cv2.resize(img, (640, 480))
                        img = cv2.flip(img, 1)

                        self.frame = img
            except:
                print("stream lost . reconnecting ...")
                self.connect()

    def get_frame(self):
        return self.frame

    def stop(self):
        if self.stream:
            self.stream.close()