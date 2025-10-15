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

# ==============================
# Configuration
# ==============================
IDLE_THRESHOLD = 5           # seconds of inactivity before triggering
COOLDOWN_PERIOD = 30         # seconds between consecutive triggers

EMAIL_ADDRESS = "varima28@gmail.com"        # sender email
EMAIL_PASSWORD = "dulsnksnprhjslfa"         # app password / SMTP password
RECIPIENT = "varimadudeja10@gmail.com"      # receiver email

# ==============================
# State Tracking
# ==============================
last_active = time.time()
last_trigger_time = 0
system_locked = False  # tracks if system is currently locked

# ==============================
# Activity Handlers
# ==============================
def reset_activity():
    """Resets idle timer and unlock status when user becomes active."""
    global last_active, system_locked
    last_active = time.time()
    if system_locked:
        print("🔓 User activity detected — system is active again.")
        system_locked = False

def on_mouse_move(x, y): reset_activity()
def on_click(x, y, button, pressed): reset_activity()
def on_scroll(x, y, dx, dy): reset_activity()
def on_key_press(key): reset_activity()

# ==============================
# Webcam Snapshot
# ==============================
def capture_snapshot(filename_prefix="inactivity_snapshot"):
    """Capture snapshot from webcam silently"""
    cap = None
    try:
        for camera_index in [0, 1, 2]:
            try:
                cap = cv2.VideoCapture(camera_index)
                if cap.isOpened():
                    for _ in range(5):  # warm up
                        ret, frame = cap.read()

                    ret, frame = cap.read()
                    if ret and frame is not None:
                        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                        filename = f"{filename_prefix}_{timestamp}.jpg"

                        # add timestamp overlay
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
    global last_active, last_trigger_time, system_locked

    mouse_listener = mouse.Listener(on_move=on_mouse_move, on_click=on_click, on_scroll=on_scroll)
    keyboard_listener = keyboard.Listener(on_press=on_key_press)
    mouse_listener.start()
    keyboard_listener.start()

    print("🕵️ Context-Aware Locker running silently... Press Ctrl+C to stop.")

    try:
        while True:
            current_time = time.time()
            idle_time = current_time - last_active

            if (
                not system_locked and
                idle_time >= IDLE_THRESHOLD and
                current_time - last_trigger_time >= COOLDOWN_PERIOD
            ):
                last_trigger_time = current_time

                try:
                    # 1️⃣ Capture snapshot
                    filename, timestamp = capture_snapshot()

                    # 2️⃣ Send email alert
                    if filename:
                        subject = "System Security Alert"
                        body = f"Intruder detected at {timestamp}."
                        send_email_with_attachment(EMAIL_ADDRESS, EMAIL_PASSWORD, RECIPIENT, subject, body, filename)

                    # 3️⃣ Lock system
                    lock_system()

                    # 4️⃣ Remove snapshot after sending
                    if filename and os.path.exists(filename):
                        os.remove(filename)

                except Exception as e:
                    print(f"⚠️ Error in main loop: {e}")

                # Reset last_active to current time
                last_active = time.time()

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Stopping context-aware locker...")
    finally:
        mouse_listener.stop()
        keyboard_listener.stop()
        print("✅ Listeners stopped cleanly.")


if __name__ == "__main__":
    # Hide console window (Windows only)
    if os.name == 'nt':
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    main()
