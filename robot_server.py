#!/usr/bin/env python3
"""
🤖 ULTIMATE ROBOT CONTROL SERVER - GOD LEVEL v3.2
FIXED: Performance optimization for higher FPS
"""

import asyncio
import websockets
import threading
import webbrowser
import socket
import json
import time
import logging
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path
from collections import deque
import signal
import sys
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Global variables
latest_frame = None
latest_frame_lock = asyncio.Lock()
browsers = set()
esp_socket = None
sensor_history = deque(maxlen=100)
executor = ThreadPoolExecutor(max_workers=4)

connection_stats = {
    'start_time': time.time(),
    'total_frames': 0,
    'total_sensors': 0,
    'peak_browsers': 0
}

class ConnectionStats:
    """Track connection statistics"""
    def __init__(self):
        self.esp_connected = False
        self.esp_last_seen = 0
        self.browser_count = 0
        self.frames_per_second = 0
        self.frame_times = deque(maxlen=30)
        self.last_fps_update = time.time()
        self.frame_count = 0
    
    def update_fps(self):
        self.frame_count += 1
        now = time.time()
        if now - self.last_fps_update >= 1.0:
            self.frames_per_second = self.frame_count
            self.frame_count = 0
            self.last_fps_update = now

stats = ConnectionStats()

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def get_system_info():
    """Get system information for status display"""
    info = {
        'uptime': time.time() - connection_stats['start_time'],
        'total_frames': connection_stats['total_frames'],
        'total_sensors': connection_stats['total_sensors'],
        'browsers': len(browsers),
        'esp_connected': esp_socket is not None,
        'fps': stats.frames_per_second,
        'timestamp': datetime.now().isoformat()
    }
    return info

async def broadcast_to_browsers(message, binary=False):
    """Broadcast a message to all connected browsers with better error handling"""
    if not browsers:
        return
    
    # Create tasks for all browsers
    tasks = []
    for browser in list(browsers):
        try:
            if binary:
                tasks.append(asyncio.create_task(browser.send(message)))
            else:
                tasks.append(asyncio.create_task(browser.send(message)))
        except:
            browsers.discard(browser)
    
    if tasks:
        # Use gather with return_exceptions to handle individual failures
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Remove browsers that caused exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                browser = list(browsers)[i] if i < len(browsers) else None
                if browser:
                    browsers.discard(browser)

def optimize_frame(frame_data):
    """Optimize frame for faster transmission"""
    try:
        # Convert bytes to numpy array
        nparr = np.frombuffer(frame_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is not None:
            # Resize if too large
            height, width = img.shape[:2]
            if width > 640:
                scale = 640 / width
                new_width = 640
                new_height = int(height * scale)
                img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
            
            # Compress JPEG with lower quality for faster transmission
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
            _, buffer = cv2.imencode('.jpg', img, encode_param)
            return buffer.tobytes()
    except:
        pass
    return frame_data

async def esp32_handler(websocket):
    """Handle connection from ESP32-CAM with optimized frame processing"""
    global esp_socket, latest_frame
    
    esp_socket = websocket
    stats.esp_connected = True
    stats.esp_last_seen = time.time()
    connection_stats['total_frames'] = 0
    
    logger.info(f"✅ ESP32-CAM connected from {websocket.remote_address}")
    
    # Send initial status
    await broadcast_to_browsers(json.dumps({
        'type': 'system',
        'event': 'esp_connected',
        'message': 'ESP32-CAM connected'
    }))
    
    try:
        async for message in websocket:
            stats.esp_last_seen = time.time()
            
            if isinstance(message, bytes):
                # New camera frame
                connection_stats['total_frames'] += 1
                stats.update_fps()
                
                # Optimize frame in thread pool to avoid blocking
                if len(message) > 50000:  # Only optimize large frames
                    loop = asyncio.get_event_loop()
                    optimized_frame = await loop.run_in_executor(executor, optimize_frame, message)
                else:
                    optimized_frame = message
                
                # Update latest frame with lock
                async with latest_frame_lock:
                    latest_frame = optimized_frame
                
                # Broadcast to browsers immediately (don't wait)
                if browsers:
                    asyncio.create_task(broadcast_to_browsers(optimized_frame, binary=True))
                    
            else:
                # Text message (sensor data)
                connection_stats['total_sensors'] += 1
                sensor_history.append({
                    'time': time.time(),
                    'data': message
                })
                
                # Parse and forward sensor data
                try:
                    parts = message.split(',')
                    if len(parts) >= 10:
                        enhanced_data = {
                            'type': 'sensor',
                            'raw': message,
                            'timestamp': time.time(),
                            'encoders': {
                                'left': parts[1] if len(parts) > 1 else '0',
                                'right': parts[2] if len(parts) > 2 else '0'
                            },
                            'imu': {
                                'accel_x': parts[3] if len(parts) > 3 else '0',
                                'accel_y': parts[4] if len(parts) > 4 else '0',
                                'accel_z': parts[5] if len(parts) > 5 else '0',
                                'gyro_x': parts[6] if len(parts) > 6 else '0',
                                'gyro_y': parts[7] if len(parts) > 7 else '0',
                                'gyro_z': parts[8] if len(parts) > 8 else '0'
                            },
                            'tof': parts[12] if len(parts) > 12 else '0',
                            'servos': {
                                'base': parts[14] if len(parts) > 14 else '90',
                                'right_arm': parts[15] if len(parts) > 15 else '90',
                                'left_arm': parts[16] if len(parts) > 16 else '90',
                                'gripper': parts[17] if len(parts) > 17 else '135'
                            }
                        }
                        
                        # Forward to browsers (non-blocking)
                        if browsers:
                            asyncio.create_task(broadcast_to_browsers(json.dumps(enhanced_data)))
                            
                except Exception as e:
                    logger.debug(f"Error parsing sensor data: {e}")
                    # Forward raw data
                    if browsers:
                        asyncio.create_task(broadcast_to_browsers(message))
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("ESP32-CAM disconnected")
    except Exception as e:
        logger.error(f"ESP32 handler error: {e}")
    finally:
        esp_socket = None
        stats.esp_connected = False
        async with latest_frame_lock:
            latest_frame = None
        await broadcast_to_browsers(json.dumps({
            'type': 'system',
            'event': 'esp_disconnected',
            'message': 'ESP32-CAM disconnected'
        }))

async def browser_handler(websocket):
    """Handle connection from web browser with optimized frame delivery"""
    browsers.add(websocket)
    connection_stats['peak_browsers'] = max(connection_stats['peak_browsers'], len(browsers))
    
    logger.info(f"🌐 Browser connected: {websocket.remote_address} (Total: {len(browsers)})")
    
    # Send initial status
    try:
        await websocket.send(json.dumps({
            'type': 'system',
            'event': 'connected',
            'message': 'Connected to robot server',
            'stats': get_system_info()
        }))
    except:
        browsers.discard(websocket)
        return
    
    # Send latest frame if available
    async with latest_frame_lock:
        if latest_frame:
            try:
                await websocket.send(latest_frame)
            except:
                browsers.discard(websocket)
                return
    
    try:
        async for message in websocket:
            try:
                # Parse JSON command
                data = json.loads(message)
                
                # Forward to ESP32 if connected
                if esp_socket:
                    try:
                        await esp_socket.send(message)
                        logger.debug(f"🎮 Command forwarded: {data.get('cmd', 'unknown')}")
                    except:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Failed to send command to ESP32'
                        }))
                else:
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': 'ESP32 not connected'
                    }))
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from browser")
            except Exception as e:
                logger.error(f"Error handling browser message: {e}")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"🌐 Browser disconnected")
    finally:
        browsers.discard(websocket)
        logger.info(f"   Total browsers: {len(browsers)}")

async def health_check():
    """Periodic health check and stats broadcast"""
    while True:
        try:
            await asyncio.sleep(2)  # Check more frequently
            
            # Check ESP32 connection timeout
            if stats.esp_connected and time.time() - stats.esp_last_seen > 5:
                logger.warning("ESP32 connection timeout")
                stats.esp_connected = False
            
            # Broadcast stats to browsers
            if browsers:
                stats_msg = json.dumps({
                    'type': 'stats',
                    'stats': get_system_info()
                })
                await broadcast_to_browsers(stats_msg)
        except Exception as e:
            logger.error(f"Health check error: {e}")

async def main():
    """Main server function"""
    local_ip = get_local_ip()
    
    # Print banner
    print("\n" + "="*60)
    print("      🤖 ULTIMATE ROBOT CONTROL SERVER - GOD LEVEL v3.2".center(60))
    print("="*60)
    print(f"\n📡 Local IP address: {local_ip}")
    print(f"🚀 Performance mode: OPTIMIZED for high FPS")
    
    # Start WebSocket servers with optimized settings
    print(f"\n🚀 Starting WebSocket servers...")
    
    # Server for ESP32-CAM (port 8765)
    esp32_server = await websockets.serve(
        esp32_handler, 
        "0.0.0.0", 
        8765,
        ping_interval=None,  # Disable ping to reduce overhead
        ping_timeout=None,
        max_size=20_000_000,  # 20MB max frame size
        compression=None  # Disable compression for speed
    )
    print(f"   ✅ ESP32-CAM server: ws://{local_ip}:8765")
    
    # Server for Browser (port 8766)
    browser_server = await websockets.serve(
        browser_handler, 
        "0.0.0.0", 
        8766,
        ping_interval=None,
        ping_timeout=None,
        compression=None
    )
    print(f"   ✅ Browser server: ws://{local_ip}:8766")
    
    print(f"\n🌐 HTTP server: http://{local_ip}:8000")
    print("\n📋 QUICK START:")
    print("   1. Make sure ESP32-CAM is powered on")
    print("   2. Open browser to the HTTP address above")
    print("   3. Wait for connections...")
    print("\n⏳ Press Ctrl+C to stop the server\n")
    
    # Start health check task
    asyncio.create_task(health_check())
    
    try:
        await asyncio.Future()  # run forever
    except asyncio.CancelledError:
        print("\n\n👋 Shutting down gracefully...")
    finally:
        executor.shutdown(wait=False)
        esp32_server.close()
        browser_server.close()
        await esp32_server.wait_closed()
        await browser_server.wait_closed()

def start_http():
    """Start HTTP server to serve HTML files"""
    try:
        import os
        os.chdir(Path(__file__).parent)
        
        handler = SimpleHTTPRequestHandler
        handler.log_message = lambda *args: None
        
        httpd = HTTPServer(("", 8000), handler)
        logger.info(f"   ✅ HTTP server: http://localhost:8000")
        httpd.serve_forever()
    except Exception as e:
        logger.error(f"HTTP server error: {e}")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\n👋 Shutting down robot server...")
    sys.exit(0)

if __name__ == "__main__":
    import os
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start HTTP server in background
    http_thread = threading.Thread(target=start_http, daemon=True)
    http_thread.start()
    
    # Open browser automatically
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://localhost:8000")
    
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # Run main async function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()