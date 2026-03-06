import cv2
import numpy as np
import time
from dataclasses import dataclass
from typing import Optional, Tuple, List
import threading
from enum import Enum

class UIMode(Enum):
    NORMAL = "normal"
    FOCUS = "focus"
    MINIMAL = "minimal"
    DEBUG = "debug"

@dataclass
class UITheme:
    primary_color: Tuple[int, int, int] = (100, 200, 255)  # Cyan
    secondary_color: Tuple[int, int, int] = (150, 255, 150)  # Light green
    accent_color: Tuple[int, int, int] = (255, 100, 100)  # Coral
    warning_color: Tuple[int, int, int] = (0, 255, 255)  # Yellow
    background_color: Tuple[int, int, int] = (20, 20, 30)  # Dark blue-gray
    text_color: Tuple[int, int, int] = (255, 255, 255)  # White

class DeskCompanionUI:
    def __init__(self, window_name="SHERU AI Desk Companion", theme=UITheme()):
        self.window_name = window_name
        self.theme = theme
        self.mode = UIMode.NORMAL
        self.width = 1280
        self.height = 720
        self.fps = 0
        self.frame_count = 0
        self.fps_time = time.time()
        
        # UI Elements
        self.notifications = []
        self.max_notifications = 5
        self.notification_duration = 3.0  # seconds
        
        # Metrics widgets
        self.show_metrics = True
        self.show_face_grid = False
        self.show_attention_map = False
        
        # Create window
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, self.width, self.height)
        
    def add_notification(self, message: str, level: str = "info"):
        """Add a notification to display"""
        self.notifications.append({
            'message': message,
            'level': level,
            'time': time.time()
        })
        if len(self.notifications) > self.max_notifications:
            self.notifications.pop(0)
    
    def draw_glass_panel(self, frame: np.ndarray, x: int, y: int, 
                         w: int, h: int, alpha: float = 0.3) -> np.ndarray:
        """Draw a glass-morphism panel"""
        overlay = frame.copy()
        cv2.rectangle(overlay, (x, y), (x + w, y + h), 
                     (40, 40, 50), -1)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        cv2.rectangle(frame, (x, y), (x + w, y + h), 
                     (80, 80, 100), 1)
        return frame
    
    def draw_circular_meter(self, frame: np.ndarray, center: Tuple[int, int], 
                           radius: int, value: float, max_value: float,
                           label: str, color: Tuple[int, int, int]):
        """Draw a circular progress meter"""
        # Background circle
        cv2.circle(frame, center, radius, (60, 60, 70), 2)
        
        # Progress arc
        angle = int(360 * (value / max_value))
        if angle > 0:
            for i in range(0, angle, 5):
                rad = np.radians(i - 90)
                x = int(center[0] + (radius - 10) * np.cos(rad))
                y = int(center[1] + (radius - 10) * np.sin(rad))
                cv2.circle(frame, (x, y), 2, color, -1)
        
        # Label
        cv2.putText(frame, label, (center[0] - 30, center[1] + radius + 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.theme.text_color, 1)
        cv2.putText(frame, f"{value:.0f}%", (center[0] - 20, center[1] + 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        return frame
    
    def draw_attention_heatmap(self, frame: np.ndarray, 
                               attention_points: List[Tuple[int, int]]):
        """Draw attention heatmap overlay"""
        if not attention_points:
            return frame
            
        heatmap = np.zeros((self.height, self.width), dtype=np.float32)
        
        for x, y in attention_points:
            if 0 <= x < self.width and 0 <= y < self.height:
                cv2.circle(heatmap, (x, y), 50, 1, -1)
        
        # Apply Gaussian blur for smooth heatmap
        heatmap = cv2.GaussianBlur(heatmap, (99, 99), 0)
        heatmap = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX)
        heatmap = heatmap.astype(np.uint8)
        
        # Apply colormap
        heatmap_color = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
        
        # Blend with original frame
        cv2.addWeighted(heatmap_color, 0.3, frame, 0.7, 0, frame)
        
        return frame
    
    def draw_metrics_panel(self, frame: np.ndarray, metrics: dict):
        """Draw comprehensive metrics panel"""
        panel_x, panel_y = self.width - 320, 60
        panel_w, panel_h = 300, 300
        
        frame = self.draw_glass_panel(frame, panel_x, panel_y, panel_w, panel_h)
        
        # Title
        cv2.putText(frame, "SYSTEM METRICS", (panel_x + 10, panel_y + 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.theme.primary_color, 2)
        
        y_offset = panel_y + 50
        for key, value in metrics.items():
            if y_offset < panel_y + panel_h - 20:
                display_key = key.replace('_', ' ').title()
                cv2.putText(frame, f"{display_key}:", (panel_x + 10, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.theme.text_color, 1)
                cv2.putText(frame, str(value), (panel_x + 150, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.theme.secondary_color, 1)
                y_offset += 25
        
        return frame
    
    def draw_emotion_indicator(self, frame: np.ndarray, emotion: str, 
                              x: int, y: int, size: int = 40):
        """Draw a cute emotion indicator"""
        # Draw face circle
        cv2.circle(frame, (x, y), size, self.theme.primary_color, 2)
        
        # Draw eyes
        eye_offset = size // 3
        eye_y = y - size // 4
        cv2.circle(frame, (x - eye_offset, eye_y), size // 6, 
                  self.theme.text_color, -1)
        cv2.circle(frame, (x + eye_offset, eye_y), size // 6, 
                  self.theme.text_color, -1)
        
        # Draw mouth based on emotion
        mouth_y = y + size // 4
        if emotion == "happy":
            cv2.ellipse(frame, (x, mouth_y), (size // 3, size // 6), 
                       0, 0, 180, self.theme.text_color, 2)
        elif emotion == "curious":
            cv2.circle(frame, (x, mouth_y), size // 6, 
                      self.theme.text_color, 2)
        elif emotion == "alert":
            cv2.line(frame, (x - size // 4, mouth_y), 
                    (x + size // 4, mouth_y), 
                    self.theme.text_color, 2)
        
        return frame
    
    def draw_notifications(self, frame: np.ndarray):
        """Draw notification area"""
        current_time = time.time()
        y_offset = 80
        
        # Remove expired notifications
        self.notifications = [n for n in self.notifications 
                             if current_time - n['time'] < self.notification_duration]
        
        for notification in self.notifications:
            color_map = {
                'info': self.theme.primary_color,
                'warning': self.theme.warning_color,
                'alert': self.theme.accent_color
            }
            color = color_map.get(notification['level'], self.theme.text_color)
            
            cv2.putText(frame, f"⚡ {notification['message']}", (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            y_offset += 25
        
        return frame
    
    def draw_focus_grid(self, frame: np.ndarray, focus_point: Tuple[int, int]):
        """Draw focus assist grid with rule of thirds"""
        h, w = frame.shape[:2]
        
        # Draw rule of thirds grid
        for i in range(1, 3):
            x = w * i // 3
            cv2.line(frame, (x, 0), (x, h), 
                    self.theme.primary_color, 1, cv2.LINE_AA)
        
        for i in range(1, 3):
            y = h * i // 3
            cv2.line(frame, (0, y), (w, y), 
                    self.theme.primary_color, 1, cv2.LINE_AA)
        
        # Draw focus point
        if focus_point:
            x, y = focus_point
            cv2.circle(frame, (x, y), 10, self.theme.accent_color, 2)
            cv2.line(frame, (x - 20, y), (x + 20, y), 
                    self.theme.accent_color, 1)
            cv2.line(frame, (x, y - 20), (x, y + 20), 
                    self.theme.accent_color, 1)
        
        return frame
    
    def update(self, frame: np.ndarray, robot_state: dict, vision_data: dict):
        """Main UI update method"""
        if frame is None:
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Calculate FPS
        self.frame_count += 1
        if self.frame_count >= 30:
            self.fps = self.frame_count / (time.time() - self.fps_time)
            self.fps_time = time.time()
            self.frame_count = 0
        
        # Apply base overlay
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (self.width, self.height), 
                     self.theme.background_color, -1)
        frame = cv2.addWeighted(frame, 0.8, overlay, 0.2, 0)
        
        # Draw top status bar
        cv2.rectangle(frame, (0, 0), (self.width, 40), 
                     (30, 30, 40), -1)
        
        # Status indicators
        status = robot_state.get('status', 'unknown')
        status_color = self.theme.secondary_color if status == 'awake' else self.theme.accent_color
        cv2.putText(frame, f"● {status.upper()}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        
        # Mode
        mode = robot_state.get('mode', 'idle')
        cv2.putText(frame, f"MODE: {mode.upper()}", (150, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.theme.primary_color, 1)
        
        # Emotion
        emotion = robot_state.get('emotion', 'curious')
        cv2.putText(frame, f"EMOTION: {emotion.upper()}", (350, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.theme.secondary_color, 1)
        
        # Time
        current_time = time.strftime("%H:%M:%S")
        cv2.putText(frame, current_time, (self.width - 100, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.theme.text_color, 1)
        
        # Draw mode-specific elements
        if self.mode == UIMode.FOCUS and 'focus_point' in vision_data:
            frame = self.draw_focus_grid(frame, vision_data['focus_point'])
        
        if self.show_attention_map and 'attention_points' in vision_data:
            frame = self.draw_attention_heatmap(frame, vision_data['attention_points'])
        
        # Draw emotion indicator
        if 'emotion' in robot_state:
            frame = self.draw_emotion_indicator(frame, robot_state['emotion'], 
                                               self.width - 60, self.height - 60)
        
        # Draw notifications
        frame = self.draw_notifications(frame)
        
        # Draw metrics if enabled
        if self.show_metrics:
            metrics = {
                'fps': f"{self.fps:.1f}",
                'battery': f"{robot_state.get('battery', 100)}%",
                'uptime': robot_state.get('uptime', '00:00'),
                'detections': len(vision_data.get('detections', [])),
                'attention': f"{vision_data.get('attention_time', 0):.1f}s"
            }
            frame = self.draw_metrics_panel(frame, metrics)
        
        # Update display
        cv2.imshow(self.window_name, frame)
        
        # Handle key presses
        key = cv2.waitKey(1) & 0xFF
        if key == ord('m'):
            # Cycle through UI modes
            modes = list(UIMode)
            current_idx = modes.index(self.mode)
            self.mode = modes[(current_idx + 1) % len(modes)]
            self.add_notification(f"UI Mode: {self.mode.value}", "info")
        elif key == ord('g'):
            self.show_face_grid = not self.show_face_grid
        elif key == ord('a'):
            self.show_attention_map = not self.show_attention_map
        elif key == ord('h'):
            self.show_metrics = not self.show_metrics
        
        return key
    
    def cleanup(self):
        cv2.destroyAllWindows()