#!/usr/bin/env python3
"""
Face-Aware Security Service for macOS
-------------------------------------
Automatically monitors idle time. When idle for a few seconds, it opens the camera,
captures a face, compares it with stored embeddings, and locks + sends an alert email
if an intruder or no face is detected.
"""

import os
import cv2
import time
import subprocess
import sys
import numpy as np
import getpass
from datetime import datetime
import smtplib
from email.message import EmailMessage
from pynput import mouse, keyboard
import face_recognition
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================
IDLE_THRESHOLD = 5          # seconds before triggering face check
CAMERA_COOLDOWN = 5         # cooldown to prevent re-triggering
TOLERANCE = 0.45
EMAIL_ADDRESS = "varima28@gmail.com"
EMAIL_PASSWORD = "dulsnksnprhjslfa"  # App Password
RECIPIENT = "varimadudeja10@gmail.com"

USER = getpass.getuser()
AUTHORIZED_EMBEDDINGS_FILE = f"/Users/{USER}/Documents/VD28/OS Project/GUI/embeddings.npy"
INTRUDER_DIR = f"/Users/{USER}/Documents/VD28/OS Project/intruder_snapshots"
os.makedirs(INTRUDER_DIR, exist_ok=True)

# =============================================================================
# GLOBALS
# =============================================================================
last_active = time.time()
system_locked = False
last_camera_use = 0

# =============================================================================
# ACTIVITY MONITOR
# =============================================================================
def reset_activity():
    global last_active
    last_active = time.time()

def on_mouse_move(x, y): reset_activity()
def on_click(x, y, button, pressed): reset_activity()
def on_scroll(x, y, dx, dy): reset_activity()
def on_key_press(key): reset_activity()

# =============================================================================
# FACE RECOGNITION
# =============================================================================
def load_authorized_embeddings():
    """Load authorized embeddings (.npy) safely."""
    if not os.path.exists(AUTHORIZED_EMBEDDINGS_FILE):
        print(f"⚠️ No authorized embeddings found: {AUTHORIZED_EMBEDDINGS_FILE}")
        return np.empty((0, 128))
    try:
        data = np.load(AUTHORIZED_EMBEDDINGS_FILE, allow_pickle=True).item()
        embeddings = []
        if isinstance(data, dict) and "users" in data:
            for name, emb in data["users"].items():
                arr = np.array(emb)
                if arr.shape == (128,):
                    embeddings.append(arr)
                    print(f"✅ Loaded embedding for {name}")
        return np.vstack(embeddings) if embeddings else np.empty((0, 128))
    except Exception as e:
        print(f"⚠️ Error loading embeddings: {e}")
        return np.empty((0, 128))

def match_face(face_encoding, authorized_encodings):
    if authorized_encodings.size == 0:
        return False
    matches = face_recognition.compare_faces(authorized_encodings, face_encoding, TOLERANCE)
    return True in matches

# =============================================================================
# SECURITY ACTIONS
# =============================================================================
def detect_faces_and_handle_security():
    """Opens camera, verifies face, or locks system."""
    global system_locked, last_camera_use

    # if system is already locked, don't trigger camera again
    if system_locked:
        print("🔒 System already locked — skipping face scan.")
        return

    # prevent frequent triggering
    if time.time() - last_camera_use < CAMERA_COOLDOWN:
        return
    last_camera_use = time.time()

    # stop if user becomes active before trigger
    if time.time() - last_active < IDLE_THRESHOLD:
        return

    cap = cv2.VideoCapture(0)
    authorized_encodings = load_authorized_embeddings()

    if not cap.isOpened():
        print("⚠️ Camera not accessible.")
        return

    no_face_count = 0

    try:
        for _ in range(5):
            cap.read()
            time.sleep(0.1)

        while no_face_count < 2:
            if time.time() - last_active < IDLE_THRESHOLD:
                print("🟢 Activity detected during scan — aborting camera check.")
                cap.release()
                return

            ret, frame = cap.read()
            if not ret or frame is None:
                no_face_count += 1
                time.sleep(1)
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            locations = face_recognition.face_locations(rgb)
            encodings = face_recognition.face_encodings(rgb, locations)

            if len(encodings) == 0:
                no_face_count += 1
                print(f"Attempt {no_face_count}: No face detected.")
                time.sleep(1)
                continue

            encoding = encodings[0]
            if match_face(encoding, authorized_encodings):
                print("✅ Authorized user detected — system stays unlocked.")
                return
            else:
                print("🚨 Intruder detected!")
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                snapshot_path = os.path.join(INTRUDER_DIR, f"intruder_{timestamp}.jpg")
                cv2.imwrite(snapshot_path, frame)
                send_intruder_alert(snapshot_path, timestamp)
                lock_system("Intruder Detected")
                return

        print("❌ No face detected — locking system.")
        lock_system("No face detected")

    except Exception as e:
        print(f"⚠️ Face detection error: {e}")
    finally:
        cap.release()
        cv2.destroyAllWindows()

def send_intruder_alert(snapshot, timestamp):
    """Send an email alert with intruder photo."""
    msg = EmailMessage()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = RECIPIENT
    msg["Subject"] = "🚨 Unauthorized Access Detected"
    msg.set_content(f"An intruder was detected at {timestamp}. System was locked automatically.")

    try:
        with open(snapshot, "rb") as f:
            msg.add_attachment(f.read(), maintype="image", subtype="jpeg",
                               filename=os.path.basename(snapshot))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print("📧 Intruder alert sent successfully.")
    except Exception as e:
        print(f"⚠️ Failed to send alert email: {e}")

def lock_system(reason=""):
    """Immediately lock the system and display a notification."""
    global system_locked
    print(f"🔒 Locking system... ({reason})")
    try:
        # Lock screen
        subprocess.run(["pmset", "displaysleepnow"], check=True, timeout=10)

        # macOS notification for logging/debug
        subprocess.run([
            "osascript", "-e",
            f'display notification "System locked: {reason}" with title "Face Security"'
        ])

        system_locked = True
    except Exception as e:
        print(f"⚠️ Error locking system: {e}")

# =============================================================================
# MAIN LOOP
# =============================================================================
def start_security_system():
    print("🧠 Face Security System Activated.")
    print(f"⏱️ Idle threshold: {IDLE_THRESHOLD}s | Tolerance: {TOLERANCE}")

    mouse_listener = mouse.Listener(on_move=on_mouse_move, on_click=on_click, on_scroll=on_scroll)
    keyboard_listener = keyboard.Listener(on_press=on_key_press)
    mouse_listener.start()
    keyboard_listener.start()

    try:
        while True:
            # If system is locked, skip everything
            if system_locked:
                time.sleep(1)
                continue

            # If idle threshold reached, trigger face scan
            if time.time() - last_active >= IDLE_THRESHOLD:
                print("\n⚠️ System idle detected — scanning face...")
                detect_faces_and_handle_security()
                reset_activity()

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Stopped manually.")

    finally:
        mouse_listener.stop()
        keyboard_listener.stop()
        cv2.destroyAllWindows()

# =============================================================================
# SERVICE INSTALLER (macOS)
# =============================================================================
SERVICE_NAME = "com.user.face-security"
SCRIPT_PATH = f"/Users/{USER}/Documents/VD28/OS Project/securityService.py"
LOG_PATH = f"/Users/{USER}/Library/Logs/face_security.log"
ERROR_LOG_PATH = f"/Users/{USER}/Library/Logs/face_security_error.log"
PLIST_PATH = f"/Users/{USER}/Library/LaunchAgents/{SERVICE_NAME}.plist"

def create_plist():
    """Generate LaunchAgent plist file."""
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{SERVICE_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/anaconda3/bin/python3</string>
        <string>{SCRIPT_PATH}</string>
        <string>--run</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>{LOG_PATH}</string>
    <key>StandardErrorPath</key><string>{ERROR_LOG_PATH}</string>
</dict>
</plist>
"""
    os.makedirs(os.path.dirname(PLIST_PATH), exist_ok=True)
    with open(PLIST_PATH, "w") as f:
        f.write(plist)
    return PLIST_PATH

def install_service():
    """Install and start LaunchAgent."""
    plist_file = create_plist()
    subprocess.run(["chmod", "+x", SCRIPT_PATH], check=False)
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{SERVICE_NAME}"], check=False)
    subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", plist_file], check=False)
    print(f"🚀 Service installed and started.\n📜 Logs: {LOG_PATH}")

def uninstall_service():
    """Completely remove the LaunchAgent."""
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{SERVICE_NAME}"], check=False)
    if os.path.exists(PLIST_PATH):
        os.remove(PLIST_PATH)
    print("🧹 Face Security Service removed completely.")

# =============================================================================
# ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    if "--run" in sys.argv:
        start_security_system()
    elif "--uninstall" in sys.argv:
        uninstall_service()
    else:
        install_service()
