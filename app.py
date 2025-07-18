from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import requests
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import InputRequired, Length, ValidationError, Email, DataRequired, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import or_
from dotenv import load_dotenv
import pandas as pd
from flask_wtf.file import FileField, FileAllowed
from werkzeug.utils import secure_filename
import os
import random
import mysql.connector

app = Flask(__name__)

load_dotenv()

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:GalaxyGears@localhost/flask_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'GalaxyGears'

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
UPLOAD_FOLDER = 'static/upload'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

mail = Mail(app)
db = SQLAlchemy(app)
reset_codes = {}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    location = db.Column(db.String(200))
    profile_picture = db.Column(db.String(255))

def get_user_by_id(user_id):
    return User.query.get(user_id)


class Car(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    rating = db.Column(db.Float, nullable=True)
    image_url = db.Column(db.String(255), nullable=False)
    brand = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(50), nullable=True)
    body_type = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    mileage = db.Column(db.Integer, nullable=False)
    engine_type = db.Column(db.String(50), nullable=False)
    transmission_type = db.Column(db.String(50), nullable=False)
    fuel_type = db.Column(db.String(50), nullable=True)
    condition = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)

class TradeIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    make_model = db.Column(db.String(255), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    mileage = db.Column(db.Integer, nullable=False)
    car_condition = db.Column(db.String(255), nullable=False)
    image_path = db.Column(db.String(255))
    desired_make_model = db.Column(db.String(255), nullable=False)
    budget = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[InputRequired(), Length(min=4, max=100)])
    email = StringField("Email", validators=[InputRequired(), Email()])
    password = PasswordField("Password", validators=[InputRequired(), Length(min=8)])
    submit = SubmitField("Register")

    def validate_username(self, username):
        if User.query.filter_by(username=username.data).first():
            raise ValidationError("This username is already taken. Please choose a different one.")

    def validate_email(self, email):
        if User.query.filter_by(email=email.data).first():
            raise ValidationError("This email is already registered. Please use a different email.")

class LoginForm(FlaskForm):
    username = StringField("Username or Email", validators=[InputRequired(), Length(min=4, max=100)])
    password = PasswordField("Password", validators=[InputRequired(), Length(min=8)])
    submit = SubmitField("Login")

class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Reset Password")

class ResetPasswordForm(FlaskForm):
    code = StringField("Code", validators=[InputRequired()])
    password = PasswordField("New Password", validators=[InputRequired(), Length(min=6)])
    submit = SubmitField("Reset Password")

class ProfileForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=100)])
    email = StringField('Email', validators=[InputRequired(), Email()])
    phone = StringField('Phone', validators=[Length(min=10, max=20)])
    location = StringField('Location', validators=[Length(max=255)])
    profile_picture = FileField('Profile Picture', validators=[FileAllowed(['jpg', 'png'])])
    submit = SubmitField('Update Profile')

class PurchaseHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    car_id = db.Column(db.Integer, db.ForeignKey('car.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='purchases')
    car = db.relationship('Car', backref='purchased_by')

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    car_id = db.Column(db.Integer, db.ForeignKey('car.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='cart_items')
    car = db.relationship('Car', backref='in_carts')


def process_excel_file():
    file_path = 'static/Cars.xlsx'
    df = pd.read_excel(file_path, engine='openpyxl')
    df.fillna({
        'name': 'Unknown',
        'price': 0.0,
        'rating': 0.0,
        'image_url': 'default_image_url',
        'brand': 'Unknown',
        'color': 'Unknown',
        'body_type': 'Unknown',
        'year': 0,
        'mileage': 0,
        'engine_type': 'Unknown',
        'transmission_type': 'Unknown',
        'fuel_type': 'Unknown',
        'condition': 'Unknown',
        'description': 'No description provided'
    }, inplace=True)
    for _, row in df.iterrows():
        existing_car = Car.query.filter_by(name=row['name'], image_url=row['image_url']).first()
        if existing_car:
            continue
        new_car = Car(
            name=row['name'],
            price=row['price'],
            rating=row['rating'],
            image_url=row['image_url'],
            brand=row['brand'],
            color=row['color'],
            body_type=row['body_type'],
            year=int(row['year']),
            mileage=int(row['mileage']),
            engine_type=row['engine_type'],
            transmission_type=row['transmission_type'],
            fuel_type=row['fuel_type'],
            condition=row['condition'],
            description=row['description']
        )
        db.session.add(new_car)
    db.session.commit()

with app.app_context():
    db.create_all()
    process_excel_file()

@app.route('/')
def splash():
    if 'user' in session:
        session["user_color"] = "#"+''.join([random.choice('0123456789ABCDEF') for _ in range(6)])
    return render_template('splash.html')

@app.route('/home')
def home():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    else:
        user = None
    return render_template('home.html', user=user)

@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    error = None
    if form.validate_on_submit():
        identifier = form.username.data.strip()
        password_input = form.password.data

        user = User.query.filter(
            or_(User.username.ilike(identifier), User.email.ilike(identifier))
        ).first()

        if not user:
            error = "User does not exist."
        elif not check_password_hash(user.password, password_input):
            error = "Incorrect password."
        else:
            session["user"] = user.username
            session["user_id"] = user.id
            flash('Login successful!', 'success')
            return render_template('success.html', message="Login Successful!", redirect_url=url_for('home'))

    return render_template("login.html", form=form, error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = User.query.filter(
            (User.username == form.username.data) | (User.email == form.email.data)).first()
        if existing_user:
            flash('Username or Email already exists!', 'danger')
            return redirect(url_for('register'))
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            password=generate_password_hash(form.password.data),
            phone = None,
            location = None,
            profile_picture = None
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! You can now log in.', 'success')
        return render_template('success.html', message="Registration Successful!", redirect_url=url_for('login'))
    return render_template('register.html', form=form)


@app.route('/forgot-password', methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()
    error = None
    if form.validate_on_submit():
        email = form.email.data.strip()
        user = User.query.filter_by(email=email).first()
        if user:
            code = str(random.randint(100000, 999999))
            reset_codes[email] = {
                "code": code,
                "timestamp": datetime.now()
            }
            msg = Message(
                subject="🔐 GalaxyGears Password Reset",
                sender=("GalaxyGears", app.config['MAIL_USERNAME']),
                recipients=[email]
            )
            msg.body = f"""Hello {user.username},

            We received a request to reset your GalaxyGears account password.

            🔐 Your reset code is: {code}

            ⚠️ This code will expire in 15 minutes for your security.

            If you didn’t request a password reset, no further action is required. You can safely ignore this message.

            Best regards,  
            Team GalaxyGears 🚗
            """
            mail.send(msg)
            return redirect(url_for("reset_password", email=email))
        else:
            error = "Email not found."

    return render_template("forgot_password.html", form=form, error=error)

@app.route('/reset-password/<email>', methods=["GET", "POST"])
def reset_password(email):
    form = ResetPasswordForm()
    error = None

    if form.validate_on_submit():
        code = form.code.data
        new_pass = form.password.data
        if email in reset_codes:
            stored_code = reset_codes[email]["code"]
            timestamp = reset_codes[email]["timestamp"]
            if datetime.now() - timestamp > timedelta(minutes=15):
                del reset_codes[email]
                error = "Reset code has expired. Please request a new one."
            elif stored_code == code:
                user = User.query.filter_by(email=email).first()
                if user:
                    user.password = generate_password_hash(new_pass)
                    db.session.commit()
                    del reset_codes[email]
                    return redirect(url_for("login"))
                else:
                    error = "User not found."
            else:
                error = "Invalid reset code."
        else:
            error = "Invalid or expired reset code."

        return render_template('success.html', message="Password Reset Successful!", redirect_url=url_for('login'))
    return render_template("reset_password.html", email=email, form=form, error=error)


@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        flash("Please log in to update your profile.", "warning")
        return redirect('/login')

    user = User.query.get(session['user_id'])

    if user:
        user.username = request.form.get('username', user.username)
        user.email = request.form.get('email', user.email)
        user.phone = request.form.get('phone', user.phone)
        user.location = request.form.get('location', user.location)
        try:
            db.session.commit()
            flash("Profile updated successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Database error: {str(e)}", "danger")

    return redirect(url_for('home'))

@app.route('/new_arrivals', methods=["GET", "POST"])
def new_arrivals():
    filters = request.args.to_dict()
    cleaned_filters = {k: v for k, v in filters.items() if v and v.lower() != "select"}
    page = request.args.get('page', 1, type=int)
    query = Car.query

    search_query = filters.get('query', '').strip().lower()

    if search_query:
        search = f"%{search_query}%"
        query = query.filter(
            or_(
                Car.name.ilike(search),
                Car.brand.ilike(search),
                Car.body_type.ilike(search),
                Car.engine_type.ilike(search),
                Car.fuel_type.ilike(search),
                Car.transmission_type.ilike(search),
                Car.color.ilike(search),
                Car.condition.ilike(search),
                Car.description.ilike(search)
            )
        )

    if 'price-range' in cleaned_filters:
        if cleaned_filters['price-range'] == "50000plus":
            query = query.filter(Car.price > 50000)
        else:
            try:
                price_limit = int(cleaned_filters['price-range'])
                query = query.filter(Car.price <= price_limit)
            except:
                pass

    if 'brand' in cleaned_filters:
        query = query.filter(Car.brand.ilike(f"%{cleaned_filters['brand']}%"))

    if 'body-type' in cleaned_filters:
        query = query.filter(Car.body_type.ilike(f"%{cleaned_filters['body-type']}%"))

    if 'year' in cleaned_filters:
        try:
            query = query.filter(Car.year == int(cleaned_filters['year']))
        except:
            pass

    if 'mileage-range' in cleaned_filters:
        if cleaned_filters['mileage-range'] == "10000plus":
            query = query.filter(Car.mileage > 10000)
        elif cleaned_filters['mileage-range'] == "20000plus":
            query = query.filter(Car.mileage > 20000)
        elif cleaned_filters['mileage-range'] == "30000plus":
            query = query.filter(Car.mileage > 30000)

    if 'engine-type' in cleaned_filters:
        query = query.filter(Car.engine_type.ilike(f"%{cleaned_filters['engine-type']}%"))

    if 'transmission-type' in cleaned_filters:
        query = query.filter(Car.transmission_type.ilike(f"%{cleaned_filters['transmission-type']}%"))

    if 'fuel-type' in cleaned_filters:
        query = query.filter(Car.fuel_type.ilike(f"%{cleaned_filters['fuel-type']}%"))

    if 'condition' in cleaned_filters:
        query = query.filter(Car.condition.ilike(f"%{cleaned_filters['condition']}%"))

    if 'color' in cleaned_filters:
        query = query.filter(Car.color.ilike(f"%{cleaned_filters['color']}%"))

    if 'rating' in cleaned_filters:
        try:
            min_rating = float(cleaned_filters['rating'])
            query = query.filter(Car.rating >= min_rating)
        except:
            pass

    cars = query.paginate(page=page, per_page=25, error_out=False)

    has_next = cars.has_next
    has_prev = cars.has_prev

    return render_template(
        'new_arrivals.html',
        page=page,
        has_next=has_next,
        has_prev=has_prev,
        filters=cleaned_filters,
        search_query=search_query,
        cars=cars.items
    )


@app.route('/car_details/<int:car_id>')
def car_details(car_id):
    car = Car.query.get_or_404(car_id)
    cars = Car.query.order_by(Car.id).all()

    car_ids = [c.id for c in cars]
    current_index = car_ids.index(car_id)

    prev_car_id = car_ids[current_index - 1] if current_index > 0 else None
    next_car_id = car_ids[current_index + 1] if current_index < len(car_ids) - 1 else None

    return render_template('car_details.html', car=car, prev_car_id=prev_car_id, next_car_id=next_car_id, cars=cars)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user', None)
    flash('Logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/about-us')
def about_us():
    return render_template("about_us.html")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/trade_and_exchange", methods=["GET", "POST"])
def trade_and_exchange():
    if request.method == "POST":
        make_model = request.form.get("make_model")
        year = request.form.get("year")
        mileage = request.form.get("mileage")
        car_condition = request.form.get("car_condition")
        desired_make_model = request.form.get("desired_make_model")
        budget = request.form.get("budget")
        image = request.files.get("car_image")

        filename = None
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)

        trade = TradeIn(
            make_model=make_model,
            year=int(year),
            mileage=int(mileage),
            car_condition=car_condition,
            desired_make_model=desired_make_model,
            budget=budget,
            image_path=url_for('static', filename=f'upload/{filename}') if filename else None
        )

        db.session.add(trade)
        db.session.commit()
        flash("Trade-in submitted successfully!", "success")
        return redirect(url_for("trade_and_exchange"))

    return render_template("trade_and_exchange.html")

@app.route("/thank_you")
def thank_you():
    return render_template("thank_you.html")

@app.route('/success')
def success():
    message = request.args.get('message', 'Success!')
    redirect_url = request.args.get('redirect_url', url_for('home'))
    return render_template('success.html', message=message, redirect_url=redirect_url)

@app.route('/toggle_cart/<int:car_id>', methods=['POST'])
def toggle_cart(car_id):
    if 'user_id' not in session:
        flash("Please log in to manage your cart.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    from_cart = request.args.get('from_cart') == 'true'  # Check if the request came from the cart

    try:
        cart_item = CartItem.query.filter_by(user_id=user_id, car_id=car_id).first()

        if cart_item:
            db.session.delete(cart_item)
            db.session.commit()
            flash("Car removed from cart.", "info")
        else:
            new_item = CartItem(user_id=user_id, car_id=car_id)
            db.session.add(new_item)
            db.session.commit()
            flash("Car added to cart!", "success")

    except Exception as e:
        db.session.rollback()
        flash("Something went wrong while updating your cart.", "danger")
        print("Error in toggle_cart:", e)

    if from_cart:
        return redirect(url_for('cart'))
    else:
        return redirect(url_for('car_details', car_id=car_id))

@app.route('/cart')
def view_cart():
    if 'user_id' not in session:
        flash("You need to be logged in to view your cart.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    cart_items = CartItem.query.filter_by(user_id=user_id).all()

    cars_in_cart = []
    total_price = 0

    for item in cart_items:
        car = Car.query.get(item.car_id)
        if car:
            cars_in_cart.append(car)
            total_price += car.price

    return render_template('cart.html', cars=cars_in_cart, total_price=total_price)

@app.route('/buy_now_modal', methods=['POST'])
def buy_now_modal():
    if 'user_id' not in session:
        flash("Please log in to complete the purchase.", "warning")
        return redirect(url_for('login'))

    car_id = request.form.get('car_id')
    card_number = request.form.get('card_number')
    expiry = request.form.get('expiry')
    cvv = request.form.get('cvv')

    # Simulate payment processing
    car = Car.query.get(car_id)
    print(f"Processing payment for {car.name} (${car.price}) using card {card_number}")

    flash(f"Payment for {car.name} successful!", "success")
    return redirect(url_for('view_cart'))

if __name__ == '__main__':
    app.run(debug=True)
