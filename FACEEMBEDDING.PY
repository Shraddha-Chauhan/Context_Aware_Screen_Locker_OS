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
import face_recognition
import numpy as np

# ==============================
# Configuration
# ==============================
IDLE_THRESHOLD = 5           # seconds of inactivity before triggering
COOLDOWN_PERIOD = 30         # seconds between consecutive triggers
FACE_DETECTION_INTERVAL = 2  # seconds between face detection checks during idle time

EMAIL_ADDRESS = "varima28@gmail.com"        # sender email
EMAIL_PASSWORD = "dulsnksnprhjslfa"         # app password / SMTP password
RECIPIENT = "varimadudeja10@gmail.com"      # receiver email

# ==============================
# State Tracking
# ==============================
last_active = time.time()
last_trigger_time = 0
last_face_check_time = 0
system_locked = False  # tracks if system is currently locked
face_detected_during_idle = False

# ==============================
# Activity Handlers
# ==============================
def reset_activity():
    """Resets idle timer and unlock status when user becomes active."""
    global last_active, system_locked, face_detected_during_idle
    last_active = time.time()
    face_detected_during_idle = False
    if system_locked:
        print("🔓 User activity detected — system is active again.")
        system_locked = False

def on_mouse_move(x, y): reset_activity()
def on_click(x, y, button, pressed): reset_activity()
def on_scroll(x, y, dx, dy): reset_activity()
def on_key_press(key): reset_activity()

# ==============================
# Face Embedding Extraction
# ==============================
def extract_face_embedding(frame):
    """Extract face embedding from the given frame using face_recognition."""
    try:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        if not face_locations:
            print("❌ No face found for embedding extraction.")
            return None

        # Extract embeddings for first detected face
        encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        if encodings:
            print("✅ Face embedding extracted successfully.")
            return encodings[0]
        else:
            print("⚠️ Face encoding could not be generated.")
            return None
    except Exception as e:
        print(f"⚠️ Error extracting embedding: {e}")
        return None


def save_embedding(username, embedding, directory="embeddings"):
    """Save the face embedding as a .npy file."""
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
        filepath = os.path.join(directory, f"{username}.npy")
        np.save(filepath, embedding)
        print(f"💾 Embedding saved successfully at {filepath}")
    except Exception as e:
        print(f"⚠️ Error saving embedding: {e}")

# ==============================
# Face Detection & Webcam Snapshot
# ==============================
def detect_faces_and_capture_snapshot(filename_prefix="security_alert"):
    """
    Capture snapshot from webcam only if human faces are detected.
    Returns (filename, timestamp, faces_detected)
    """
    cap = None
    try:
        for camera_index in [0, 1, 2]:
            try:
                cap = cv2.VideoCapture(camera_index)
                if cap.isOpened():
                    # Warm up camera
                    for _ in range(5):
                        ret, frame = cap.read()
                    
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        # Convert to RGB for face recognition
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        
                        # Detect faces using face_recognition library
                        face_locations = face_recognition.face_locations(rgb_frame)
                        
                        if len(face_locations) > 0:
                            print(f"👤 {len(face_locations)} face(s) detected during idle time!")
                            
                            # ✅ Extract and save embedding for first detected face
                            embedding = extract_face_embedding(frame)
                            if embedding is not None:
                                save_embedding("nitya", embedding)

                            # Draw rectangles around detected faces for the snapshot
                            for (top, right, bottom, left) in face_locations:
                                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 3)
                            
                            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                            filename = f"{filename_prefix}_{timestamp}.jpg"

                            # Add timestamp and face count overlay
                            cv2.putText(frame, f"SECURITY ALERT - {timestamp}", (10, 30),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                            cv2.putText(frame, f"Faces Detected: {len(face_locations)}", (10, 60),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                            
                            cv2.imwrite(filename, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                            return filename, timestamp, len(face_locations)
                        else:
                            print("❌ No faces detected - skipping snapshot")
                            return None, None, 0
            except Exception as e:
                print(f"⚠️ Camera {camera_index} error: {e}")
                if cap:
                    cap.release()
                continue
            finally:
                if cap:
                    cap.release()
        return None, None, 0
    finally:
        cv2.destroyAllWindows()

def check_for_faces():
    """
    Quick face detection check without saving snapshot
    Returns number of faces detected
    """
    cap = None
    try:
        for camera_index in [0, 1, 2]:
            try:
                cap = cv2.VideoCapture(camera_index)
                if cap.isOpened():
                    # Quick warm up
                    for _ in range(3):
                        ret, frame = cap.read()
                    
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        # Convert to RGB for face recognition
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        
                        # Detect faces using face_recognition library
                        face_locations = face_recognition.face_locations(rgb_frame)
                        return len(face_locations)
            except:
                continue
            finally:
                if cap:
                    cap.release()
        return 0
    finally:
        cv2.destroyAllWindows()

# ==============================
# Email Notification
# ==============================
def send_email_with_attachment(sender, password, recipient, subject, body, attachment_path):
    """Send email with snapshot"""
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
        print(f"📧 Email sent successfully to {recipient}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

# ==============================
# System Lock
# ==============================
def lock_system():
    """Lock the system silently"""
    global system_locked
    try:
        print("🔒 Locking system due to inactivity...")
        if os.name == 'nt':  # Windows
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"],
                           check=True, timeout=10,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif os.name == 'posix':  # macOS/Linux
            if sys.platform == "darwin":  # macOS
                subprocess.run(["pmset", "displaysleepnow"],
                               check=True, timeout=10,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                for cmd in [
                    ["gnome-screensaver-command", "--lock"],
                    ["xdg-screensaver", "lock"],
                    ["loginctl", "lock-session"],
                    ["i3lock"]
                ]:
                    try:
                        subprocess.run(cmd, check=True, timeout=10,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        break
                    except:
                        continue
        system_locked = True
        return True
    except Exception as e:
        print(f"⚠️ Error locking system: {e}")
        return False

# ==============================
# Main Security Monitor
# ==============================
def main():
    global last_active, last_trigger_time, last_face_check_time, system_locked, face_detected_during_idle

    mouse_listener = mouse.Listener(on_move=on_mouse_move, on_click=on_click, on_scroll=on_scroll)
    keyboard_listener = keyboard.Listener(on_press=on_key_press)
    mouse_listener.start()
    keyboard_listener.start()

    print("🕵️ Face-Aware Security System Activated")
    print(f"⏰ Idle threshold: {IDLE_THRESHOLD} seconds")
    print(f"📧 Email alerts: Only when faces detected")
    print(f"🔒 System lock: Always when idle threshold reached")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            current_time = time.time()
            idle_time = current_time - last_active

            # Check if system is idle and ready for triggering
            if (not system_locked and 
                idle_time >= IDLE_THRESHOLD and 
                current_time - last_trigger_time >= COOLDOWN_PERIOD):
                
                # Periodically check for faces during idle time
                if current_time - last_face_check_time >= FACE_DETECTION_INTERVAL:
                    last_face_check_time = current_time
                    
                    faces_detected = check_for_faces()
                    
                    if faces_detected > 0:
                        # FACE DETECTED: Send email + Lock system
                        print(f"🚨 Face detected during idle time! Triggering FULL security protocol...")
                        face_detected_during_idle = True
                        last_trigger_time = current_time

                        try:
                            # 1️⃣ Capture snapshot with face detection & embedding extraction
                            filename, timestamp, face_count = detect_faces_and_capture_snapshot()

                            # 2️⃣ Send email alert only if faces were detected and snapshot taken
                            if filename and face_count > 0:
                                subject = f"Security Alert: {face_count} Intruder(s) Detected"
                                body = f"""Security System Triggered!

Detection Time: {timestamp}
Faces Detected: {face_count}
System Status: Locked and Secured

This alert was generated because face(s) were detected during user inactivity."""
                                
                                print("📧 Sending security alert email...")
                                send_email_with_attachment(EMAIL_ADDRESS, EMAIL_PASSWORD, RECIPIENT, subject, body, filename)

                            # 3️⃣ Lock system
                            lock_system()

                            # 4️⃣ Remove snapshot after sending
                            if filename and os.path.exists(filename):
                                os.remove(filename)
                                print("✅ Snapshot cleaned up")

                        except Exception as e:
                            print(f"⚠️ Error in security protocol: {e}")

                    else:
                        # NO FACE DETECTED: Lock system only (no email)
                        print("⏰ Idle threshold reached. No faces detected. Locking system quietly...")
                        last_trigger_time = current_time
                        face_detected_during_idle = False
                        
                        # Lock system without email
                        lock_system()

            # Reset face detection flag when user becomes active
            elif idle_time < IDLE_THRESHOLD and face_detected_during_idle:
                face_detected_during_idle = False

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Stopping face-aware security system...")
    finally:
        mouse_listener.stop()
        keyboard_listener.stop()
        cv2.destroyAllWindows()
        print("✅ Security system stopped cleanly.")


if __name__ == "__main__":
    # Hide console window (Windows only)
    if os.name == 'nt':
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    main()
