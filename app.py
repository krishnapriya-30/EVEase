from flask import Flask, render_template, request, session, redirect
import mysql.connector
import os

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash


load_dotenv()


app = Flask(__name__)
app.secret_key = "evease-development-secret-key"


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_db_connection():
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

    return connection


# ==========================================
# DRIVER MODULE DATABASE SETUP
# ==========================================

def ensure_driver_schema():
    """Create the driver table and booking association when missing."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS drivers
            (
                id INT NOT NULL AUTO_INCREMENT,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(150) NOT NULL,
                phone VARCHAR(15) NOT NULL,
                password VARCHAR(255) NOT NULL,
                license_no VARCHAR(50) NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'Active',
                created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY email (email),
                UNIQUE KEY license_no (license_no)
            )
            """
        )

        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'driver_id'")

        if not cursor.fetchone():
            cursor.execute(
                """
                ALTER TABLE bookings
                ADD COLUMN driver_id INT NULL,
                ADD KEY driver_id (driver_id)
                """
            )

        connection.commit()

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


ensure_driver_schema()


# ==========================================
# ADMIN MODULE DATABASE SETUP
# ==========================================

def ensure_admin_schema():
    """Create the admin table when it does not already exist."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS admins
            (
                id INT NOT NULL AUTO_INCREMENT,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(150) NOT NULL,
                password VARCHAR(255) NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'Active',
                created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY email (email)
            )
            """
        )

        connection.commit()

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


ensure_admin_schema()


# ==========================================
# EVEASE HOME PAGE
# ==========================================

@app.route("/")
def home():
    return render_template("home.html")


# ==========================================
# OWNER REGISTRATION
# ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    # ------------------------------------------
    # VALIDATION
    # ------------------------------------------

    if not name or not email or not phone or not password:
        return "Please fill in all required fields."

    if password != confirm_password:
        return "Passwords do not match."

    if len(password) < 6:
        return "Password must be at least 6 characters long."

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if email already exists
        cursor.execute(
            """
            SELECT id
            FROM owners
            WHERE email = %s
            """,
            (email,)
        )

        existing_owner = cursor.fetchone()

        if existing_owner:
            return render_template(
                "auth_message.html",
                title="Account Already Exists",
                message="An account with this email address already exists. Please login to your existing EVEase account.",
                name=None,
                email=email,
                button_text="Login to EVEase",
                button_url="/login"
            )

        # ------------------------------------------
        # HASH PASSWORD
        # ------------------------------------------

        hashed_password = generate_password_hash(password)

        # ------------------------------------------
        # INSERT OWNER
        # ------------------------------------------

        cursor.execute(
            """
            INSERT INTO owners
            (
                name,
                email,
                phone,
                password
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                name,
                email,
                phone,
                hashed_password
            )
        )

        connection.commit()

        # ------------------------------------------
        # REGISTRATION SUCCESS
        # ------------------------------------------

        return render_template(
            "auth_message.html",
            title="Registration Successful!",
            message="Your EVEase account has been created successfully.",
            name=name,
            email=email,
            button_text="Login to EVEase",
            button_url="/login"
        )

    except mysql.connector.Error as error:

        if connection:
            connection.rollback()

        return f"""
        <h1>Registration Failed</h1>
        <p>Something went wrong while creating your account.</p>
        <p>Error: {error}</p>
        """

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# OWNER LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    # ------------------------------------------
    # VALIDATION
    # ------------------------------------------

    if not email or not password:
        return render_template(
            "auth_message.html",
            title="Login Failed",
            message="Please enter your email and password.",
            name=None,
            email=None,
            button_text="Try Again",
            button_url="/login"
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                name,
                email,
                password
            FROM owners
            WHERE email = %s
            """,
            (email,)
        )

        owner = cursor.fetchone()

        # ------------------------------------------
        # ACCOUNT NOT FOUND
        # ------------------------------------------

        if not owner:
            return render_template(
                "auth_message.html",
                title="Login Failed",
                message="The email address or password you entered is incorrect.",
                name=None,
                email=None,
                button_text="Try Again",
                button_url="/login"
            )

        # ------------------------------------------
        # PASSWORD CHECK
        # ------------------------------------------

        if not check_password_hash(owner["password"], password):
            return render_template(
                "auth_message.html",
                title="Login Failed",
                message="The email address or password you entered is incorrect.",
                name=None,
                email=None,
                button_text="Try Again",
                button_url="/login"
            )

        # ------------------------------------------
        # CREATE LOGIN SESSION
        # ------------------------------------------

        session.pop("driver_id", None)
        session.pop("driver_name", None)
        session.pop("driver_email", None)
        session.pop("admin_id", None)
        session.pop("admin_name", None)
        session.pop("admin_email", None)
        session["owner_id"] = owner["id"]
        session["owner_name"] = owner["name"]
        session["owner_email"] = owner["email"]

        # ------------------------------------------
        # LOGIN SUCCESS
        # ------------------------------------------

        return render_template(
            "auth_message.html",
            title="Login Successful!",
            message="You are now logged in to EVEase.",
            name=owner["name"],
            email=owner["email"],
            button_text="Go to Dashboard",
            button_url="/dashboard"
        )

    except mysql.connector.Error as error:

        return f"""
        <h1>Login Failed</h1>
        <p>Something went wrong while logging in.</p>
        <p>Error: {error}</p>
        """

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# OWNER DASHBOARD
# ==========================================

@app.route("/dashboard")
def dashboard():

    if "owner_id" not in session:
        return redirect("/login")

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ------------------------------------------
        # GET OWNER'S VEHICLES
        # ------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                vehicle_number,
                brand,
                model,
                vehicle_type,
                year,
                battery_capacity
            FROM vehicles
            WHERE owner_id = %s
            ORDER BY created_at DESC
            """,
            (session["owner_id"],)
        )

        vehicles = cursor.fetchall()

        vehicle_count = len(vehicles)

        # ------------------------------------------
        # TOTAL BOOKING COUNT
        # ------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS total_bookings
            FROM bookings
            WHERE owner_id = %s
            """,
            (session["owner_id"],)
        )

        booking_count = cursor.fetchone()["total_bookings"]

        # ------------------------------------------
        # PENDING BOOKING COUNT
        # ------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS pending_bookings
            FROM bookings
            WHERE owner_id = %s
              AND status = 'Pending'
            """,
            (session["owner_id"],)
        )

        pending_count = cursor.fetchone()["pending_bookings"]

        # ------------------------------------------
        # PENDING PAYMENT COUNT
        # ------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS pending_payments
            FROM bookings
            WHERE owner_id = %s
              AND status = 'Payment Pending'
            """,
            (session["owner_id"],)
        )

        pending_payment_count = cursor.fetchone()["pending_payments"]

        # ------------------------------------------
        # GET RECENT BOOKINGS
        # ------------------------------------------

        cursor.execute(
            """
            SELECT
                b.id,
                b.booking_reference,
                b.service_type,
                b.preferred_date,
                b.preferred_time,
                b.status,
                b.created_at,
                v.vehicle_number,
                v.brand,
                v.model
            FROM bookings b
            INNER JOIN vehicles v
                ON b.vehicle_id = v.id
            WHERE b.owner_id = %s
            ORDER BY b.created_at DESC
            LIMIT 3
            """,
            (session["owner_id"],)
        )

        recent_bookings = cursor.fetchall()

        # ------------------------------------------
        # RENDER DASHBOARD
        # ------------------------------------------

        return render_template(
            "dashboard.html",
            owner_name=session.get(
                "owner_name",
                "Owner"
            ),
            vehicles=vehicles,
            vehicle_count=vehicle_count,
            booking_count=booking_count,
            pending_count=pending_count,
            pending_payment_count=pending_payment_count,
            recent_bookings=recent_bookings
        )

    except mysql.connector.Error as error:

        return f"""
        <h1>Dashboard Error</h1>
        <p>Something went wrong while loading your dashboard.</p>
        <p>Error: {error}</p>
        """

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# ADD VEHICLE
# ==========================================

@app.route("/add-vehicle", methods=["GET", "POST"])
def add_vehicle():

    if "owner_id" not in session:
        return redirect("/login")

    if request.method == "GET":
        return render_template("add_vehicle.html")

    vehicle_number = request.form.get(
        "vehicle_number", ""
    ).strip().upper()

    brand = request.form.get(
        "brand", ""
    ).strip()

    model = request.form.get(
        "model", ""
    ).strip()

    vehicle_type = request.form.get(
        "vehicle_type", ""
    ).strip()

    year = request.form.get(
        "year", ""
    ).strip()

    battery_capacity = request.form.get(
        "battery_capacity", ""
    ).strip()

    # ------------------------------------------
    # VALIDATION
    # ------------------------------------------

    if not vehicle_number or not brand or not model or not vehicle_type:
        return "Please fill in all required vehicle details."

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO vehicles
            (
                owner_id,
                vehicle_number,
                brand,
                model,
                vehicle_type,
                year,
                battery_capacity
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                session["owner_id"],
                vehicle_number,
                brand,
                model,
                vehicle_type,
                int(year) if year else None,
                battery_capacity if battery_capacity else None
            )
        )

        connection.commit()

        return redirect("/dashboard")

    except (mysql.connector.Error, ValueError) as error:

        if connection:
            connection.rollback()

        return f"""
        <h1>Vehicle Registration Failed</h1>
        <p>Something went wrong while adding your vehicle.</p>
        <p>Error: {error}</p>
        <p><a href="/add-vehicle">Try Again</a></p>
        """

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# EDIT VEHICLE
# ==========================================

@app.route("/edit-vehicle/<int:vehicle_id>", methods=["GET", "POST"])
def edit_vehicle(vehicle_id):

    if "owner_id" not in session:
        return redirect("/login")

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Get only the vehicle belonging to the logged-in owner
        cursor.execute(
            """
            SELECT
                id,
                vehicle_number,
                brand,
                model,
                vehicle_type,
                year,
                battery_capacity
            FROM vehicles
            WHERE id = %s
              AND owner_id = %s
            """,
            (
                vehicle_id,
                session["owner_id"]
            )
        )

        vehicle = cursor.fetchone()

        if not vehicle:
            return "Vehicle not found."

        # ------------------------------------------
        # DISPLAY EDIT FORM
        # ------------------------------------------

        if request.method == "GET":

            return render_template(
                "edit_vehicle.html",
                vehicle=vehicle
            )

        # ------------------------------------------
        # GET UPDATED VALUES
        # ------------------------------------------

        vehicle_number = request.form.get(
            "vehicle_number", ""
        ).strip().upper()

        brand = request.form.get(
            "brand", ""
        ).strip()

        model = request.form.get(
            "model", ""
        ).strip()

        vehicle_type = request.form.get(
            "vehicle_type", ""
        ).strip()

        year = request.form.get(
            "year", ""
        ).strip()

        battery_capacity = request.form.get(
            "battery_capacity", ""
        ).strip()

        if not vehicle_number or not brand or not model or not vehicle_type:
            return "Please fill in all required vehicle details."

        # ------------------------------------------
        # UPDATE VEHICLE
        # ------------------------------------------

        cursor.execute(
            """
            UPDATE vehicles
            SET
                vehicle_number = %s,
                brand = %s,
                model = %s,
                vehicle_type = %s,
                year = %s,
                battery_capacity = %s
            WHERE id = %s
              AND owner_id = %s
            """,
            (
                vehicle_number,
                brand,
                model,
                vehicle_type,
                int(year) if year else None,
                battery_capacity if battery_capacity else None,
                vehicle_id,
                session["owner_id"]
            )
        )

        connection.commit()

        return redirect("/my-vehicles")

    except (mysql.connector.Error, ValueError) as error:

        if connection:
            connection.rollback()

        return f"""
        <h1>Vehicle Update Failed</h1>
        <p>Something went wrong while updating your vehicle.</p>
        <p>Error: {error}</p>
        <p><a href="/my-vehicles">Back to My Vehicles</a></p>
        """

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# DELETE VEHICLE
# ==========================================

@app.route("/delete-vehicle/<int:vehicle_id>", methods=["POST"])
def delete_vehicle(vehicle_id):

    if "owner_id" not in session:
        return redirect("/login")

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        # Delete only the vehicle belonging to the logged-in owner
        cursor.execute(
            """
            DELETE FROM vehicles
            WHERE id = %s
              AND owner_id = %s
            """,
            (
                vehicle_id,
                session["owner_id"]
            )
        )

        connection.commit()

        return redirect("/my-vehicles")

    except mysql.connector.Error as error:

        if connection:
            connection.rollback()

        return f"""
        <h1>Vehicle Deletion Failed</h1>
        <p>Something went wrong while deleting your vehicle.</p>
        <p><a href="/my-vehicles">Back to My Vehicles</a></p>
        """

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# MY VEHICLES
# ==========================================

@app.route("/my-vehicles")
def my_vehicles():

    if "owner_id" not in session:
        return redirect("/login")

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                vehicle_number,
                brand,
                model,
                vehicle_type,
                year,
                battery_capacity,
                created_at
            FROM vehicles
            WHERE owner_id = %s
            ORDER BY created_at DESC
            """,
            (session["owner_id"],)
        )

        vehicles = cursor.fetchall()

        return render_template(
            "my_vehicles.html",
            vehicles=vehicles
        )

    except mysql.connector.Error as error:

        return f"""
        <h1>Vehicles Error</h1>
        <p>Something went wrong while loading your vehicles.</p>
        <p>Error: {error}</p>
        """

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# BOOK A SERVICE
# ==========================================

@app.route("/book-service")
def book_service():

    if "owner_id" not in session:
        return redirect("/login")

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ------------------------------------------
        # LOAD ONLY THE LOGGED-IN OWNER'S VEHICLES
        # ------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                vehicle_number,
                brand,
                model,
                vehicle_type
            FROM vehicles
            WHERE owner_id = %s
            ORDER BY created_at DESC
            """,
            (session["owner_id"],)
        )

        vehicles = cursor.fetchall()

        return render_template(
            "book_service.html",
            vehicles=vehicles
        )

    except mysql.connector.Error as error:

        return f"""
        <h1>Booking Error</h1>
        <p>Something went wrong while loading your vehicles.</p>
        <p>Error: {error}</p>
        """

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# CREATE BOOKING
# ==========================================

@app.route("/create-booking", methods=["POST"])
def create_booking():

    if "owner_id" not in session:
        return redirect("/login")

    vehicle_id = request.form.get(
        "vehicle_id",
        ""
    ).strip()

    service_type = request.form.get(
        "service_type",
        ""
    ).strip()

    preferred_date = request.form.get(
        "preferred_date",
        ""
    ).strip()

    preferred_time = request.form.get(
        "preferred_time",
        ""
    ).strip()

    pickup_address = request.form.get(
        "pickup_address",
        ""
    ).strip()

    pickup_instructions = request.form.get(
        "pickup_instructions",
        ""
    ).strip()

    # ------------------------------------------
    # BASIC VALIDATION
    # ------------------------------------------

    if not vehicle_id or not service_type or not preferred_date:
        return "Please complete all required booking details."

    if not preferred_time:
        return "Please select a preferred time."

    if not pickup_address:
        return "Pickup address is required."

    # ------------------------------------------
    # ALLOWED SERVICES
    # ------------------------------------------

    allowed_services = [
        "General Service",
        "Battery Check"
    ]

    if service_type not in allowed_services:
        return "Invalid service type."

    # ------------------------------------------
    # ALLOWED TIME SLOTS
    # ------------------------------------------

    allowed_times = [
        "09:00 AM",
        "10:00 AM",
        "11:00 AM",
        "12:00 PM",
        "02:00 PM",
        "03:00 PM",
        "04:00 PM",
        "05:00 PM"
    ]

    if preferred_time not in allowed_times:
        return "Invalid preferred time."

    # ------------------------------------------
    # DATE VALIDATION
    # ------------------------------------------

    from datetime import datetime, date

    try:

        selected_date = datetime.strptime(
            preferred_date,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return "Invalid preferred date."

    if selected_date < date.today():
        return "Preferred date cannot be in the past."

    # ------------------------------------------
    # DATABASE
    # ------------------------------------------

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # --------------------------------------
        # VERIFY VEHICLE BELONGS TO OWNER
        # --------------------------------------

        cursor.execute(
            """
            SELECT id
            FROM vehicles
            WHERE id = %s
              AND owner_id = %s
            """,
            (
                vehicle_id,
                session["owner_id"]
            )
        )

        vehicle = cursor.fetchone()

        if not vehicle:
            return "Invalid vehicle selected."

        # --------------------------------------
        # CREATE TEMPORARY UNIQUE REFERENCE
        # --------------------------------------

        import uuid

        temporary_reference = (
            "TEMP-" + uuid.uuid4().hex[:20]
        )

        # --------------------------------------
        # INSERT BOOKING
        # --------------------------------------

        cursor.execute(
            """
            INSERT INTO bookings
            (
                booking_reference,
                owner_id,
                vehicle_id,
                service_type,
                preferred_date,
                preferred_time,
                pickup_address,
                pickup_instructions,
                status,
                final_amount
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                temporary_reference,
                session["owner_id"],
                vehicle_id,
                service_type,
                selected_date,
                preferred_time,
                pickup_address,
                pickup_instructions
                if pickup_instructions
                else None,
                "Pending",
                None
            )
        )

        booking_id = cursor.lastrowid

        # --------------------------------------
        # GENERATE FINAL BOOKING REFERENCE
        # --------------------------------------

        booking_reference = (
            f"EV-{selected_date.strftime('%Y%m%d')}-{booking_id:05d}"
        )

        cursor.execute(
            """
            UPDATE bookings
            SET booking_reference = %s
            WHERE id = %s
            """,
            (
                booking_reference,
                booking_id
            )
        )

        connection.commit()

        # --------------------------------------
        # LOAD CREATED BOOKING
        # --------------------------------------

        cursor.execute(
            """
            SELECT
                b.id,
                b.booking_reference,
                b.service_type,
                b.preferred_date,
                b.preferred_time,
                b.status,
                v.vehicle_number,
                v.brand,
                v.model
            FROM bookings b
            INNER JOIN vehicles v
                ON b.vehicle_id = v.id
            WHERE b.id = %s
              AND b.owner_id = %s
            """,
            (
                booking_id,
                session["owner_id"]
            )
        )

        booking = cursor.fetchone()

        # --------------------------------------
        # BOOKING CONFIRMATION
        # --------------------------------------

        return render_template(
            "booking_confirmation.html",
            booking=booking
        )

    except mysql.connector.Error as error:

        if connection:
            connection.rollback()

        return f"""
        <h1>Booking Failed</h1>

        <p>
            Something went wrong while creating your booking.
        </p>

        <p>
            Error: {error}
        </p>
        """

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# MY BOOKINGS
# ==========================================

@app.route("/my-bookings")
def my_bookings():

    if "owner_id" not in session:
        return redirect("/login")

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                b.id,
                b.booking_reference,
                b.service_type,
                b.preferred_date,
                b.preferred_time,
                b.status,
                b.created_at,
                v.vehicle_number,
                v.brand,
                v.model
            FROM bookings b
            INNER JOIN vehicles v
                ON b.vehicle_id = v.id
            WHERE b.owner_id = %s
            ORDER BY b.created_at DESC
            """,
            (session["owner_id"],)
        )

        bookings = cursor.fetchall()

        return render_template(
            "my_bookings.html",
            bookings=bookings
        )

    except mysql.connector.Error as error:

        return f"""
        <h1>My Bookings Error</h1>
        <p>Something went wrong while loading your bookings.</p>
        <p>Error: {error}</p>
        """

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# DRIVER LOGIN
# ==========================================

@app.route("/driver-login", methods=["GET", "POST"])
def driver_login():

    if "owner_id" in session:
        return redirect("/dashboard")

    if "admin_id" in session:
        return redirect("/admin-dashboard")

    if request.method == "GET":
        return render_template("driver_login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template(
            "auth_message.html",
            title="Driver Login Failed",
            message="Please enter your email and password.",
            name=None,
            email=None,
            button_text="Try Again",
            button_url="/driver-login"
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, name, email, password
            FROM drivers
            WHERE email = %s
              AND status = 'Active'
            """,
            (email,)
        )

        driver = cursor.fetchone()

        if not driver or not check_password_hash(driver["password"], password):
            return render_template(
                "auth_message.html",
                title="Driver Login Failed",
                message="The email address or password you entered is incorrect.",
                name=None,
                email=None,
                button_text="Try Again",
                button_url="/driver-login"
            )

        session.pop("owner_id", None)
        session.pop("owner_name", None)
        session.pop("owner_email", None)
        session.pop("admin_id", None)
        session.pop("admin_name", None)
        session.pop("admin_email", None)
        session["driver_id"] = driver["id"]
        session["driver_name"] = driver["name"]
        session["driver_email"] = driver["email"]

        return redirect("/driver-dashboard")

    except mysql.connector.Error as error:
        return f"""
        <h1>Driver Login Failed</h1>
        <p>Something went wrong while logging in.</p>
        <p>Error: {error}</p>
        """

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# DRIVER DASHBOARD
# ==========================================

@app.route("/driver-dashboard")
def driver_dashboard():

    if "owner_id" in session:
        return redirect("/dashboard")

    if "driver_id" not in session:
        return redirect("/driver-login")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                b.id,
                b.booking_reference,
                b.service_type,
                b.preferred_date,
                b.preferred_time,
                b.pickup_address,
                b.pickup_instructions,
                b.status,
                o.name AS owner_name,
                v.vehicle_number,
                v.brand,
                v.model,
                v.vehicle_type
            FROM bookings b
            INNER JOIN owners o ON b.owner_id = o.id
            INNER JOIN vehicles v ON b.vehicle_id = v.id
            WHERE b.driver_id = %s
            ORDER BY b.preferred_date ASC, b.preferred_time ASC
            """,
            (session["driver_id"],)
        )

        bookings = cursor.fetchall()
        assigned_count = len(bookings)
        pending_pickup_count = sum(
            booking["status"] == "Driver Assigned" for booking in bookings
        )
        delivered_count = sum(
            booking["status"] == "Delivered" for booking in bookings
        )

        return render_template(
            "driver_dashboard.html",
            driver_name=session.get("driver_name", "Driver"),
            bookings=bookings,
            assigned_count=assigned_count,
            pending_pickup_count=pending_pickup_count,
            delivered_count=delivered_count
        )

    except mysql.connector.Error as error:
        return f"""
        <h1>Driver Dashboard Error</h1>
        <p>Something went wrong while loading assigned requests.</p>
        <p>Error: {error}</p>
        """

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# DRIVER BOOKING STATUS UPDATE
# ==========================================

@app.route("/driver/update-status/<int:booking_id>", methods=["POST"])
def driver_update_status(booking_id):

    if "owner_id" in session:
        return redirect("/dashboard")

    if "driver_id" not in session:
        return redirect("/driver-login")

    requested_status = request.form.get("status", "").strip()
    allowed_transitions = {
        "Driver Assigned": "Picked Up",
        "Out for Delivery": "Delivered"
    }

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, status
            FROM bookings
            WHERE id = %s
              AND driver_id = %s
            """,
            (booking_id, session["driver_id"])
        )

        booking = cursor.fetchone()

        if not booking:
            return "Booking not found or not assigned to you.", 403

        expected_status = allowed_transitions.get(booking["status"])

        if not expected_status or requested_status != expected_status:
            return "Invalid booking status transition.", 400

        cursor.execute(
            """
            UPDATE bookings
            SET status = %s
            WHERE id = %s
              AND driver_id = %s
              AND status = %s
            """,
            (
                requested_status,
                booking_id,
                session["driver_id"],
                booking["status"]
            )
        )

        if cursor.rowcount != 1:
            connection.rollback()
            return "Booking status could not be updated.", 409

        connection.commit()
        return redirect("/driver-dashboard")

    except mysql.connector.Error as error:
        if connection:
            connection.rollback()

        return f"""
        <h1>Booking Update Failed</h1>
        <p>Something went wrong while updating the booking.</p>
        <p>Error: {error}</p>
        """

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# DRIVER LOGOUT
# ==========================================

@app.route("/driver-logout")
def driver_logout():

    session.clear()
    return redirect("/driver-login")


# ==========================================
# ADMIN LOGIN
# ==========================================

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if "owner_id" in session:
        return redirect("/dashboard")

    if "driver_id" in session:
        return redirect("/driver-dashboard")

    if request.method == "GET":
        return render_template("admin_login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template(
            "auth_message.html",
            title="Admin Login Failed",
            message="Please enter your email and password.",
            name=None,
            email=None,
            button_text="Try Again",
            button_url="/admin-login"
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, name, email, password
            FROM admins
            WHERE email = %s
              AND status = 'Active'
            """,
            (email,)
        )

        admin = cursor.fetchone()

        if not admin or not check_password_hash(admin["password"], password):
            return render_template(
                "auth_message.html",
                title="Admin Login Failed",
                message="The email address or password you entered is incorrect.",
                name=None,
                email=None,
                button_text="Try Again",
                button_url="/admin-login"
            )

        session.pop("owner_id", None)
        session.pop("owner_name", None)
        session.pop("owner_email", None)
        session.pop("driver_id", None)
        session.pop("driver_name", None)
        session.pop("driver_email", None)
        session["admin_id"] = admin["id"]
        session["admin_name"] = admin["name"]
        session["admin_email"] = admin["email"]

        return redirect("/admin-dashboard")

    except mysql.connector.Error as error:
        return f"""
        <h1>Admin Login Failed</h1>
        <p>Something went wrong while logging in.</p>
        <p>Error: {error}</p>
        """

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# ADMIN DASHBOARD
# ==========================================

@app.route("/admin-dashboard")
def admin_dashboard():

    if "owner_id" in session:
        return redirect("/dashboard")

    if "driver_id" in session:
        return redirect("/driver-dashboard")

    if "admin_id" not in session:
        return redirect("/admin-login")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                b.id,
                b.booking_reference,
                b.service_type,
                b.preferred_date,
                b.preferred_time,
                b.pickup_address,
                b.pickup_instructions,
                o.name AS owner_name,
                o.phone AS owner_phone,
                v.vehicle_number,
                v.brand,
                v.model,
                v.vehicle_type
            FROM bookings b
            INNER JOIN owners o ON b.owner_id = o.id
            INNER JOIN vehicles v ON b.vehicle_id = v.id
            WHERE b.status = 'Pending'
              AND b.driver_id IS NULL
            ORDER BY b.created_at ASC
            """
        )

        pending_bookings = cursor.fetchall()

        cursor.execute(
            """
            SELECT id, name, email, phone, license_no
            FROM drivers
            WHERE status = 'Active'
            ORDER BY name ASC
            """
        )

        active_drivers = cursor.fetchall()

        cursor.execute(
            """
            SELECT COUNT(*) AS assigned_bookings
            FROM bookings
            WHERE status = 'Driver Assigned'
            """
        )

        assigned_count = cursor.fetchone()["assigned_bookings"]

        return render_template(
            "admin_dashboard.html",
            admin_name=session.get("admin_name", "Admin"),
            pending_bookings=pending_bookings,
            active_drivers=active_drivers,
            pending_count=len(pending_bookings),
            assigned_count=assigned_count
        )

    except mysql.connector.Error as error:
        return f"""
        <h1>Admin Dashboard Error</h1>
        <p>Something went wrong while loading booking assignments.</p>
        <p>Error: {error}</p>
        """

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# ADMIN DRIVER ASSIGNMENT
# ==========================================

@app.route("/admin/assign-driver/<int:booking_id>", methods=["POST"])
def admin_assign_driver(booking_id):

    if "owner_id" in session:
        return redirect("/dashboard")

    if "driver_id" in session:
        return redirect("/driver-dashboard")

    if "admin_id" not in session:
        return redirect("/admin-login")

    driver_id = request.form.get("driver_id", "").strip()

    if not driver_id.isdigit():
        return "Please select a valid active driver.", 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id
            FROM bookings
            WHERE id = %s
              AND status = 'Pending'
              AND driver_id IS NULL
            """,
            (booking_id,)
        )

        booking = cursor.fetchone()

        if not booking:
            return "Booking is not available for driver assignment.", 400

        cursor.execute(
            """
            SELECT id
            FROM drivers
            WHERE id = %s
              AND status = 'Active'
            """,
            (driver_id,)
        )

        driver = cursor.fetchone()

        if not driver:
            return "Selected driver is not available.", 400

        cursor.execute(
            """
            UPDATE bookings
            SET driver_id = %s,
                status = 'Driver Assigned'
            WHERE id = %s
              AND status = 'Pending'
              AND driver_id IS NULL
            """,
            (driver_id, booking_id)
        )

        if cursor.rowcount != 1:
            connection.rollback()
            return "Booking could not be assigned.", 409

        connection.commit()
        return redirect("/admin-dashboard")

    except mysql.connector.Error as error:
        if connection:
            connection.rollback()

        return f"""
        <h1>Driver Assignment Failed</h1>
        <p>Something went wrong while assigning the driver.</p>
        <p>Error: {error}</p>
        """

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# ADMIN LOGOUT
# ==========================================

@app.route("/admin-logout")
def admin_logout():

    session.clear()
    return redirect("/admin-login")


# ==========================================
# OWNER LOGOUT
# ==========================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ==========================================
# START FLASK APPLICATION
# ==========================================

if __name__ == "__main__":
    app.run(debug=True)
