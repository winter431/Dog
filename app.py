from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

# App setup
app = Flask(__name__)
app.secret_key = 'secret_key'

# Upload config
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dogs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), default='user')  # user or admin

# Dog model
class Dog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    breed = db.Column(db.String(100))
    age = db.Column(db.String(50))
    size = db.Column(db.String(50))
    temperament = db.Column(db.String(100))
    medical_history = db.Column(db.String(200))
    special_needs = db.Column(db.String(200))
    status = db.Column(db.String(50))
    image_url = db.Column(db.String(200))

# Adoption Application model
class AdoptionApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    dog_id = db.Column(db.Integer, db.ForeignKey('dog.id'), nullable=False)
    user = db.relationship('User', back_populates='applications')
    dog = db.relationship('Dog', back_populates='applications')
    status = db.Column(db.String(20), default='pending')  # pending, approved, denied

User.applications = db.relationship('AdoptionApplication', back_populates='user')
Dog.applications = db.relationship('AdoptionApplication', back_populates='dog')

# Message model
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')

# Create DB tables
with app.app_context():
    db.create_all()

# Check if admin exists, and create one if not
def create_admin_account():
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin_password = generate_password_hash("adminpassword")  # Change this password as needed
        new_admin = User(name="Admin", email="admin@admin.com", password=admin_password, role='admin')
        db.session.add(new_admin)
        db.session.commit()
        print("Admin account created")

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user'] = user.name
            session['role'] = user.role
            session['user_id'] = user.id
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('view_dogs'))
        else:
            return "Invalid email or password!"
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return "User already exists!"

        new_user = User(name=name, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route("/add-dog", methods=["GET"])
def add_dog():
    return render_template("add_dog.html")

@app.route('/dogs', methods=['GET', 'POST'])
def dogs():
    if 'user' not in session or session.get('role') != 'admin':
        return "Access Denied", 403

    if request.method == 'POST':
        # form handling for admins
        name = request.form['name']
        breed = request.form['breed']
        age = request.form['age']
        size = request.form['size']
        temperament = request.form['temperament']
        medical_history = request.form['medical_history']
        special_needs = request.form['special_needs']
        status = request.form['status']

        image = request.files.get('image')
        image_url = None
        if image:
            image_filename = image.filename
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image.save(image_path)
            image_url = image_path

        new_dog = Dog(name=name, breed=breed, age=age, size=size,
                      temperament=temperament, medical_history=medical_history,
                      special_needs=special_needs, status=status, image_url=image_url)
        db.session.add(new_dog)
        db.session.commit()
        
        return redirect(url_for('admin_dashboard'))  # Redirect to the admin dashboard after adding a dog

    dogs = Dog.query.filter(Dog.status != 'Adopted').all()  # Exclude adopted dogs
    return render_template('admin_dashboard.html', dogs=dogs)

@app.route('/view_dogs')
def view_dogs():
    if 'user' not in session:
        return redirect(url_for('login'))

    search = request.args.get('search', '')
    if search:
        dogs = Dog.query.filter(
            Dog.status != 'Adopted',
            (Dog.name.ilike(f"%{search}%")) | (Dog.breed.ilike(f"%{search}%"))
        ).all()
    else:
        dogs = Dog.query.filter(Dog.status != 'Adopted').all()

    user_id = session.get('user_id')
    user_applications = AdoptionApplication.query.filter_by(user_id=user_id).all()

    return render_template('dogs.html', user=session['user'], dogs=dogs, user_applications=user_applications)

@app.route('/edit_dog/<int:dog_id>', methods=['GET', 'POST'])
def edit_dog(dog_id):
    if 'user' not in session or session.get('role') != 'admin':
        return "Access Denied", 403

    dog = Dog.query.get_or_404(dog_id)

    if request.method == 'POST':
        dog.name = request.form['name']
        dog.breed = request.form['breed']
        dog.age = request.form['age']
        dog.size = request.form['size']
        dog.temperament = request.form['temperament']
        dog.medical_history = request.form['medical_history']
        dog.special_needs = request.form['special_needs']
        dog.status = request.form['status']
        db.session.commit()
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_dog.html', dog=dog)

@app.route('/adopted_dogs')
def adopted_dogs():
    if 'user' not in session or session.get('role') != 'admin':
        return "Access Denied", 403

    adopted_dogs = Dog.query.filter_by(status='Adopted').all()
    return render_template('adopted_dogs.html', dogs=adopted_dogs)

@app.route('/mark_adopted/<int:dog_id>')
def mark_adopted(dog_id):
    if 'user' not in session or session.get('role') != 'admin':
        return "Access Denied", 403

    dog = Dog.query.get_or_404(dog_id)
    dog.status = 'Adopted'
    db.session.commit()
    return redirect(url_for('admin_dashboard'))  # Redirect to admin dashboard after marking the dog as adopted


@app.route('/delete_dog/<int:dog_id>', methods=['POST', 'GET'])
def delete_dog(dog_id):
    if 'user' not in session or session.get('role') != 'admin':
        return "Access Denied", 403

    dog = Dog.query.get_or_404(dog_id)
    db.session.delete(dog)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/apply_for_adoption/<int:dog_id>', methods=['POST'])
def apply_for_adoption(dog_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    dog = Dog.query.get_or_404(dog_id)
    user = User.query.get(session['user_id'])

    # Check if the user has already applied for this dog
    existing_application = AdoptionApplication.query.filter_by(user_id=user.id, dog_id=dog.id).first()
    if existing_application:
        return "You have already applied to adopt this dog."

    # Create adoption application
    application = AdoptionApplication(user_id=user.id, dog_id=dog.id)
    db.session.add(application)
    db.session.commit()

    return redirect(url_for('dogs'))

@app.route('/admin')
def admin_dashboard():
    if 'user' not in session or session.get('role') != 'admin':
        return "Access Denied", 403
    all_dogs = Dog.query.all()
    applications = AdoptionApplication.query.all()  # Get all adoption applications
    return render_template('admin.html', dogs=all_dogs, admin=session['user'], applications=applications)


@app.route('/approve_adoption/<int:application_id>', methods=['POST'])
def approve_adoption(application_id):
    # Find the adoption application by ID (assuming you're using SQLAlchemy)
    application = AdoptionApplication.query.get(application_id)
    
    if not application:
        # If the application does not exist, return a 404 response
        return "Application not found", 404

    # Set the application status to "approved"
    application.status = 'approved'
    db.session.commit()  # Save changes to the database

    # Redirect to another page (e.g. admin dashboard or applications page)
    return redirect(url_for('admin_dashboard'))


@app.route('/deny_adoption/<int:application_id>', methods=['POST'])
def deny_adoption(application_id):
    # Add your logic to deny the adoption here
    # e.g. update application status in the database
    return redirect(url_for('admin_dashboard'))  # Or wherever you want to redirect

# Messaging Routes
@app.route('/messages')
def messages():
    return render_template('messages.html')


@app.route('/send_message/<int:receiver_id>', methods=['GET', 'POST'])
def send_message(receiver_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        content = request.form['content']
        sender_id = session['user_id']

        new_message = Message(sender_id=sender_id, receiver_id=receiver_id, content=content)
        db.session.add(new_message)
        db.session.commit()

        return redirect(url_for('messages'))

    return render_template('send_message.html', receiver_id=receiver_id)

@app.route('/logout')
def logout():
    # Clear the session to log out the user
    session.clear()
    return redirect(url_for('login'))  # Redirect to the login page after logout


# Run the app
if __name__ == "__main__":
    with app.app_context():  # Wrap create_admin_account() inside the app context
        create_admin_account()
    app.run(debug=True)

