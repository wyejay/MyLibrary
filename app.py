
from flask import Flask, request, send_from_directory, jsonify, send_file, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
import os
import json
import datetime
import hashlib
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///edulibrary.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB max file size

# Email configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@edulibrary.com')

db = SQLAlchemy(app)
mail = Mail(app)

# Create upload directory
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

CATEGORIES = [
    'Educational', 'Religious', 'Medical', 'Literature', 
    'Science', 'Technology', 'History', 'Philosophy', 'Other'
]

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    join_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    uploads_count = db.Column(db.Integer, default=0)
    downloads_count = db.Column(db.Integer, default=0)
    files = db.relationship('File', backref='uploader', lazy=True, cascade='all, delete-orphan')
    support_tickets = db.relationship('SupportTicket', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'join_date': self.join_date.isoformat(),
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'uploads_count': self.uploads_count,
            'downloads_count': self.downloads_count
        }

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    size_mb = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    upload_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    download_count = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_featured = db.Column(db.Boolean, default=False)
    tags = db.Column(db.String(500))  # Comma-separated tags

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'original_name': self.original_name,
            'size_mb': self.size_mb,
            'category': self.category,
            'description': self.description,
            'upload_date': self.upload_date.isoformat(),
            'download_count': self.download_count,
            'uploaded_by': self.uploader.username,
            'uploader_id': self.user_id,
            'is_featured': self.is_featured,
            'tags': self.tags.split(',') if self.tags else []
        }

class SupportTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='medium')
    status = db.Column(db.String(20), default='open')
    created_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    resolved_date = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    admin_response = db.Column(db.Text)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'status': self.status,
            'created_date': self.created_date.isoformat(),
            'resolved_date': self.resolved_date.isoformat() if self.resolved_date else None,
            'user': self.user.username,
            'admin_response': self.admin_response
        }

class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    invite_code = db.Column(db.String(32), unique=True, nullable=False)
    invited_by = db.Column(db.String(80), nullable=False)
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    used = db.Column(db.Boolean, default=False)
    used_at = db.Column(db.DateTime)

def require_login(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def require_admin(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def get_file_size_mb(filepath):
    size_bytes = os.path.getsize(filepath)
    return round(size_bytes / (1024 * 1024), 2)

def send_email(to_email, subject, body):
    """Send email using Flask-Mail"""
    try:
        # Check if email configuration is available
        if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
            print(f"📧 Email would be sent to {to_email}: {subject}")
            print(f"📝 Body: {body}")
            return True  # Return True for demo purposes when email not configured
        
        msg = Message(subject=subject, recipients=[to_email], body=body)
        mail.send(msg)
        print(f"✅ Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Email send failed: {e}")
        print(f"📧 Would have sent to {to_email}: {subject}")
        return False  # Still continue execution even if email fails

# Initialize database
with app.app_context():
    db.create_all()
    # Create admin user if doesn't exist
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@edulibrary.com',
            is_admin=True
        )
        admin.set_password('admin123')  # Change this password!
        db.session.add(admin)
        db.session.commit()
        print("🔑 Admin user created successfully!")
        print("📧 Username: admin")
        print("🔒 Password: admin123")
        print("⚠️  Please change the admin password after first login!")

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
        invite_code = data.get('invite_code', '')
        
        if not username or not email or not password:
            return jsonify({'error': 'All fields are required'}), 400
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        # Validate invite code if provided
        if invite_code:
            invitation = Invitation.query.filter_by(invite_code=invite_code, used=False).first()
            if invitation and invitation.email == email:
                invitation.used = True
                invitation.used_at = datetime.datetime.utcnow()
        
        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        if invite_code:
            db.session.add(invitation)
        db.session.commit()
        
        return jsonify({'message': 'Registration successful'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        # Find user by username or email
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if not user or not user.check_password(password) or not user.is_active:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        session['user_id'] = user.id
        session['username'] = user.username
        session['is_admin'] = user.is_admin
        
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict()
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
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return jsonify({'logged_in': False}), 200
    
    return jsonify({
        'logged_in': True,
        'user': user.to_dict()
    }), 200

@app.route('/upload', methods=['POST'])
@require_login
def upload_file():
    try:
        file = request.files.get('pdf')
        category = request.form.get('category', 'Other')
        description = request.form.get('description', '').strip()
        tags = request.form.get('tags', '').strip()
        
        if not file or not file.filename:
            return jsonify({'error': 'No file provided'}), 400
            
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are allowed'}), 400
        
        if category not in CATEGORIES:
            category = 'Other'
        
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{original_filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Save file
        file.save(filepath)
        
        # Create database record
        file_record = File(
            filename=filename,
            original_name=original_filename,
            filepath=filepath,
            size_mb=get_file_size_mb(filepath),
            category=category,
            description=description,
            tags=tags,
            user_id=session['user_id']
        )
        
        # Update user stats
        user = User.query.get(session['user_id'])
        user.uploads_count += 1
        
        db.session.add(file_record)
        db.session.commit()
        
        return jsonify({
            'message': 'Upload successful', 
            'filename': filename,
            'original_name': original_filename
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/files')
def list_files():
    try:
        category = request.args.get('category')
        search = request.args.get('search', '').strip()
        featured_only = request.args.get('featured') == 'true'
        
        query = File.query
        
        if category and category != 'all':
            query = query.filter(File.category == category)
        
        if search:
            query = query.filter(
                (File.original_name.contains(search)) |
                (File.description.contains(search)) |
                (File.tags.contains(search))
            )
        
        if featured_only:
            query = query.filter(File.is_featured == True)
        
        files = query.order_by(File.upload_date.desc()).all()
        
        return jsonify({
            'files': [file.to_dict() for file in files],
            'categories': CATEGORIES
        })
    except Exception as e:
        return jsonify({'files': [], 'categories': CATEGORIES, 'error': str(e)})

@app.route('/download/<int:file_id>')
@require_login
def download_file(file_id):
    try:
        file_record = File.query.get_or_404(file_id)
        
        # Update download count
        file_record.download_count += 1
        user = User.query.get(session['user_id'])
        user.downloads_count += 1
        db.session.commit()
        
        return send_from_directory(
            app.config['UPLOAD_FOLDER'], 
            file_record.filename, 
            as_attachment=True,
            download_name=file_record.original_name
        )
    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

@app.route('/preview/<int:file_id>')
def preview_file(file_id):
    file_record = File.query.get_or_404(file_id)
    return send_from_directory(app.config['UPLOAD_FOLDER'], file_record.filename)

@app.route('/delete/<int:file_id>', methods=['DELETE'])
@require_login
def delete_file(file_id):
    try:
        file_record = File.query.get_or_404(file_id)
        user = User.query.get(session['user_id'])
        
        # Check permissions
        if file_record.user_id != session['user_id'] and not user.is_admin:
            return jsonify({'error': 'You can only delete your own files'}), 403
        
        # Delete physical file
        if os.path.exists(file_record.filepath):
            os.remove(file_record.filepath)
        
        # Update user stats
        if file_record.user_id == session['user_id']:
            user.uploads_count = max(0, user.uploads_count - 1)
        
        db.session.delete(file_record)
        db.session.commit()
        
        return jsonify({'message': 'File deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error deleting file: {str(e)}'}), 500

@app.route('/send-invite', methods=['POST'])
@require_login
def send_invite():
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        message = data.get('message', '').strip()
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        # Generate invite code
        invite_code = secrets.token_hex(16)
        invite_link = f"{request.host_url}?invite={invite_code}&email={email}"
        
        # Store invitation
        invitation = Invitation(
            email=email,
            invite_code=invite_code,
            invited_by=session['username'],
            message=message
        )
        db.session.add(invitation)
        db.session.commit()
        
        # Send email
        email_body = f"""
Hello!

{session['username']} has invited you to join EduLibrary - a collaborative digital library platform.

{message if message else 'Join us to share and discover educational resources!'}

Click the link below to join:
{invite_link}

Best regards,
The EduLibrary Team
        """
        
        if send_email(email, "You're invited to join EduLibrary!", email_body):
            return jsonify({
                'message': 'Invitation sent successfully!',
                'invite_link': invite_link
            }), 200
        else:
            return jsonify({
                'message': 'Invitation created but email could not be sent. Check email configuration.',
                'invite_link': invite_link
            }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to send invitation: {str(e)}'}), 500

@app.route('/support/tickets', methods=['GET', 'POST'])
@require_login
def support_tickets():
    if request.method == 'POST':
        try:
            data = request.get_json()
            title = data.get('title', '').strip()
            description = data.get('description', '').strip()
            priority = data.get('priority', 'medium')
            
            if not title or not description:
                return jsonify({'error': 'Title and description are required'}), 400
            
            ticket = SupportTicket(
                title=title,
                description=description,
                priority=priority,
                user_id=session['user_id']
            )
            db.session.add(ticket)
            db.session.commit()
            
            # Send notification email to admin
            admin_email = os.getenv('ADMIN_EMAIL', 'admin@edulibrary.com')
            email_body = f"""
New support ticket created:

Title: {title}
Priority: {priority}
User: {session['username']}
Description: {description}

Please log in to the admin panel to respond.
            """
            send_email(admin_email, f"New Support Ticket: {title}", email_body)
            
            return jsonify({'message': 'Support ticket created successfully'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Failed to create ticket: {str(e)}'}), 500
    
    else:  # GET
        user = User.query.get(session['user_id'])
        if user.is_admin:
            tickets = SupportTicket.query.order_by(SupportTicket.created_date.desc()).all()
        else:
            tickets = SupportTicket.query.filter_by(user_id=session['user_id']).order_by(SupportTicket.created_date.desc()).all()
        
        return jsonify({'tickets': [ticket.to_dict() for ticket in tickets]})

# Admin Routes
@app.route('/admin/users')
@require_admin
def admin_users():
    users = User.query.order_by(User.join_date.desc()).all()
    return jsonify({'users': [user.to_dict() for user in users]})

@app.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@require_admin
def toggle_user_status(user_id):
    try:
        user = User.query.get_or_404(user_id)
        if user.is_admin:
            return jsonify({'error': 'Cannot modify admin user'}), 400
        
        user.is_active = not user.is_active
        db.session.commit()
        
        # Send notification email to user
        status_text = "activated" if user.is_active else "deactivated"
        email_body = f"""
Hello {user.username},

Your EduLibrary account has been {status_text} by an administrator.

Status: {"Active" if user.is_active else "Inactive"}

If you have any questions, please contact our support team.

Best regards,
The EduLibrary Team
        """
        send_email(user.email, f"Account Status Update", email_body)
        
        return jsonify({
            'message': f'User {status_text} successfully',
            'user': user.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update user: {str(e)}'}), 500

@app.route('/admin/users/<int:user_id>/delete', methods=['DELETE'])
@require_admin
def delete_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        if user.is_admin:
            return jsonify({'error': 'Cannot delete admin user'}), 400
        
        # Delete user's files first
        user_files = File.query.filter_by(user_id=user_id).all()
        for file_record in user_files:
            if os.path.exists(file_record.filepath):
                os.remove(file_record.filepath)
        
        # Delete user and cascade will handle related records
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'message': 'User deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete user: {str(e)}'}), 500

@app.route('/admin/files/featured/<int:file_id>', methods=['POST'])
@require_admin
def toggle_featured_file(file_id):
    try:
        file_record = File.query.get_or_404(file_id)
        file_record.is_featured = not file_record.is_featured
        db.session.commit()
        
        return jsonify({
            'message': f'File {"featured" if file_record.is_featured else "unfeatured"} successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update file: {str(e)}'}), 500

@app.route('/admin/tickets/<int:ticket_id>/respond', methods=['POST'])
@require_admin
def respond_to_ticket(ticket_id):
    try:
        data = request.get_json()
        response = data.get('response', '').strip()
        status = data.get('status', 'open')
        
        if not response:
            return jsonify({'error': 'Response is required'}), 400
        
        ticket = SupportTicket.query.get_or_404(ticket_id)
        ticket.admin_response = response
        ticket.status = status
        if status == 'resolved':
            ticket.resolved_date = datetime.datetime.utcnow()
        
        db.session.commit()
        
        # Send email to user
        email_body = f"""
Hello {ticket.user.username},

Your support ticket "{ticket.title}" has been updated.

Admin Response: {response}
Status: {status}

Thank you for using EduLibrary!
        """
        send_email(ticket.user.email, f"Support Ticket Update: {ticket.title}", email_body)
        
        return jsonify({'message': 'Response sent successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to respond: {str(e)}'}), 500

@app.route('/analytics')
@require_admin
def analytics():
    try:
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        total_files = File.query.count()
        total_downloads = db.session.query(db.func.sum(File.download_count)).scalar() or 0
        total_size = db.session.query(db.func.sum(File.size_mb)).scalar() or 0
        
        # Category distribution
        categories_data = db.session.query(
            File.category, 
            db.func.count(File.id)
        ).group_by(File.category).all()
        
        # Recent activity
        recent_uploads = File.query.order_by(File.upload_date.desc()).limit(10).all()
        
        # Support tickets stats
        open_tickets = SupportTicket.query.filter_by(status='open').count()
        total_tickets = SupportTicket.query.count()
        
        return jsonify({
            'stats': {
                'total_users': total_users,
                'active_users': active_users,
                'total_files': total_files,
                'total_downloads': total_downloads,
                'total_size_mb': round(total_size, 2),
                'open_tickets': open_tickets,
                'total_tickets': total_tickets
            },
            'categories': [{'category': cat, 'count': count} for cat, count in categories_data],
            'recent_uploads': [file.to_dict() for file in recent_uploads]
        })
    except Exception as e:
        return jsonify({'error': f'Failed to load analytics: {str(e)}'}), 500

@app.route('/admin/backup', methods=['POST'])
@require_admin
def create_backup():
    try:
        import datetime
        import shutil
        
        backup_dir = f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(backup_dir, exist_ok=True)
        
        # Backup database
        shutil.copy2('edulibrary.db', os.path.join(backup_dir, 'edulibrary.db'))
        
        # Backup uploads
        if os.path.exists('uploads'):
            shutil.copytree('uploads', os.path.join(backup_dir, 'uploads'))
        
        return jsonify({'message': f'Backup created successfully: {backup_dir}'})
    except Exception as e:
        return jsonify({'error': f'Backup failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
