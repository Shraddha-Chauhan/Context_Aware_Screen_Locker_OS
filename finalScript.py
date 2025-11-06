#!/usr/bin/env python3
import os
import cv2
import time
import subprocess
import sys
import numpy as np
from datetime import datetime
import smtplib
from email.message import EmailMessage
from pynput import mouse, keyboard
import face_recognition

# =====================================================================================
# CONFIGURATION
# =====================================================================================
IDLE_THRESHOLD = 5  # seconds of inactivity before triggering face check
TOLERANCE = 0.45    # matching threshold (same as Flask GUI)

EMAIL_ADDRESS = "varima28@gmail.com"
EMAIL_PASSWORD = "dulsnksnprhjslfa"  # app password
RECIPIENT = "varimadudeja10@gmail.com"

AUTHORIZED_EMBEDDINGS_FILE = "/Users/varimadudeja/Documents/VD28/OS Project/GUI/embeddings.npy"
INTRUDER_DIR = "/Users/varimadudeja/Documents/VD28/OS Project/intruder_snapshots"

os.makedirs(INTRUDER_DIR, exist_ok=True)

# =====================================================================================
last_active = time.time()
system_locked = False
face_detected_during_idle = False
relogin_detected = False

# =====================================================================================
def reset_activity():
    """Resets idle timer when user becomes active."""
    global last_active, system_locked, face_detected_during_idle, relogin_detected
    last_active = time.time()
    face_detected_during_idle = False
    if system_locked:
        system_locked = False
        relogin_detected = True
        print("🔓 System re-login detected — resetting security system.")
    else:
        relogin_detected = False

def on_mouse_move(x, y): reset_activity()
def on_click(x, y, button, pressed): reset_activity()
def on_scroll(x, y, dx, dy): reset_activity()
def on_key_press(key): reset_activity()

# =====================================================================================
def load_authorized_embeddings():
    """Load authorized user embeddings safely from .npy file."""
    if not os.path.exists(AUTHORIZED_EMBEDDINGS_FILE):
        print(f"⚠️ Authorized embeddings file not found: {AUTHORIZED_EMBEDDINGS_FILE}")
        return np.empty((0, 128))

    try:
        data = np.load(AUTHORIZED_EMBEDDINGS_FILE, allow_pickle=True).item()

        if isinstance(data, dict) and "users" in data:
            users = data["users"]
            embeddings = []
            for name, emb in users.items():
                emb_array = np.array(emb)
                if emb_array.ndim == 1 and emb_array.shape[0] == 128:
                    embeddings.append(emb_array)
                    print(f"✅ Loaded embedding for '{name}' ({len(emb_array)} dims)")
                else:
                    print(f"⚠️ Skipping malformed embedding for '{name}'")

            if embeddings:
                return np.vstack(embeddings)
            else:
                print("⚠️ No valid embeddings found in file.")
                return np.empty((0, 128))

        else:
            print("⚠️ Invalid file format or no 'users' key found.")
            return np.empty((0, 128))

    except Exception as e:
        print(f"⚠️ Failed to load embeddings: {e}")
        return np.empty((0, 128))

# =====================================================================================
def match_face_to_authorized(face_encoding, authorized_encodings, tolerance=TOLERANCE):
    """Compare captured face with stored authorized embeddings."""
    if authorized_encodings.size == 0:
        return False
    matches = face_recognition.compare_faces(authorized_encodings, face_encoding, tolerance)
    return True in matches

# =====================================================================================
def detect_faces_and_handle_security():
    """Main detection and locking function."""
    global system_locked
    cap = cv2.VideoCapture(0)
    authorized_encodings = load_authorized_embeddings()

    try:
        if not cap.isOpened():
            print("⚠️ Camera not accessible.")
            return

        # Warm up camera
        for _ in range(8):
            ret, _ = cap.read()
            time.sleep(0.1)

        for attempt in range(2):  # retry twice if no face
            ret, frame = cap.read()
            if not ret or frame is None:
                print("⚠️ Failed to capture frame.")
                return

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            if len(face_encodings) == 0:
                print(f"Attempt {attempt+1}: No face detected.")
                if attempt == 0:
                    time.sleep(1)
                    continue
                else:
                    print("No face detected after 2 attempts — locking system.")
                    lock_system()
                    return

            # Process detected faces
            for encoding, (top, right, bottom, left) in zip(face_encodings, face_locations):
                match = match_face_to_authorized(encoding, authorized_encodings)
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                snapshot_path = os.path.join(INTRUDER_DIR, f"intruder_{timestamp}.jpg")

                cv2.rectangle(frame, (left, top), (right, bottom),
                              (0, 255, 0) if match else (0, 0, 255), 2)
                cv2.putText(frame, "AUTHORIZED" if match else "INTRUDER",
                            (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (0, 255, 0) if match else (0, 0, 255), 2)
                cv2.imwrite(snapshot_path, frame)

                if match:
                    print("✅ Authorized user detected — system remains unlocked.")
                    if os.path.exists(snapshot_path):
                        os.remove(snapshot_path)
                    return
                else:
                    print("🚨 Unauthorized user detected — locking system & sending alert.")
                    send_intruder_alert(snapshot_path, timestamp)
                    lock_system()
                    if os.path.exists(snapshot_path):
                        os.remove(snapshot_path)
                    return

    except Exception as e:
        print(f"⚠️ Error in face detection: {e}")
    finally:
        cap.release()
        cv2.destroyAllWindows()

# =====================================================================================
def send_intruder_alert(snapshot_path, timestamp):
    """Send an email alert with intruder snapshot."""
    subject = "🚨 Security Alert: Unauthorized Access Detected"
    body = f"An intruder was detected at {timestamp}. The system was locked automatically."

    try:
        msg = EmailMessage()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = RECIPIENT
        msg["Subject"] = subject
        msg.set_content(body)

        with open(snapshot_path, "rb") as f:
            img_data = f.read()
        msg.add_attachment(img_data, maintype="image", subtype="jpeg",
                           filename=os.path.basename(snapshot_path))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print(f"📧 Email alert sent successfully to {RECIPIENT}")
    except Exception as e:
        print(f"⚠️ Failed to send alert email: {e}")

# =====================================================================================
def lock_system():
    """Lock system screen immediately."""
    global system_locked
    print("🔒 Locking system due to inactivity or unauthorized face...")

    try:
        if os.name == "nt":  # Windows
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"],
                           check=True, timeout=10)
        elif sys.platform == "darwin":  # macOS
            subprocess.run(["pmset", "displaysleepnow"], check=True, timeout=10)
        else:  # Linux
            for cmd in [
                ["gnome-screensaver-command", "--lock"],
                ["xdg-screensaver", "lock"],
                ["loginctl", "lock-session"],
                ["i3lock"]
            ]:
                try:
                    subprocess.run(cmd, check=True, timeout=10)
                    break
                except:
                    continue
        system_locked = True
    except Exception as e:
        print(f"⚠️ Error locking system: {e}")

# =====================================================================================
def main():
    global last_active, system_locked

    print("🧠 Face-Aware Security System Activated.")
    print("⏱️ Idle threshold:", IDLE_THRESHOLD, "seconds")

    mouse_listener = mouse.Listener(on_move=on_mouse_move, on_click=on_click, on_scroll=on_scroll)
    keyboard_listener = keyboard.Listener(on_press=on_key_press)
    mouse_listener.start()
    keyboard_listener.start()

    try:
        while True:
            current_time = time.time()
            idle_time = current_time - last_active

            if system_locked:
                time.sleep(1)
                continue

            if idle_time >= IDLE_THRESHOLD:
                print(f"\n⚠️ System idle for {IDLE_THRESHOLD}s — scanning for faces...")
                detect_faces_and_handle_security()
                last_active = time.time()

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Stopping face-aware security system...")
    finally:
        mouse_listener.stop()
        keyboard_listener.stop()
        cv2.destroyAllWindows()
        print("✅ Security system stopped cleanly.")

# =====================================================================================
if __name__ == "__main__":
    main()
