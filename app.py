
from flask import Flask, request, send_from_directory, jsonify, send_file, session, redirect, url_for
import os
import json
import datetime
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this in production
UPLOAD_FOLDER = 'uploads'
METADATA_FILE = 'file_metadata.json'
USERS_FILE = 'users.json'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

CATEGORIES = [
    'Educational', 'Religious', 'Medical', 'Literature', 
    'Science', 'Technology', 'History', 'Philosophy', 'Other'
]

def load_metadata():
    """Load file metadata from JSON file"""
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_metadata(metadata):
    """Save file metadata to JSON file"""
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)

def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def get_file_size_mb(filepath):
    """Get file size in MB"""
    size_bytes = os.path.getsize(filepath)
    return round(size_bytes / (1024 * 1024), 2)

def require_login(f):
    """Decorator to require login"""
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/')
def index():
    with open("index.html", "r") as f:
        return f.read()

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not username or not email or not password:
            return jsonify({'error': 'All fields are required'}), 400
        
        users = load_users()
        
        # Check if user already exists
        for user_id, user_data in users.items():
            if user_data['username'] == username or user_data['email'] == email:
                return jsonify({'error': 'Username or email already exists'}), 400
        
        # Create new user
        user_id = hashlib.md5(f"{username}{email}{datetime.datetime.now()}".encode()).hexdigest()
        users[user_id] = {
            'username': username,
            'email': email,
            'password_hash': generate_password_hash(password),
            'join_date': datetime.datetime.now().isoformat(),
            'uploads_count': 0,
            'downloads_count': 0
        }
        
        save_users(users)
        return jsonify({'message': 'Registration successful'}), 200
        
    except Exception as e:
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        users = load_users()
        
        # Find user
        user_id = None
        user_data = None
        for uid, udata in users.items():
            if udata['username'] == username or udata['email'] == username:
                user_id = uid
                user_data = udata
                break
        
        if not user_data or not check_password_hash(user_data['password_hash'], password):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        session['user_id'] = user_id
        session['username'] = user_data['username']
        
        return jsonify({
            'message': 'Login successful',
            'user': {
                'username': user_data['username'],
                'email': user_data['email'],
                'uploads_count': user_data.get('uploads_count', 0),
                'downloads_count': user_data.get('downloads_count', 0)
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Login failed: {str(e)}'}), 500

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/user-info')
def user_info():
    if 'user_id' not in session:
        return jsonify({'logged_in': False}), 200
    
    users = load_users()
    user_data = users.get(session['user_id'], {})
    
    return jsonify({
        'logged_in': True,
        'user': {
            'username': user_data.get('username', ''),
            'email': user_data.get('email', ''),
            'uploads_count': user_data.get('uploads_count', 0),
            'downloads_count': user_data.get('downloads_count', 0)
        }
    }), 200

@app.route('/upload', methods=['POST'])
@require_login
def upload_file():
    try:
        file = request.files.get('pdf')
        category = request.form.get('category', 'Other')
        description = request.form.get('description', '').strip()
        
        if not file:
            return jsonify({'error': 'No file provided'}), 400
        
        if not file.filename:
            return jsonify({'error': 'No file selected'}), 400
            
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are allowed'}), 400
        
        if category not in CATEGORIES:
            category = 'Other'
        
        # Check file size before saving
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            return jsonify({'error': 'File size exceeds 10MB limit'}), 400
        
        # Generate unique filename if exists
        original_filename = file.filename
        filename = original_filename
        counter = 1
        while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
            name, ext = os.path.splitext(original_filename)
            filename = f"{name}_{counter}{ext}"
            counter += 1
        
        # Save file
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Save metadata
        metadata = load_metadata()
        metadata[filename] = {
            'original_name': original_filename,
            'upload_date': datetime.datetime.now().isoformat(),
            'size_mb': get_file_size_mb(filepath),
            'download_count': 0,
            'category': category,
            'description': description,
            'uploaded_by': session['username'],
            'uploader_id': session['user_id']
        }
        save_metadata(metadata)
        
        # Update user stats
        users = load_users()
        if session['user_id'] in users:
            users[session['user_id']]['uploads_count'] = users[session['user_id']].get('uploads_count', 0) + 1
            save_users(users)
        
        return jsonify({
            'message': 'Upload successful', 
            'filename': filename,
            'original_name': original_filename
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/files')
def list_files():
    try:
        files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if f.lower().endswith('.pdf')]
        metadata = load_metadata()
        
        file_list = []
        for filename in files:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file_info = {
                'filename': filename,
                'size_mb': get_file_size_mb(filepath),
                'upload_date': metadata.get(filename, {}).get('upload_date', 'Unknown'),
                'download_count': metadata.get(filename, {}).get('download_count', 0),
                'original_name': metadata.get(filename, {}).get('original_name', filename),
                'category': metadata.get(filename, {}).get('category', 'Other'),
                'description': metadata.get(filename, {}).get('description', ''),
                'uploaded_by': metadata.get(filename, {}).get('uploaded_by', 'Unknown')
            }
            file_list.append(file_info)
        
        # Sort by upload date (newest first)
        file_list.sort(key=lambda x: x['upload_date'], reverse=True)
        
        return jsonify({'files': file_list, 'categories': CATEGORIES})
    except Exception as e:
        return jsonify({'files': [], 'categories': CATEGORIES, 'error': str(e)})

@app.route('/download/<filename>')
@require_login
def download_file(filename):
    # Update download count and user stats
    metadata = load_metadata()
    if filename in metadata:
        metadata[filename]['download_count'] = metadata[filename].get('download_count', 0) + 1
        save_metadata(metadata)
    
    users = load_users()
    if session['user_id'] in users:
        users[session['user_id']]['downloads_count'] = users[session['user_id']].get('downloads_count', 0) + 1
        save_users(users)
    
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/preview/<filename>')
def preview_file(filename):
    """Serve PDF for preview in browser"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/delete/<filename>', methods=['DELETE'])
@require_login
def delete_file(filename):
    try:
        metadata = load_metadata()
        
        # Check if user owns the file or is admin
        if filename in metadata:
            uploader_id = metadata[filename].get('uploader_id', '')
            if uploader_id != session['user_id']:
                return jsonify({'error': 'You can only delete your own files'}), 403
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            
            # Remove from metadata
            if filename in metadata:
                del metadata[filename]
                save_metadata(metadata)
            
            return jsonify({'message': 'File deleted successfully'})
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Error deleting file: {str(e)}'}), 500

@app.route('/send-invite', methods=['POST'])
@require_login
def send_invite():
    """Send invitation email to a friend"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        message = data.get('message', '').strip()
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        # In a real application, you would send an actual email here
        # For this demo, we'll just simulate the process
        
        # Generate invite link
        invite_code = hashlib.md5(f"{session['username']}{email}{datetime.datetime.now()}".encode()).hexdigest()[:8]
        invite_link = f"{request.host_url}?invite={invite_code}&from={session['username']}"
        
        # Store invitation (in a real app, this would be in a database)
        invitations_file = 'invitations.json'
        invitations = {}
        if os.path.exists(invitations_file):
            with open(invitations_file, 'r') as f:
                invitations = json.load(f)
        
        invitations[invite_code] = {
            'email': email,
            'invited_by': session['username'],
            'message': message,
            'invite_link': invite_link,
            'created_at': datetime.datetime.now().isoformat(),
            'used': False
        }
        
        with open(invitations_file, 'w') as f:
            json.dump(invitations, f, indent=2)
        
        # Simulate email sending (in production, use actual email service)
        print(f"INVITE EMAIL SIMULATION:")
        print(f"To: {email}")
        print(f"From: {session['username']} via EduLibrary")
        print(f"Subject: You're invited to join EduLibrary!")
        print(f"Message: {message}")
        print(f"Link: {invite_link}")
        print("=" * 50)
        
        return jsonify({
            'message': 'Invitation sent successfully!',
            'invite_link': invite_link
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to send invitation: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
