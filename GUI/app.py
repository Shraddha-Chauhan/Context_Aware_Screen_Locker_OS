from flask import Flask, render_template, request, redirect, url_for, flash, session
import cv2
import os
import pickle
import numpy as np
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# === Admin Credentials ===
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "os12345"

# Files / folders
DB_FILE = "authorized_users.pkl"
INTRUDER_DIR = "intruder_snapshots"
LOG_FILE = "intruder_log.txt"

os.makedirs(INTRUDER_DIR, exist_ok=True)

# Load embeddings database
if os.path.exists(DB_FILE):
    with open(DB_FILE, "rb") as f:
        authorized_users = pickle.load(f)
else:
    authorized_users = {}

def save_users():
    """Save updated authorized embeddings."""
    with open(DB_FILE, "wb") as f:
        pickle.dump(authorized_users, f)

def log_intruder(snapshot_path):
    """Log intruder detection with timestamp."""
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now()} - Intruder detected: {snapshot_path}\n")

def get_face_embedding(frame):
    """Extract face embedding using multiple fallback methods."""
    try:
        # Method 1: Try DeepFace first
        try:
            from deepface import DeepFace
            embedding_obj = DeepFace.represent(frame, model_name="Facenet", enforce_detection=False)
            if embedding_obj and len(embedding_obj) > 0:
                return embedding_obj[0]["embedding"]
        except ImportError:
            # flash("DeepFace not available. Using alternative method.", "warning")
            return get_face_embedding_fallback(frame)
        except Exception as e:
            print(f"DeepFace error: {e}")
            return get_face_embedding_fallback(frame)
            
    except Exception as e:
        print(f"Face detection error: {e}")
        return None

def get_face_embedding_fallback(frame):
    """Fallback method using OpenCV for face detection and basic feature extraction."""
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        if len(faces) > 0:
            x, y, w, h = faces[0]
            face_roi = gray[y:y+h, x:x+w]
            face_resized = cv2.resize(face_roi, (100, 100))
            face_normalized = face_resized / 255.0
            embedding = face_normalized.flatten()
            return embedding.tolist()
        else:
            return None
    except Exception as e:
        print(f"Fallback face detection error: {e}")
        return None

# === Authentication Required Decorator ===
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            flash("Please log in to access the dashboard.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# === Routes ===
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            # flash("Login successful. Redirecting to welcome page...", "success")
            # Redirect to welcome animation page
            return redirect(url_for("welcome"))
        else:
            flash("Invalid username or password.", "error")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/welcome")
@login_required
def welcome():
    # Temporary welcome animation page before dashboard
    return render_template("welcome.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

@app.route("/")
@login_required
def home():
    return render_template("index.html", users=list(authorized_users.keys()))

@app.route("/add_user", methods=["GET", "POST"])
@login_required
def add_user():
    if request.method == "POST":
        name = request.form["name"].strip()
        if not name:
            flash("Please enter a valid name.", "error")
            return redirect(url_for("add_user"))
        if name in authorized_users:
            flash("User already exists!", "error")
            return redirect(url_for("add_user"))

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            flash("Error: Could not access webcam.", "error")
            return redirect(url_for("add_user"))
        ret, frame = cap.read()
        cap.release()

        if not ret:
            flash("Error: Could not capture image from webcam.", "error")
            return redirect(url_for("add_user"))

        embedding = get_face_embedding(frame)
        if embedding is not None:
            authorized_users[name] = embedding
            save_users()
            flash(f"User '{name}' added successfully! Face embedding stored.", "success")
            return redirect(url_for("home"))
        else:
            flash("Could not detect face. Please ensure your face is visible and try again.", "error")
            return redirect(url_for("add_user"))

    return render_template("add_user.html")

@app.route("/view_users")
@login_required
def view_users():
    return render_template("view_users.html", users=list(authorized_users.keys()))

@app.route("/remove_user/<name>")
@login_required
def remove_user(name):
    if name in authorized_users:
        del authorized_users[name]
        save_users()
        flash(f"User '{name}' removed successfully! Face embedding deleted.", "success")
    else:
        flash("User not found!", "error")
    return redirect(url_for("view_users"))

if __name__ == "__main__":
    app.run(debug=True)
