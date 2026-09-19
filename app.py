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
        cursor = connection.cursor()

        # ------------------------------------------
        # COUNT OWNER VEHICLES
        # ------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM vehicles
            WHERE owner_id = %s
            """,
            (session["owner_id"],)
        )

        vehicle_count = cursor.fetchone()[0]

        # ------------------------------------------
        # DASHBOARD
        # ------------------------------------------

        return render_template(
            "dashboard.html",
            owner_name=session.get("owner_name", "Owner"),
            vehicle_count=vehicle_count,
            booking_count=0,
            pending_count=0,
            pending_payment_count=0,
            recent_bookings=[]
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
        <p>Error: {error}</p>
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