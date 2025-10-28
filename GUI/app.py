from flask import Flask, render_template, request, redirect, url_for, flash, session
import cv2
import os
import pickle
import numpy as np
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Admin credentials
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
    with open(DB_FILE, "wb") as f:
        pickle.dump(authorized_users, f)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            flash("Please log in to access the dashboard.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def get_face_embedding(frame):
    """Extract face embedding using OpenCV"""
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Load face detector
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        # Detect faces
        faces = face_cascade.detectMultiScale(
            gray, 
            scaleFactor=1.1, 
            minNeighbors=5, 
            minSize=(100, 100)  # Increased minimum size for better quality
        )
        
        if len(faces) > 0:
            # Get the largest face
            faces = sorted(faces, key=lambda x: x[2]*x[3], reverse=True)
            x, y, w, h = faces[0]
            
            # Extract face region
            face_roi = gray[y:y+h, x:x+w]
            
            # Resize to standard size
            face_resized = cv2.resize(face_roi, (100, 100))
            
            # Normalize pixel values
            face_normalized = face_resized / 255.0
            
            # Flatten to create embedding vector (10000 dimensions)
            embedding = face_normalized.flatten()
            
            print(f"✓ Face detected! Embedding size: {len(embedding)} dimensions")
            return embedding.tolist()
        else:
            print("✗ No face detected in the frame")
            return None
            
    except Exception as e:
        print(f"✗ Face detection error: {e}")
        return None

def verify_face_quality(frame):
    """Check if the captured face is good quality"""
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Check image brightness
        brightness = np.mean(gray)
        if brightness < 60:
            return False, "Face too dark - improve lighting"
        elif brightness > 200:
            return False, "Face too bright - reduce lighting"
            
        # Check image contrast
        contrast = np.std(gray)
        if contrast < 25:
            return False, "Low contrast - ensure good lighting"
            
        # Check if face is properly detected
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100))
        
        if len(faces) == 0:
            return False, "No face detected - ensure face is clearly visible"
            
        x, y, w, h = faces[0]
        
        # Check face size
        if w < 100 or h < 100:
            return False, "Face too small - move closer to camera"
            
        return True, "Face quality good"
        
    except Exception as e:
        return False, f"Error checking face quality: {str(e)}"

def log_intruder():
    """Log access attempts"""
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{datetime.now()} - Access attempt\n")
    except:
        pass

@app.route("/")
@login_required
def home():
    return render_template("index.html", users=list(authorized_users.keys()))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            flash("Login successful! Welcome to Screen Locker Dashboard.", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password.", "error")
            log_intruder()
    return render_template("login.html")

@app.route("/welcome")
@login_required
def welcome():
    return render_template("welcome.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("login"))

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

        # Access webcam
        print("🔍 Accessing webcam...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            flash("Could not access webcam. Please ensure a camera is connected and try again.", "error")
            return redirect(url_for("add_user"))
        
        # Set camera resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        print("📸 Capturing image from webcam...")
        ret, frame = cap.read()
        cap.release()

        if not ret:
            flash("Could not capture image from webcam. Please try again.", "error")
            return redirect(url_for("add_user"))

        # Check face quality before processing
        print("🔍 Checking face quality...")
        quality_ok, quality_message = verify_face_quality(frame)
        if not quality_ok:
            flash(f"Face capture issue: {quality_message}", "error")
            return redirect(url_for("add_user"))

        # Extract face embedding
        print("🧠 Extracting face embedding...")
        embedding = get_face_embedding(frame)
        
        if embedding is not None:
            # Store the actual face embedding
            authorized_users[name] = embedding
            save_users()
            flash(f"✅ User '{name}' added successfully! Face embedding stored.", "success")
            print(f"✅ User '{name}' registered with {len(embedding)}-dimensional face embedding")
            return redirect(url_for("home"))
        else:
            flash("❌ Could not detect a clear face. Please ensure your face is clearly visible, well-lit, and centered in the frame.", "error")
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
        flash(f"✅ User '{name}' removed successfully!", "success")
    else:
        flash("❌ User not found!", "error")
    return redirect(url_for("view_users"))

# Face recognition function for future authentication
def recognize_face(live_frame):
    """Compare live face with stored embeddings"""
    live_embedding = get_face_embedding(live_frame)
    if live_embedding is None:
        return None
    
    best_match = None
    best_score = float('inf')
    
    for name, stored_embedding in authorized_users.items():
        # Simple Euclidean distance comparison
        distance = np.linalg.norm(np.array(live_embedding) - np.array(stored_embedding))
        
        if distance < best_score:
            best_score = distance
            best_match = name
    
    # Threshold for recognition (adjust based on testing)
    if best_score < 0.5:  # You may need to adjust this threshold
        return best_match
    else:
        return "Unknown"

if __name__ == "__main__":
    print("🚀 Starting Screen Locker Application...")
    print("=" * 50)
    print("📋 Available Routes:")
    print("   http://localhost:5000/ - Dashboard")
    print("   http://localhost:5000/login - Admin Login")
    print("   http://localhost:5000/add_user - Add User")
    print("   http://localhost:5000/view_users - View Users")
    print("=" * 50)
    print(f"📊 Currently registered users: {len(authorized_users)}")
    print("✅ All systems ready!")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
