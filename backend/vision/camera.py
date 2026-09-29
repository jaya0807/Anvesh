import cv2
import threading
import numpy as np

class Camera:
    def __init__(self, src=0):
        self.cap = cv2.VideoCapture(src)
        self.grabbed, self.frame = self.cap.read()
        self.started = False
        self.read_lock = threading.Lock()
        
        # If camera fails to open, we'll serve a clean blank frame without ugly text
        if not self.grabbed:
            self.frame = np.zeros((480, 640, 3), dtype=np.uint8)
            self.grabbed = True

    def start(self):
        if self.started:
            return self
        self.started = True
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()
        return self

    def update(self):
        while self.started:
            if self.cap.isOpened():
                grabbed, frame = self.cap.read()
                if grabbed:
                    with self.read_lock:
                        self.grabbed = grabbed
                        self.frame = frame

    def read(self):
        with self.read_lock:
            frame = self.frame.copy() if self.frame is not None else None
        return self.grabbed, frame

    def stop(self):
        self.started = False
        if self.thread.is_alive():
            self.thread.join()
        if self.cap.isOpened():
            self.cap.release()
