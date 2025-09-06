from flask import Flask, render_template, request, redirect, url_for
import cv2
import os
import pickle
import numpy as np

app = Flask(__name__)

DB_FILE = "authorized_users.pkl"

# Load database
if os.path.exists(DB_FILE):
    with open(DB_FILE, "rb") as f:
        authorized_users = pickle.load(f)
else:
    authorized_users = {}

def save_users():
    with open(DB_FILE, "wb") as f:
        pickle.dump(authorized_users, f)

# Load Haar Cascade for face detection
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

@app.route("/")
def home():
    return render_template("index.html", users=list(authorized_users.keys()))

@app.route("/add_user", methods=["GET", "POST"])
def add_user():
    if request.method == "POST":
        name = request.form["name"]

        # Capture image from webcam
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            return "Error: Could not access webcam."

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

        if len(faces) == 0:
            return "No face detected."
        elif len(faces) > 1:
            return "Multiple faces detected. Please ensure only one face is visible."

        # Save face image as encoding (for simplicity, store the cropped grayscale face)
        x, y, w, h = faces[0]
        face_img = gray[y:y+h, x:x+w]
        authorized_users[name] = face_img
        save_users()

        return redirect(url_for("home"))

    return render_template("add_user.html")

@app.route("/remove_user/<name>")
def remove_user(name):
    if name in authorized_users:
        del authorized_users[name]
        save_users()
    return redirect(url_for("home"))

@app.route("/view_users")
def view_users():
    return render_template("view_users.html", users=list(authorized_users.keys()))

if __name__ == "__main__":
    app.run(debug=True)
