
import time
import threading
from pynput import keyboard, mouse

# Threshold for inactivity (in seconds)
INACTIVITY_THRESHOLD = 5

# Global variable to track last activity time
last_activity_time = time.time()

# Flag to indicate whether the face recognition trigger is active
face_recognition_triggered = False


def update_activity(event_source):
    """Updates the last activity timestamp when user interacts."""
    global last_activity_time, face_recognition_triggered
    last_activity_time = time.time()
    if face_recognition_triggered:
        print(f"[INFO] {event_source} activity detected — user is active again.")
        face_recognition_triggered = False


def monitor_activity():
    """Monitors user inactivity and triggers face recognition logic."""
    global face_recognition_triggered
    while True:
        current_time = time.time()
        inactivity_duration = current_time - last_activity_time

        # If inactivity crosses the threshold
        if inactivity_duration > INACTIVITY_THRESHOLD and not face_recognition_triggered:
            print("[ALERT] No activity detected for 5 seconds.")
            trigger_face_recognition()
            face_recognition_triggered = True

        time.sleep(1)  # Avoid CPU overuse


def trigger_face_recognition():
    """
    Simulate triggering the face recognition module.
    In the real project, this will activate the webcam and start face detection.
    """
    print("[ACTION] Activating face recognition module (simulated)...")


def on_key_press(key):
    """Callback for keyboard events."""
    update_activity("Keyboard")


def on_mouse_move(x, y):
    """Callback for mouse movements."""
    update_activity("Mouse movement")


def on_mouse_click(x, y, button, pressed):
    """Callback for mouse clicks."""
    if pressed:
        update_activity("Mouse click")


def start_listeners():
    """Starts keyboard and mouse listeners in parallel threads."""
    keyboard_listener = keyboard.Listener(on_press=on_key_press)
    mouse_listener = mouse.Listener(on_move=on_mouse_move, on_click=on_mouse_click)

    keyboard_listener.start()
    mouse_listener.start()

    print("[INFO] Activity monitoring started. Move the mouse or press any key...")
    monitor_activity()


if __name__ == "__main__":
    start_listeners()
