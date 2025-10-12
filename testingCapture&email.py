#!/usr/bin/env python3

import os
import cv2
import time
import subprocess
import sys
from datetime import datetime
import smtplib
from email.message import EmailMessage
from pynput import mouse, keyboard

# -------------------------
# Configuration
# -------------------------
IDLE_THRESHOLD = 5  # seconds of inactivity before triggering

# Hardcoded credentials (silent operation)
EMAIL_ADDRESS = "varima28@gmail.com"
EMAIL_PASSWORD = "dulsnksnprhjslfa"
RECIPIENT = "varimadudeja10@gmail.com"

# -------------------------
# Activity Monitoring
# -------------------------
last_active = time.time()

def on_mouse_move(x, y):
    global last_active
    last_active = time.time()

def on_click(x, y, button, pressed):
    global last_active
    last_active = time.time()

def on_scroll(x, y, dx, dy):
    global last_active
    last_active = time.time()

def on_key_press(key):
    global last_active
    last_active = time.time()

# -------------------------
# Webcam Capture
# -------------------------
def capture_snapshot(filename_prefix="inactivity_snapshot"):
    """Capture snapshot from webcam silently"""
    cap = None
    try:
        for camera_index in [0, 1, 2]:
            try:
                if os.name == 'nt':
                    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
                else:
                    cap = cv2.VideoCapture(camera_index)
                
                if cap.isOpened():
                    # Warm up camera
                    for _ in range(5):
                        ret, frame = cap.read()
                    
                    # Capture frame
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                        filename = f"{filename_prefix}_{timestamp}.jpg"
                        
                        # Add timestamp to image
                        cv2.putText(frame, timestamp, (10, 30), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        
                        cv2.imwrite(filename, frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                        return filename, timestamp
            except:
                if cap:
                    cap.release()
                continue
            finally:
                if cap:
                    cap.release()
        
        return None, None
    except:
        return None, None
    finally:
        cv2.destroyAllWindows()

# -------------------------
# Email Functionality
# -------------------------
def send_email_with_attachment(sender, password, recipient, subject, body, attachment_path):
    """Send email silently"""
    try:
        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.set_content(body)

        with open(attachment_path, "rb") as f:
            img_data = f.read()
        
        msg.add_attachment(img_data, maintype="image", subtype="jpeg", 
                          filename=os.path.basename(attachment_path))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        return True
    except:
        return False

# -------------------------
# System Lock
# -------------------------
def lock_system():
    """Lock the system silently"""
    try:
        if os.name == 'nt':  # Windows
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], 
                         check=True, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif os.name == 'posix':  # Linux/macOS
            if sys.platform == "darwin":  # macOS
                subprocess.run(["pmset", "displaysleepnow"], 
                             check=True, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:  # Linux
                lock_commands = [
                    ["gnome-screensaver-command", "--lock"],
                    ["xdg-screensaver", "lock"],
                    ["loginctl", "lock-session"],
                    ["i3lock"]
                ]
                for cmd in lock_commands:
                    try:
                        subprocess.run(cmd, check=True, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        break
                    except:
                        continue
        return True
    except:
        return False

# -------------------------
# Main Security Monitor (Silent)
# -------------------------
def main():
    global last_active
    
    # Start activity listeners silently
    mouse_listener = mouse.Listener(
        on_move=on_mouse_move,
        on_click=on_click,
        on_scroll=on_scroll
    )
    keyboard_listener = keyboard.Listener(on_press=on_key_press)
    
    mouse_listener.start()
    keyboard_listener.start()
    
    last_trigger_time = 0
    cooldown_period = 30  # Minimum seconds between triggers
    
    try:
        while True:
            current_time = time.time()
            idle_time = current_time - last_active
            
            # Check if should trigger
            if (idle_time >= IDLE_THRESHOLD and 
                current_time - last_trigger_time >= cooldown_period):
                
                last_trigger_time = current_time
                
                try:
                    # Step 1: Capture snapshot
                    filename, timestamp = capture_snapshot()
                    
                    if filename:
                        # Step 2: Send email
                        subject = f"Security Alert for System"
                        body = f"Intruder Detected."
                        
                        send_email_with_attachment(
                            EMAIL_ADDRESS, EMAIL_PASSWORD, RECIPIENT, 
                            subject, body, filename
                        )
                    
                    # Step 3: Lock system
                    lock_system()
                    
                    # Clean up the image file
                    if filename and os.path.exists(filename):
                        try:
                            os.remove(filename)
                        except:
                            pass
                    
                except:
                    pass
                
                # Reset activity tracking
                last_active = time.time()
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        pass
    except:
        pass
    finally:
        # Clean up silently
        try:
            mouse_listener.stop()
            keyboard_listener.stop()
        except:
            pass

if __name__ == "__main__":
    # Run completely silently - no console window
    if os.name == 'nt':
        # On Windows, hide the console window
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    
    main()