import os
from flask import Flask, request, jsonify, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Config
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "secret")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB

# Mail Config
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT", 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")

# Init
db = SQLAlchemy(app)
mail = Mail(app)
bcrypt = Bcrypt(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class MessageModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)

# Helpers
def get_current_user():
    user_id = session.get("user_id")
    if user_id:
        return User.query.get(user_id)
    return None

# Routes
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    hashed_pw = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    if User.query.count() == 0:  # first user becomes admin
        user = User(username=data["username"], email=data["email"], password=hashed_pw, is_admin=True)
    else:
        user = User(username=data["username"], email=data["email"], password=hashed_pw)
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "User registered"}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user = User.query.filter_by(username=data["username"]).first()
    if user and bcrypt.check_password_hash(user.password, data["password"]):
        session["user_id"] = user.id
        return jsonify({"message": "Login successful", "is_admin": user.is_admin})
    return jsonify({"error": "Invalid credentials"}), 401

@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    return jsonify({"message": "Logged out"})

@app.route("/upload", methods=["POST"])
def upload():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    file = request.files["file"]
    filename = secure_filename(file.filename)
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    file.save(path)

    new_file = File(filename=filename, user_id=user.id)
    db.session.add(new_file)
    db.session.commit()

    return jsonify({"message": "File uploaded", "filename": filename})

@app.route("/files", methods=["GET"])
def list_files():
    files = File.query.all()
    return jsonify([{"id": f.id, "filename": f.filename, "user_id": f.user_id} for f in files])

@app.route("/download/<int:file_id>", methods=["GET"])
def download(file_id):
    file = File.query.get_or_404(file_id)
    return send_from_directory(app.config["UPLOAD_FOLDER"], file.filename, as_attachment=True)

@app.route("/support", methods=["POST"])
def support():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    admin = User.query.filter_by(is_admin=True).first()
    if not admin:
        return jsonify({"error": "No admin found"}), 404

    msg = Message(subject="Support Request",
                  sender=app.config["MAIL_USERNAME"],
                  recipients=[admin.email],
                  body=f"User {user.username} wrote: {data['message']}")
    mail.send(msg)

    return jsonify({"message": "Support request sent"})

@app.route("/send_message", methods=["POST"])
def send_message():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    receiver = User.query.filter_by(username=data["receiver"]).first()
    if not receiver:
        return jsonify({"error": "User not found"}), 404

    msg = MessageModel(sender_id=user.id, receiver_id=receiver.id, content=data["content"])
    db.session.add(msg)
    db.session.commit()
    return jsonify({"message": "Message sent"})

@app.route("/get_messages", methods=["GET"])
def get_messages():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    messages = MessageModel.query.filter(
        (MessageModel.sender_id == user.id) | (MessageModel.receiver_id == user.id)
    ).all()
    return jsonify([{
        "id": m.id,
        "sender": User.query.get(m.sender_id).username,
        "receiver": User.query.get(m.receiver_id).username,
        "content": m.content
    } for m in messages])

@app.route("/admin/users", methods=["GET"])
def admin_users():
    user = get_current_user()
    if not user or not user.is_admin:
        return jsonify({"error": "Unauthorized"}), 401

    users = User.query.all()
    return jsonify([{"id": u.id, "username": u.username, "email": u.email, "is_admin": u.is_admin} for u in users])

@app.route("/admin/messages", methods=["GET"])
def admin_messages():
    user = get_current_user()
    if not user or not user.is_admin:
        return jsonify({"error": "Unauthorized"}), 401

    messages = MessageModel.query.all()
    return jsonify([{
        "id": m.id,
        "sender": User.query.get(m.sender_id).username,
        "receiver": User.query.get(m.receiver_id).username,
        "content": m.content
    } for m in messages])

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
