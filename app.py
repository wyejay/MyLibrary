from flask import Flask, request, send_from_directory, jsonify, send_file, session, redirect, url_for
import os
import json
import datetime
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# -------------------- Config & storage root --------------------
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')  # Change in production

# STORAGE_ROOT: where all persistent files and uploads live.
# On Render / other hosts, mount a persistent disk to /data and set STORAGE_ROOT=/data/edulibrary (or leave default /data/edulibrary).
# Defaults: prefer /data/edulibrary if exists, otherwise use ./data in repo.
_env_root = os.environ.get('STORAGE_ROOT')
if _env_root:
    STORAGE_ROOT = _env_root
elif os.path.exists('/data'):
    STORAGE_ROOT = '/data/edulibrary'
else:
    STORAGE_ROOT = './data'

os.makedirs(STORAGE_ROOT, exist_ok=True)

# Paths to persistent files
UPLOAD_FOLDER = os.path.join(STORAGE_ROOT, 'uploads')
METADATA_FILE = os.path.join(STORAGE_ROOT, 'file_metadata.json')
USERS_FILE = os.path.join(STORAGE_ROOT, 'users.json')
INVITATIONS_FILE = os.path.join(STORAGE_ROOT, 'invitations.json')
SUPPORT_FILE = os.path.join(STORAGE_ROOT, 'support.json')
MESSAGES_FILE = os.path.join(STORAGE_ROOT, 'messages.json')

# create folders if missing
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size

# -------------------- Categories --------------------
CATEGORIES = [
    'Educational', 'Religious', 'Medical', 'Literature',
    'Science', 'Technology', 'History', 'Philosophy', 'Other'
]

# -------------------- Helpers for JSON persistence --------------------
def _read_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except Exception:
        # if file corrupted, overwrite on save
        return default
    return default

def _write_json(path, data):
    tmp = f"{path}.tmp"
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

def load_metadata():
    """Load file metadata from JSON file"""
    return _read_json(METADATA_FILE, {})

def save_metadata(metadata):
    """Save file metadata to JSON file"""
    _write_json(METADATA_FILE, metadata)

def load_users():
    """Load users from JSON file"""
    return _read_json(USERS_FILE, {})

def save_users(users):
    """Save users to JSON file"""
    _write_json(USERS_FILE, users)

def load_invitations():
    return _read_json(INVITATIONS_FILE, {})

def save_invitations(inv):
    _write_json(INVITATIONS_FILE, inv)

def load_support():
    """Support data format:
    {
      "tickets": {
         "<ticket_id>": {
             "id": "<ticket_id>", "user_id": "<uid>", "subject": "...",
             "body": "...", "status": "open", "created_at": "...", "replies": [ {reply}, ... ]
         }
      },
      "next_id": 1
    }
    """
    return _read_json(SUPPORT_FILE, {"tickets": {}, "next_id": 1})

def save_support(support):
    _write_json(SUPPORT_FILE, support)

def load_messages():
    """Messages stored as:
    { "messages": { "<msg_id>": {id, sender_id, receiver_id, content, created_at, read:false} }, "next_id": 1 }"""
    return _read_json(MESSAGES_FILE, {"messages": {}, "next_id": 1})

def save_messages(msgs):
    _write_json(MESSAGES_FILE, msgs)

def get_file_size_mb(filepath):
    """Get file size in MB"""
    size_bytes = os.path.getsize(filepath)
    return round(size_bytes / (1024 * 1024), 2)

# -------------------- Auth utilities --------------------
def require_login(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def require_admin(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        users = load_users()
        u = users.get(session['user_id'])
        if not u or not u.get('is_admin'):
            return jsonify({'error': 'Admin privileges required'}), 403
        return f(*args, **kwargs)
    return decorated

# -------------------- Routes (original ones preserved) --------------------
@app.route('/')
def index():
    # Keep same behaviour: serve index.html from project root (unchanged)
    try:
        with open("index.html", "r") as f:
            return f.read()
    except Exception:
        return "<h1>EduLibrary</h1><p>Index not found.</p>"

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

        # Create new user id
        user_id = hashlib.md5(f"{username}{email}{datetime.datetime.now()}".encode()).hexdigest()
        # Determine if first admin: if no existing user has is_admin true -> this becomes admin
        is_admin = True if not any(u.get('is_admin') for u in users.values()) else False

        users[user_id] = {
            'username': username,
            'email': email,
            'password_hash': generate_password_hash(password),
            'join_date': datetime.datetime.now().isoformat(),
            'uploads_count': 0,
            'downloads_count': 0,
            'is_admin': is_admin
        }

        save_users(users)

        # Auto-login after register (same behaviour as before)
        session['user_id'] = user_id
        session['username'] = username
        session['is_admin'] = is_admin

        return jsonify({
            'message': 'Registration successful',
            'user': {
                'username': username,
                'email': email,
                'is_admin': is_admin
            }
        }), 200

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

        # Find user (by username or email)
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
        session['is_admin'] = user_data.get('is_admin', False)

        return jsonify({
            'message': 'Login successful',
            'user': {
                'username': user_data['username'],
                'email': user_data['email'],
                'uploads_count': user_data.get('uploads_count', 0),
                'downloads_count': user_data.get('downloads_count', 0),
                'is_admin': user_data.get('is_admin', False)
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
            'downloads_count': user_data.get('downloads_count', 0),
            'is_admin': user_data.get('is_admin', False)
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

        if file_size > app.config['MAX_CONTENT_LENGTH']:  # 10MB limit
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
                'uploaded_by': metadata.get(filename, {}).get('uploaded_by', 'Unknown'),
                'uploader_id': metadata.get(filename, {}).get('uploader_id', '')
            }
            file_list.append(file_info)

        # Sort by upload date (newest first). If upload_date unknown, treat as older.
        def _sort_key(x):
            try:
                return x['upload_date']
            except Exception:
                return ''
        file_list.sort(key=_sort_key, reverse=True)

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

    # Serve file
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
                # allow admin to delete any file
                users = load_users()
                cur_user = users.get(session['user_id'], {})
                if not cur_user.get('is_admin'):
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
    """Send invitation email to a friend (simulated)"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        message = data.get('message', '').strip()

        if not email:
            return jsonify({'error': 'Email is required'}), 400

        # Generate invite link
        invite_code = hashlib.md5(f"{session['username']}{email}{datetime.datetime.now()}".encode()).hexdigest()[:8]
        invite_link = f"{request.host_url}?invite={invite_code}&from={session['username']}"

        invitations = load_invitations()
        invitations[invite_code] = {
            'email': email,
            'invited_by': session['username'],
            'message': message,
            'invite_link': invite_link,
            'created_at': datetime.datetime.now().isoformat(),
            'used': False
        }
        save_invitations(invitations)

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

# -------------------- New: Support (customer care) --------------------
@app.route('/support/create', methods=['POST'])
@require_login
def support_create():
    """Create a support ticket"""
    try:
        data = request.get_json()
        subject = (data.get('subject') or '').strip()
        body = (data.get('body') or '').strip()
        if not subject or not body:
            return jsonify({'error': 'subject and body required'}), 400

        support = load_support()
        tid = str(support['next_id'])
        ticket = {
            'id': tid,
            'user_id': session['user_id'],
            'subject': subject,
            'body': body,
            'status': 'open',
            'created_at': datetime.datetime.now().isoformat(),
            'replies': []
        }
        support['tickets'][tid] = ticket
        support['next_id'] = support['next_id'] + 1
        save_support(support)
        return jsonify({'message': 'created', 'ticket_id': tid})
    except Exception as e:
        return jsonify({'error': f'Failed to create ticket: {str(e)}'}), 500

@app.route('/support/my', methods=['GET'])
@require_login
def support_my():
    """List tickets for current user"""
    support = load_support()
    tickets = []
    for t in support['tickets'].values():
        if t['user_id'] == session['user_id']:
            tickets.append(t)
    # newest first
    tickets.sort(key=lambda x: x['created_at'], reverse=True)
    return jsonify({'tickets': tickets})

@app.route('/support/reply', methods=['POST'])
@require_login
def support_reply():
    """Reply to a support ticket. Users may reply only to their own tickets; admins can reply to any."""
    try:
        data = request.get_json()
        ticket_id = str(data.get('ticket_id'))
        body = (data.get('body') or '').strip()
        if not ticket_id or not body:
            return jsonify({'error': 'ticket_id and body required'}), 400

        support = load_support()
        ticket = support['tickets'].get(ticket_id)
        if not ticket:
            return jsonify({'error': 'ticket not found'}), 404

        # permission
        users = load_users()
        cur_user = users.get(session['user_id'], {})
        if ticket['user_id'] != session['user_id'] and not cur_user.get('is_admin'):
            return jsonify({'error': 'forbidden'}), 403

        reply = {
            'sender_id': session['user_id'],
            'sender_username': session.get('username'),
            'body': body,
            'created_at': datetime.datetime.now().isoformat()
        }
        ticket['replies'].append(reply)
        # if admin replies, optionally set status to pending
        if cur_user.get('is_admin'):
            ticket['status'] = 'pending'
        save_support(support)
        return jsonify({'message': 'replied'})
    except Exception as e:
        return jsonify({'error': f'Failed to reply: {str(e)}'}), 500

# -------------------- New: Admin endpoints --------------------
@app.route('/admin/users', methods=['GET'])
@require_admin
def admin_list_users():
    users = load_users()
    out = []
    for uid, u in users.items():
        out.append({
            'id': uid,
            'username': u.get('username'),
            'email': u.get('email'),
            'uploads_count': u.get('uploads_count', 0),
            'downloads_count': u.get('downloads_count', 0),
            'is_admin': u.get('is_admin', False),
            'join_date': u.get('join_date')
        })
    # newest first
    out.sort(key=lambda x: x.get('join_date', ''), reverse=True)
    return jsonify({'users': out})

@app.route('/admin/user/<user_id>', methods=['PATCH'])
@require_admin
def admin_toggle_admin(user_id):
    """Toggle is_admin for a user. Admin cannot change their own role."""
    try:
        users = load_users()
        if user_id not in users:
            return jsonify({'error': 'user not found'}), 404
        if user_id == session['user_id']:
            return jsonify({'error': 'cannot change your own role'}), 400
        data = request.get_json()
        make_admin = data.get('is_admin')
        if make_admin is None:
            return jsonify({'error': 'is_admin required'}), 400
        users[user_id]['is_admin'] = bool(make_admin)
        save_users(users)
        return jsonify({'message': 'updated', 'user_id': user_id, 'is_admin': users[user_id]['is_admin']})
    except Exception as e:
        return jsonify({'error': f'Failed to update user: {str(e)}'}), 500

@app.route('/admin/support', methods=['GET'])
@require_admin
def admin_support_list():
    support = load_support()
    tickets = list(support['tickets'].values())
    tickets.sort(key=lambda x: x['created_at'], reverse=True)
    return jsonify({'tickets': tickets})

@app.route('/admin/support/<ticket_id>', methods=['PATCH'])
@require_admin
def admin_support_update(ticket_id):
    try:
        support = load_support()
        t = support['tickets'].get(str(ticket_id))
        if not t:
            return jsonify({'error': 'ticket not found'}), 404
        data = request.get_json()
        status = data.get('status')
        if status not in ['open', 'pending', 'closed']:
            return jsonify({'error': 'invalid status (open|pending|closed expected)'}), 400
        t['status'] = status
        save_support(support)
        return jsonify({'message': 'updated'})
    except Exception as e:
        return jsonify({'error': f'Failed to update ticket: {str(e)}'}), 500

# -------------------- New: Messaging (user <-> user) --------------------
@app.route('/messages/send', methods=['POST'])
@require_login
def send_message():
    try:
        data = request.get_json()
        to_user_id = data.get('to_user_id')
        content = (data.get('content') or '').strip()
        if not to_user_id or not content:
            return jsonify({'error': 'to_user_id and content required'}), 400

        users = load_users()
        if to_user_id not in users:
            return jsonify({'error': 'receiver not found'}), 404

        msgs = load_messages()
        mid = str(msgs['next_id'])
        msg = {
            'id': mid,
            'sender_id': session['user_id'],
            'sender_username': session.get('username'),
            'receiver_id': to_user_id,
            'content': content,
            'created_at': datetime.datetime.now().isoformat(),
            'read': False
        }
        msgs['messages'][mid] = msg
        msgs['next_id'] = msgs['next_id'] + 1
        save_messages(msgs)
        return jsonify({'message': 'sent', 'id': mid})
    except Exception as e:
        return jsonify({'error': f'Failed to send message: {str(e)}'}), 500

@app.route('/messages/inbox', methods=['GET'])
@require_login
def inbox():
    msgs = load_messages()
    out = [m for m in msgs['messages'].values() if m['receiver_id'] == session['user_id']]
    out.sort(key=lambda x: x['created_at'], reverse=True)
    return jsonify({'inbox': out})

@app.route('/messages/sent', methods=['GET'])
@require_login
def sent_messages():
    msgs = load_messages()
    out = [m for m in msgs['messages'].values() if m['sender_id'] == session['user_id']]
    out.sort(key=lambda x: x['created_at'], reverse=True)
    return jsonify({'sent': out})

@app.route('/messages/mark-read', methods=['POST'])
@require_login
def mark_read():
    try:
        data = request.get_json()
        msg_id = str(data.get('message_id'))
        if not msg_id:
            return jsonify({'error': 'message_id required'}), 400
        msgs = load_messages()
        m = msgs['messages'].get(msg_id)
        if not m:
            return jsonify({'error': 'message not found'}), 404
        # only receiver or admin can mark read
        users = load_users()
        cur_user = users.get(session['user_id'], {})
        if m['receiver_id'] != session['user_id'] and not cur_user.get('is_admin'):
            return jsonify({'error': 'forbidden'}), 403
        m['read'] = True
        save_messages(msgs)
        return jsonify({'message': 'ok'})
    except Exception as e:
        return jsonify({'error': f'Failed to mark read: {str(e)}'}), 500

# -------------------- Health & debug route --------------------
@app.route('/health')
def health():
    return jsonify({'ok': True, 'storage_root': STORAGE_ROOT}), 200

if __name__ == '__main__':
    # ensure storage files exist so first run won't fail
    for p in [METADATA_FILE, USERS_FILE, INVITATIONS_FILE, SUPPORT_FILE, MESSAGES_FILE]:
        if not os.path.exists(p):
            # create with sensible defaults
            if p == METADATA_FILE:
                _write_json(p, {})
            elif p == USERS_FILE:
                _write_json(p, {})
            elif p == INVITATIONS_FILE:
                _write_json(p, {})
            elif p == SUPPORT_FILE:
                _write_json(p, {"tickets": {}, "next_id": 1})
            elif p == MESSAGES_FILE:
                _write_json(p, {"messages": {}, "next_id": 1})
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
