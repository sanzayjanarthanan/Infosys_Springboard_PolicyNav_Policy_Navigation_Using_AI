import streamlit as st
import jwt
import datetime
import re
import sqlite3
import os
import random
import smtplib
from email.message import EmailMessage
import time
import bcrypt
import PyPDF2
import io
from streamlit_option_menu import option_menu
import streamlit as st
import plotly.graph_objects as go
from readability_utils import ReadabilityAnalyzer
from google.colab import userdata


JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
EMAIL_ID = os.getenv("EMAIL_ID")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
ADMIN_EMAIL_ID = os.getenv("ADMIN_EMAIL_ID")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY not set")

if "pending_signup" not in st.session_state:
    st.session_state["pending_signup"] = None

if not EMAIL_ID or not EMAIL_APP_PASSWORD:
    raise RuntimeError("Email credentials not set. OTP email cannot be sent.")

if 'page' not in st.session_state:
    st.session_state['page'] = 'login'

# --- Configuration ---
SECRET_KEY = JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --- SQLite Configuration ---
def get_db_connection():
    conn = sqlite3.connect("policynav.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            security_question TEXT NOT NULL,
            security_answer TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT DEFAULT NULL,
            failed_attempts INTEGER DEFAULT 0,
            lock_until REAL DEFAULT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            password TEXT NOT NULL,
            changed_at REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS otp_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            otp_hash TEXT NOT NULL,
            expires_at REAL NOT NULL,
            attempts INTEGER DEFAULT 0,
            created_at REAL NOT NULL
        )
    ''')


    conn.commit()
    conn.close()

init_db()


## --- AUTH HELPERS ---
# --- Password Hashing Utils ---
def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode(),
        bcrypt.gensalt(rounds=12)  # explicit cost factor
    ).decode()

def ensure_admin_exists():
    if not ADMIN_EMAIL_ID or not ADMIN_PASSWORD:
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email = ?", (ADMIN_EMAIL_ID,))
    admin = cursor.fetchone()

    if not admin:
        hashed_password = hash_password(ADMIN_PASSWORD)

        cursor.execute('''
            INSERT INTO users (email, username, password,
                               security_question, security_answer, role)
            VALUES (?, ?, ?, ?, ?, 'admin')
        ''', (
            ADMIN_EMAIL_ID,
            "admin",
            hashed_password,
            "System Generated",
            "admin"
        ))

        conn.commit()

    conn.close()

ensure_admin_exists()

# --- OTP Management (Milestone 2) ---
def otp_verify_page():

    if "otp_email" not in st.session_state:
      st.error("OTP session expired. Please login/signup again.")
      st.session_state["page"] = "login"
      st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 3, 2])

    with col2:
        st.markdown(
            "<h2 style='text-align:center;color:#38bdf8;'>OTP Verification</h2>",
            unsafe_allow_html=True
        )

        st.markdown(
            "<p style='text-align:center;color:#94a3b8;'>"
            "Enter the 6-digit OTP sent to your email</p>",
            unsafe_allow_html=True
        )

        record = get_otp(st.session_state.get("otp_email"))

        if not record:
            st.error("OTP not found. Please request a new OTP.")
            st.stop()

        # Block after too many attempts
        if record["attempts"] >= 5:
            delete_otp(st.session_state["otp_email"])

            st.error("Too many incorrect attempts. OTP blocked. Redirecting to login...")

            # Clean OTP-related session state
            st.session_state.pop("otp_email", None)
            st.session_state.pop("otp_context", None)

            time.sleep(2)
            st.session_state["page"] = "login"
            st.rerun()

        with st.form("otp_verify_form"):
            entered_otp = st.text_input(
                "OTP",
                max_chars=6,
                placeholder="••••••"
            ).strip()

            verify = st.form_submit_button("Verify OTP")

        if verify:
            # Expiry check
            if time.time() > record["expires_at"]:
                delete_otp(st.session_state["otp_email"])
                st.error("OTP expired. Please request a new OTP.")
                st.stop()

            # Invalid OTP
            if not entered_otp.isdigit() or len(entered_otp) != 6:
                st.error("OTP must be a 6-digit number.")
                st.stop()

            if not bcrypt.checkpw(
                entered_otp.encode(),
                record["otp_hash"].encode()
            ):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE otp_codes SET attempts = attempts + 1 WHERE email = ?",
                    (st.session_state["otp_email"],)
                )
                conn.commit()
                conn.close()

                st.error("Invalid OTP")
                st.stop()

            # OTP VERIFIED SUCCESSFULLY
            delete_otp(st.session_state["otp_email"])

            if st.session_state.get("otp_context") == "forgot":
                reset_token = create_access_token({
                    "email": st.session_state["otp_email"],
                    "purpose": "password_reset"
                })

                st.session_state["reset_token"] = reset_token
                st.session_state.pop("otp_email", None)
                st.session_state.pop("otp_context", None)

                st.session_state["page"] = "reset"
                st.rerun()


def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp(email, otp):
    msg = EmailMessage()

    # ---- SUBJECT ----
    msg["Subject"] = "🔐 PolicyNav OTP Verification"
    msg["From"] = EMAIL_ID
    msg["To"] = email

    # ---- HTML EMAIL BODY ----
    html_content = f'''
    <html>
    <body style="
        margin:0;
        padding:0;
        background-color:#020617;
        font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
    ">
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td align="center" style="padding:40px 0;">
                    <table width="520" cellpadding="0" cellspacing="0" style="
                        background:#0f172a;
                        border-radius:16px;
                        padding:32px;
                        box-shadow:0 20px 40px rgba(0,0,0,0.6);
                    ">

                        <!-- HEADER -->
                        <tr>
                            <td align="center" style="padding-bottom:12px;">
                                <h1 style="
                                    margin:0;
                                    font-size:28px;
                                    font-weight:800;
                                    background:linear-gradient(90deg,#38bdf8,#6366f1,#22d3ee);
                                    -webkit-background-clip:text;
                                    -webkit-text-fill-color:transparent;
                                ">
                                    PolicyNav
                                </h1>
                            </td>
                        </tr>

                        <tr>
                            <td align="center" style="padding-bottom:24px;">
                                <p style="
                                    margin:0;
                                    color:#94a3b8;
                                    font-size:15px;
                                ">
                                    Secure OTP Verification
                                </p>
                            </td>
                        </tr>

                        <!-- OTP BOX -->
                        <tr>
                            <td align="center" style="padding:24px 0;">
                                <div style="
                                    display:inline-block;
                                    padding:18px 36px;
                                    font-size:32px;
                                    letter-spacing:6px;
                                    font-weight:700;
                                    color:#ffffff;
                                    background:linear-gradient(135deg,#38bdf8,#6366f1);
                                    border-radius:12px;
                                ">
                                    {otp}
                                </div>
                            </td>
                        </tr>

                        <!-- INFO -->
                        <tr>
                            <td align="center" style="padding-top:12px;">
                                <p style="
                                    margin:0;
                                    color:#e5e7eb;
                                    font-size:14px;
                                ">
                                    This OTP is valid for <b>2 minutes</b>.
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <td align="center" style="padding-top:8px;">
                                <p style="
                                    margin:0;
                                    color:#94a3b8;
                                    font-size:13px;
                                ">
                                    If you didn’t request this, please ignore this email.
                                </p>
                            </td>
                        </tr>

                        <!-- FOOTER -->
                        <tr>
                            <td align="center" style="padding-top:32px;">
                                <p style="
                                    margin:0;
                                    font-size:12px;
                                    color:#64748b;
                                ">
                                    © {datetime.datetime.utcnow().year} PolicyNav · AI Public Policy Assistant
                                </p>
                            </td>
                        </tr>

                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    '''

    msg.set_content("Your PolicyNav OTP is: " + otp)  # fallback
    msg.add_alternative(html_content, subtype="html")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ID, EMAIL_APP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        st.error("Failed to send OTP email. Please try again.")
        print("SMTP Error:", e)
        return False

    return True


def initiate_otp(email):
    user = get_user_by_email(email)
    if not user and st.session_state.get("otp_context") == "login":
        st.error("Email not registered")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # Rate limit: allow OTP only once per 30 seconds
    cursor.execute(
        "SELECT created_at FROM otp_codes WHERE email = ?",
        (email,)
    )
    existing = cursor.fetchone()

    if existing and time.time() - existing["created_at"] < 30:
        conn.close()
        st.warning("Please wait 30 seconds before requesting another OTP.")
        return

    # Generate OTP
    otp = generate_otp()
    otp_hash = bcrypt.hashpw(otp.encode(), bcrypt.gensalt()).decode()
    created_at = time.time()
    expires_at = created_at + 120  # 2 minutes

    # Remove old OTPs
    cursor.execute("DELETE FROM otp_codes WHERE email = ?", (email,))

    #Store new OTP
    cursor.execute('''
        INSERT INTO otp_codes (email, otp_hash, expires_at, created_at)
        VALUES (?, ?, ?, ?)
    ''', (email, otp_hash, expires_at, created_at))

    conn.commit()
    conn.close()

    #Send OTP
    success = send_otp(email, otp)

    if not success:
        delete_otp(email)
        st.stop()  # prevents OTP verification from continuing

def get_otp(email):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT otp_hash, expires_at, attempts FROM otp_codes
        WHERE email = ?
    ''', (email,))

    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_otp(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM otp_codes WHERE email = ?", (email,))
    conn.commit()
    conn.close()

def update_last_login(email):
    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET last_login=? WHERE email=?",
        (datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), email)
    )
    conn.commit()
    conn.close()

def get_user_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def increment_failed_attempts(email):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE users
        SET failed_attempts = failed_attempts + 1
        WHERE email = ?
    ''', (email,))

    conn.commit()
    conn.close()


def reset_failed_attempts(email):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE users
        SET failed_attempts = 0, lock_until = NULL
        WHERE email = ?
    ''', (email,))

    conn.commit()
    conn.close()


def lock_account(email, minutes=5):
    lock_time = time.time() + (minutes * 60)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE users
        SET lock_until = ?
        WHERE email = ?
    ''', (lock_time, email))

    conn.commit()
    conn.close()

def get_user_by_username(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None


def create_user(user_data):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        hashed_password = hash_password(user_data["password"])
        cursor.execute('''
            INSERT INTO users (email, username, password, security_question, security_answer)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            user_data["email"],
            user_data["username"],
            hashed_password,
            user_data["security_question"],
            user_data["security_answer"]
        ))

        user_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO password_history (user_id, password, changed_at)
            VALUES (?, ?, ?)
        ''', (user_id, hashed_password, time.time()))

        conn.commit()

    except sqlite3.IntegrityError:
        conn.close()
        return False

    conn.close()
    return True

def is_password_reused(user_id, new_password):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT password FROM password_history
        WHERE user_id = ?
    ''', (user_id,))

    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        if verify_password(new_password, row["password"]):
            return True
    return False


def update_password(email, new_password):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return False

    user_id = user["id"]

    hashed_password = hash_password(new_password)

    # Update users table
    cursor.execute(
        "UPDATE users SET password = ? WHERE email = ?",
        (hashed_password, email)
    )

    # Insert into password history
    cursor.execute('''
        INSERT INTO password_history (user_id, password, changed_at)
        VALUES (?, ?, ?)
    ''', (user_id, hashed_password, time.time()))

    conn.commit()
    conn.close()
    return True




# --- JWT Utils ---
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "exp": expire,
        "iat": datetime.datetime.utcnow(),
        "iss": "PolicyNav",
        "aud": "PolicyNavUsers"
    })
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
def verify_token(token: str):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            audience="PolicyNavUsers",
            issuer="PolicyNav"
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_admin():
    token = st.session_state.get("jwt_token")
    payload = verify_token(token)

    if not payload or payload.get("role") != "admin":
        st.error("Unauthorized access")
        st.stop()


# --- Format timestamps safely ---
def format_timestamp(ts):
    if ts:
        try:
            # Convert string to datetime if needed
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)  # works for "YYYY-MM-DD HH:MM:SS" format
            return ts.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return ts  # fallback: just show raw string
    return "-"

# --- Validation Utils ---



def password_strength(password):
    # Block special characters visually
    if not password.isalnum():
        return 0

    score = 0

    if len(password) >= 8:
        score += 25
    if re.search(r"[A-Z]", password):
        score += 25
    if re.search(r"[a-z]", password):
        score += 25
    if re.search(r"[0-9]", password):
        score += 25

    return score


def check_password_strength(password: str):
    feedback = []

    if not password.isalnum():
        feedback.append("Password must contain only letters and numbers (no special characters).")

    if len(password) < 8:
        feedback.append("At least 8 characters")

    if not re.search(r"[A-Z]", password):
        feedback.append("At least one uppercase letter")

    if not re.search(r"[a-z]", password):
        feedback.append("At least one lowercase letter")

    if not re.search(r"[0-9]", password):
        feedback.append("At least one number")

    if feedback:
        return False, "Weak", feedback

    return True, "Strong", []



def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode(),
        hashed_password.encode()
    )

def is_valid_email(email):
    # Regex for standard email format
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    try:
        if re.match(pattern, email):
            return True
    except:
        return False
    return False

def logout():
    st.session_state.clear()
    st.session_state["page"] = "login"
    st.rerun()

# ---------- Readability Utilities ----------
def readability_metrics(text):
    sentences = max(1, text.count("."))
    words = len(text.split())
    avg_sentence_length = words / sentences

    # Simple Flesch-style heuristic (safe for exam)
    score = 206.835 - (1.015 * avg_sentence_length)

    return {
        "sentences": sentences,
        "words": words,
        "avg_sentence_length": round(avg_sentence_length, 2),
        "score": round(score, 2)
    }

# --- Session State Management ---
if 'jwt_token' not in st.session_state:
    st.session_state['jwt_token'] = None
if 'page' not in st.session_state:
    st.session_state['page'] = 'login'

# --- Styling ---
st.set_page_config(page_title="PolicyNav- AI Public Policy Assistant", page_icon="🤖", layout="wide")

st.markdown('''
    <style>
        /* ===== Global App ===== */
        .stApp {
            background: radial-gradient(circle at top, #0f172a 0%, #020617 60%);
            font-family: 'Inter', 'Segoe UI', sans-serif;
            color: #e5e7eb;
        }

        /* Remove Streamlit padding */
        .main > div {
            padding-top: 2rem;
        }

        /* ===== Headings ===== */
        h1 {
            text-align: center;
            color: #38bdf8;
            font-weight: 700;
            letter-spacing: 0.5px;
        }

        h4 {
            text-align: center;
            font-weight: 400;
        }

        /* ===== Buttons ===== */
        .stButton > button {
            width: 100%;
            height: 3em;
            border-radius: 10px;
            background: linear-gradient(135deg, #38bdf8, #6366f1);
            color: white;
            font-weight: 600;
            border: none;
            transition: all 0.25s ease;
        }

        /* Center buttons inside columns */
        div[data-testid="column"] > div:has(.stButton) {
            display: flex;
            justify-content: center;
        }


        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(99,102,241,0.4);
        }

        /* ===== Inputs ===== */
        input, textarea {
            border-radius: 8px !important;
            background-color: #020617 !important;
            color: #e5e7eb !important;
        }

        /* ===== Sidebar ===== */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #020617, #020617);
            border-right: 1px solid #1e293b;
        }

        section[data-testid="stSidebar"] h1 {
            color: #38bdf8;
        }

        /* ===== Chat Bubbles ===== */

          /* ===== Chat Bubbles ===== */

                  /* USER MESSAGE — Bright, active */
                  .user-msg {
                      text-align: right;
                      background: linear-gradient(135deg, #6366f1, #8b5cf6);
                      color: #ffffff;
                      padding: 12px 16px;
                      border-radius: 18px 18px 4px 18px;
                      margin: 10px 0;
                      display: inline-block;
                      max-width: 75%;
                      float: right;
                      clear: both;
                      font-size: 0.95rem;
                      box-shadow: 0 8px 26px rgba(99,102,241,0.45);
                      animation: fadeIn 0.25s ease-in;
                  }

                  /* BOT MESSAGE — Dark glass + cyan accent */
                  .bot-msg {
                      text-align: left;
                      background: rgba(15, 23, 42, 0.85);
                      backdrop-filter: blur(10px);
                      -webkit-backdrop-filter: blur(10px);
                      color: #e5e7eb;
                      padding: 12px 16px;
                      border-radius: 18px 18px 18px 4px;
                      margin: 10px 0;
                      display: inline-block;
                      max-width: 75%;
                      float: left;
                      clear: both;
                      font-size: 0.95rem;
                      border-left: 3px solid #38bdf8;
                      box-shadow: 0 10px 30px rgba(2,6,23,0.6);
                      animation: fadeIn 0.25s ease-in;
                  }



        /* ===== Animations ===== */
        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(6px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .welcome-container {
              text-align: center;
              margin-top: 20px;
              margin-bottom: 30px;
          }

          .welcome-text {
              font-family: 'Space Grotesk', 'Inter', sans-serif;
              font-size: 3rem;
              font-weight: 800;
              background: linear-gradient(90deg, #38bdf8, #6366f1, #22d3ee);
              -webkit-background-clip: text;
              -webkit-text-fill-color: transparent;
              letter-spacing: -1px;
          }

          .welcome-subtext {
              font-family: 'Inter', sans-serif;
              font-size: 1.1rem;
              color: #94a3b8;
              margin-top: 6px;
          }

        </style>
        ''', unsafe_allow_html=True)

# --- PAGES ---
def login_page():
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 3, 2])

    with col2:
        st.markdown(
            """
            <h1 style="
                text-align: center;
                font-size: 3rem;
                font-weight: 800;
                color: #2563eb;
                margin-bottom: 0.2em;
            ">
            PolicyNav – Public Policy Navigation Using AI
            </h1>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            "<h4 style='text-align:center; color:#94a3b8;'>Please sign in to continue</h4>",
            unsafe_allow_html=True
        )

        with st.form("login_form"):
            email = st.text_input("Email Address")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In")

            # ----- FORM SUBMISSION -----
            if submitted:
                # ----- FIELD VALIDATION -----
                if not email:
                    st.error("Email is required")
                    return
                if not is_valid_email(email):
                    st.error("Invalid email format (e.g. user@domain.com)")
                    return
                if not password:
                    st.error("Password is required")
                    return

                # ----- FETCH USER -----
                user = get_user_by_email(email)

                if not user:
                    st.error("No account found with this email")
                    return

                # 🔒 ----- ACCOUNT LOCK CHECK (CRITICAL FIX) -----
                if user.get("lock_until") and time.time() < user["lock_until"]:
                    remaining = int((user["lock_until"] - time.time()) / 60) + 1
                    st.error(f"Account locked. Try again in {remaining} minute(s).")
                    return

                # ----- PASSWORD VERIFICATION -----
                if not verify_password(password, user["password"]):
                    increment_failed_attempts(email)
                    user = get_user_by_email(email)  # refresh values

                    if user["failed_attempts"] >= 3:
                        lock_account(email)
                        st.error(
                            "Account locked due to 3 failed login attempts. "
                            "Try again after 5 minutes."
                        )
                    else:
                        remaining = 3 - user["failed_attempts"]
                        st.error(f"Incorrect password. {remaining} attempt(s) remaining.")
                    return

                # ✅ ----- SUCCESSFUL LOGIN -----
                reset_failed_attempts(email)
                update_last_login(email)

                token = create_access_token({
                    "sub": user["email"],
                    "username": user["username"],
                    "role": user["role"]
                })

                st.session_state["jwt_token"] = token
                st.success("Login successful!")
                time.sleep(0.5)

                # ----- ROLE-BASED REDIRECT -----
                if user.get("role") == "admin":
                    st.session_state["page"] = "admin_dashboard"
                else:
                    st.session_state["page"] = "dashboard"

                st.rerun()

        # ----- FOOTER ACTIONS -----
        st.markdown("---")
        c1, c2 = st.columns(2)

        with c1:
            if st.button("Forgot Password?", use_container_width=True):
                st.session_state["page"] = "forgot"
                st.rerun()

        with c2:
            if st.button("Create an Account", use_container_width=True):
                st.session_state["page"] = "signup"
                st.rerun()
                
def signup_page():
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 3, 2])

    with col2:
        st.title("Create Account")

        with st.form("signup_form"):
            username = st.text_input("Username (Required)").strip()
            email = st.text_input("Email Address (@domain.com required)").strip().lower()
            password = st.text_input(
                "Password",
                type="password",
                help="Minimum 8 chars, uppercase, lowercase, number"
            ).strip()


            if password:
                strength_percent = password_strength(password)  # returns 0–100

                st.progress(strength_percent / 100)

                if strength_percent < 40:
                    st.error("Weak password")
                elif strength_percent < 70:
                    st.warning("Moderate password")
                else:
                    st.success("Strong password")


            confirm_password = st.text_input("Confirm Password", type="password").strip()

            security_question = st.selectbox(
                "Security Question",
                [
                    "What is your pet name?",
                    "What is your college name?",
                    "Who is your favorite teacher?"
                ]
            )

            security_answer = st.text_input("Security Answer").strip()
            hashed_sa = bcrypt.hashpw(security_answer.lower().encode(), bcrypt.gensalt(rounds=12)).decode()
            submitted = st.form_submit_button("Sign Up")

            if submitted:
                errors = []

                # Username validation
                if not username:
                    errors.append("Username is mandatory.")
                elif get_user_by_username(username):
                    errors.append(f"Username '{username}' is already taken.")

                # Email validation
                if not email:
                    errors.append("Email is mandatory.")
                elif not is_valid_email(email):
                    errors.append("Invalid Email format (e.g. user@domain.com).")
                elif get_user_by_email(email):
                    errors.append(f"Email '{email}' is already registered.")

                # Password validation
                if not password:
                    errors.append("Password is mandatory.")

                is_valid, _, feedback = check_password_strength(password)

                if not is_valid:
                    errors.append("Password does not meet security requirements:")
                    for rule in feedback:
                        errors.append(f"• {rule}")


                # Confirm password
                if password != confirm_password:
                    errors.append("Passwords do not match.")



                # Security answer
                if not security_answer:
                    errors.append("Security answer is mandatory.")

                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    user_data = {
                        "username": username,
                        "email": email,
                        "password": password,
                        "security_question": security_question,
                        "security_answer": hashed_sa,
                        "created_at": datetime.datetime.utcnow()
                    }

                    success = create_user(user_data)

                    if not success:
                        st.error("Email or username already exists.")
                    else:
                        token = create_access_token({
                            "sub": email,
                            "username": username
                        })

                        st.session_state['jwt_token'] = token
                        st.success("Account created successfully!")
                        time.sleep(1)
                        st.rerun()




        st.markdown("---")
        if st.button("Back to Login"):
            st.session_state['page'] = 'login'
            st.rerun()

def forgot_password_page():
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.title("Forgot Password")

        email = st.text_input("Registered Email")

        if st.button("Verify Email"):
          user = get_user_by_email(email)

          if user:
              st.session_state['fp_email'] = email
              st.session_state['fp_question'] = user['security_question']
              st.session_state['page'] = 'forgot_verify'
              st.rerun()
          else:
              st.error("Email not found")

def forgot_verify_page():
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.title("Security Verification")

        st.info(st.session_state['fp_question'])
        answer = st.text_input("Your Answer").strip()

        if st.button("Verify Answer"):
            user = get_user_by_email(st.session_state['fp_email'])

            if bcrypt.checkpw(answer.lower().encode(), user["security_answer"].encode()):
                st.session_state["otp_email"] = user["email"]
                st.session_state["otp_context"] = "forgot"

                initiate_otp(user["email"])

                st.session_state["page"] = "otp"
                st.rerun()
            else:
                st.error("Incorrect security answer")



def reset_password_page():
    token = st.session_state.get('reset_token')
    payload = verify_token(token)

    if not payload or payload.get("purpose") != "password_reset":
        st.error("Invalid or expired password reset session.")
        st.session_state['page'] = 'login'
        st.stop()

    email = payload['email']

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.title("Reset Password")

        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")

        is_valid, _, feedback = check_password_strength(new_password)

        if st.button("Reset Password"):
            if new_password != confirm_password:
                st.error("Passwords do not match")
            elif not is_valid:
                  st.error("Password does not meet security requirements:")
                  for rule in feedback:
                      st.write(f"• {rule}")
                  st.stop()
            else:
                user = get_user_by_email(email)

                if not user:
                    st.error("User not found")

                elif is_password_reused(user["id"], new_password):
                    st.error("You cannot reuse an old password. Please choose a new one.")

                else:
                    update_password(payload["email"], new_password)

                    st.success("Password reset successful! Please login.")
                    st.session_state['reset_token'] = None
                    time.sleep(1)
                    st.session_state['page'] = 'login'
                    st.rerun()


def admin_dashboard():
    require_admin()  # Only admins can access

    st.markdown("<h1>Admin Dashboard</h1>", unsafe_allow_html=True)

    # --- Fetch user stats ---
    conn = get_db_connection()
    cursor = conn.cursor()

    total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    locked_users = cursor.execute(
        "SELECT COUNT(*) FROM users WHERE lock_until IS NOT NULL AND lock_until > ?",
        (time.time(),)
    ).fetchone()[0]

    conn.close()

    # --- Show overall metrics ---
    c1, c2 = st.columns(2)
    c1.metric("👥 Total Users", total_users)
    c2.metric("🔒 Locked Accounts", locked_users)

    st.markdown("---")
    st.subheader("User Management")

    # --- Fetch all users ---
    conn = get_db_connection()
    cursor = conn.cursor()
    users = cursor.execute(
        "SELECT email, username, role, lock_until, created_at, last_login FROM users ORDER BY role DESC, username ASC"
    ).fetchall()
    conn.close()

    # --- Table Headers ---
    cols = st.columns([3, 2, 1, 1, 2, 2, 4])  # Adjust widths
    cols[0].markdown("**Email**")
    cols[1].markdown("**Username**")
    cols[2].markdown("**Role**")
    cols[3].markdown("**Status**")
    cols[4].markdown("**Created At**")
    cols[5].markdown("**Last Login**")
    cols[6].markdown("**Actions**")

    # --- Table Rows ---
    for u in users:
        row_cols = st.columns([4, 2, 1, 1, 2, 2, 5])
        row_cols[0].write(u["email"])
        row_cols[1].write(u["username"])
        row_cols[2].write(u["role"])

        # Determine account status
        locked = u["lock_until"] and time.time() < u["lock_until"]
        status_text = f"<span style='color:red'>Locked</span>" if locked else f"<span style='color:green'>Active</span>"
        row_cols[3].markdown(status_text, unsafe_allow_html=True)

        # Format timestamps
        created = u["created_at"]
        last_login = u["last_login"]
        row_cols[4].write(format_timestamp(created))
        row_cols[5].write(format_timestamp(last_login))

        # --- Actions (non-admin users only) ---
        if u["role"] != "admin":
            action_cols = row_cols[6].columns(3)  # Side-by-side buttons: Unlock, Promote, Delete

            # Unlock account if locked
            if locked and action_cols[0].button("Unlock", key=f"unlock_{u['email']}"):
                reset_failed_attempts(u["email"])
                st.success(f"Account `{u['email']}` unlocked")
                st.session_state["page"] = "admin_dashboard"
                st.rerun()

            # Promote to admin
            if action_cols[1].button("Promote", key=f"promote_{u['email']}"):
                conn = get_db_connection()
                conn.execute("UPDATE users SET role='admin' WHERE email=?", (u["email"],))
                conn.commit()
                conn.close()
                st.success(f"User `{u['email']}` promoted to admin")
                st.session_state["page"] = "admin_dashboard"
                st.rerun()

            # Delete user
            if action_cols[2].button("Delete", key=f"delete_{u['email']}"):
                conn = get_db_connection()
                conn.execute("DELETE FROM users WHERE email=?", (u["email"],))
                conn.commit()
                conn.close()
                st.success(f"User `{u['email']}` deleted")
                st.session_state["page"] = "admin_dashboard"
                st.rerun()

def create_gauge(value, title, min_val, max_val, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={'text': title, 'font': {'size': 16}, 'align': 'center'},  # slightly bigger, centered
        gauge={
            'axis': {'range': [min_val, max_val], 'tickfont': {'size': 12}},
            'bar': {'color': color},
            'borderwidth': 2,
            'bordercolor': "gray",
        }
    ))

    fig.update_layout(
        height=350,          # increase height to avoid clipping
        margin=dict(l=10, r=10, t=60, b=20),  # push content down from top
    )
    return fig

# ---------- Readability Page ----------
def readability_page():
    # Make sure user is logged in
    if not st.session_state.get('user'):
        from streamlit_extras.switch_page_button import switch_page
        switch_page('login')
        return

    st.title("📖 Text Readability Analyzer")

    # --- Input Tabs ---
    tab1, tab2 = st.tabs(["✍️ Input Text", "📂 Upload File (TXT/PDF)"])
    text_input = ""

    with tab1:
        raw_text = st.text_area("Enter text to analyze (min 50 chars):", height=200)
        if raw_text:
            text_input = raw_text

    with tab2:
        uploaded_file = st.file_uploader("Upload a file", type=["txt", "pdf"])
        if uploaded_file:
            try:
                if uploaded_file.type == "application/pdf":
                    reader = PyPDF2.PdfReader(uploaded_file)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                    text_input = text
                    st.info(f"✅ Loaded {len(reader.pages)} pages from PDF.")
                else:
                    text_input = uploaded_file.read().decode("utf-8")
                    st.info(f"✅ Loaded TXT file: {uploaded_file.name}")
            except Exception as e:
                st.error(f"Error reading file: {e}")

    # --- Analyze Button ---
    if st.button("Analyze Readability"):
        if len(text_input) < 50:
            st.error("Text is too short (min 50 chars). Please enter more text or upload a valid file.")
        else:
            with st.spinner("Calculating advanced metrics..."):
                analyzer = ReadabilityAnalyzer(text_input)
                score = analyzer.get_all_metrics()

            # --- Overall Grade ---
            avg_grade = (score['Flesch-Kincaid Grade'] + score['Gunning Fog'] +
                         score['SMOG Index'] + score['Coleman-Liau']) / 4

            if avg_grade <= 6:
                level, color = "Beginner (Elementary)", "#28a745"
            elif avg_grade <= 10:
                level, color = "Intermediate (Middle School)", "#17a2b8"
            elif avg_grade <= 14:
                level, color = "Advanced (High School/College)", "#ffc107"
            else:
                level, color = "Expert (Professional/Academic)", "#dc3545"

            st.markdown(f"""
            <div style="background-color: #1f2937; padding: 20px; border-radius: 10px; border-left: 5px solid {color}; text-align: center;">
                <h2 style="margin:0; color: {color} !important;">Overall Level: {level}</h2>
                <p style="margin:5px 0 0 0; color: #9ca3af;">Approximate Grade Level: {int(avg_grade)}</p>
            </div>
            """, unsafe_allow_html=True)

            # --- Gauges ---
            st.markdown("### 📈 Detailed Metrics")
            c1, c2, c3 = st.columns(3)
            c1.plotly_chart(create_gauge(score["Flesch Reading Ease"], "Flesch Reading Ease", 0, 100, "#00ffcc"), use_container_width=True)
            c2.plotly_chart(create_gauge(score["Flesch-Kincaid Grade"], "Flesch-Kincaid Grade", 0, 20, "#ff00ff"), use_container_width=True)
            c3.plotly_chart(create_gauge(score["SMOG Index"], "SMOG Index", 0, 20, "#ffff00"), use_container_width=True)

            c4, c5 = st.columns(2)
            c4.plotly_chart(create_gauge(score["Gunning Fog"], "Gunning Fog", 0, 20, "#00ccff"), use_container_width=True)
            c5.plotly_chart(create_gauge(score["Coleman-Liau"], "Coleman-Liau", 0, 20, "#ff9900"), use_container_width=True)

            # --- Text Stats ---
            st.markdown("### 📝 Text Statistics")
            s1, s2, s3, s4, s5 = st.columns(5)
            s1.metric("Sentences", analyzer.num_sentences)
            s2.metric("Words", analyzer.num_words)
            s3.metric("Syllables", analyzer.syllables)
            s4.metric("Complex Words", analyzer.complex_words)
            s5.metric("Characters", analyzer.char_count)

def dashboard_page():
    token = st.session_state.get('jwt_token')
    payload = verify_token(token)

    if not payload:
        st.session_state['jwt_token'] = None
        st.session_state['page'] = 'login'
        st.warning("Session expired or invalid. Please login again.")
        time.sleep(1)
        st.rerun()
        return
    username = payload.get("username", "User")


    # Main Content - Chat Interface
    st.markdown(f'''
          <div class="welcome-container">
              <div class="welcome-text">Welcome, {username}</div>
              <div class="welcome-subtext">How can I help you today?</div>
          </div>
          ''', unsafe_allow_html=True)

    # Chat container (Simple simulation)
    chat_placeholder = st.empty()

    with chat_placeholder.container():
        st.markdown('<div class="bot-msg">Hello! I am LLM. Ask me anything about LLM!</div>', unsafe_allow_html=True)
        # Assuming we might store chat history in session state later

    # User input area at bottom
    with st.form(key='chat_form', clear_on_submit=True):
        col1, col2 = st.columns([6, 1])
        with col1:
            user_input = st.text_input("Message LLM...", placeholder="Ask me anything about LLM...", label_visibility="collapsed")
        with col2:
            submit_button = st.form_submit_button("Send")

        if submit_button and user_input:
             # Just append messages visually for demo
             st.markdown(f'<div class="user-msg">{user_input}</div>', unsafe_allow_html=True)
             st.markdown('<div class="bot-msg">I am a demo bot. I received your message!</div>', unsafe_allow_html=True)

def sidebar_navigation():
    with st.sidebar:
        st.markdown(
            """
            <style>
            /* Sidebar header */
            .sidebar .sidebar-content {
                background: linear-gradient(180deg, #020617, #0f172a);
                padding-top: 2rem;
            }

            /* Logo / Title */
            .sidebar h3 {
                font-family: 'Space Grotesk', 'Inter', sans-serif;
                font-size: 1.8rem;
                font-weight: 800;
                text-align: center;
                background: linear-gradient(90deg,#38bdf8,#6366f1,#22d3ee);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 0.3rem;
            }

            /* User info */
            .sidebar p {
                font-family: 'Inter', sans-serif;
                text-align: center;
                color: #94a3b8;
                font-size: 0.95rem;
                margin-top: 0;
                margin-bottom: 1rem;
            }

            /* Option menu adjustments */
            [data-testid="stVerticalBlock"] > div > ul > li {
                font-family: 'Inter', sans-serif;
                font-size: 1rem;
                color: #cbd5e1;
                border-radius: 12px;
                margin-bottom: 4px;
                padding: 8px 12px;
                transition: all 0.3s ease;
            }


            [data-testid="stVerticalBlock"] > div > ul > li:hover {
                background: linear-gradient(135deg,#38bdf8,#6366f1);
                color: #020617 !important;
                transform: translateX(4px);
                box-shadow: 0 6px 16px rgba(56,189,248,0.5);
            }

            /* Selected menu item */
            [data-testid="stVerticalBlock"] > div > ul > li.active {
                background: linear-gradient(135deg,#6366f1,#22d3ee);
                color: #f8fafc !important;
                font-weight: 700;
                font-size: 1.05rem;
                box-shadow: 0 8px 20px rgba(56,189,248,0.6);
            }

            /* Logout button */
            .stButton > button {
                font-family: 'Inter', sans-serif;
                font-weight: 600;
                border-radius: 12px;
                background: linear-gradient(135deg,#6366f1,#22d3ee);
                color: #f8fafc;
                border: none;
                transition: all 0.25s ease;
            }
            .stButton > button:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 24px rgba(56,189,248,0.45);
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            '''
            <h1 style="
                text-align:center;
                font-weight:800;
                font-size:3rem;
                background: linear-gradient(90deg, #38bdf8, #6366f1, #22d3ee);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            ">
                PolicyNav
            </h1>
            ''',
            unsafe_allow_html=True
        )

        st.markdown(
            f"<p>👤 {st.session_state.get('user')}</p>", unsafe_allow_html=True
        )

        st.markdown("---")
        
        menu_items = []
        icons = []

        if st.session_state.get("role") == "admin":
            menu_items = ["Admin"]
            icons = ["shield-lock"]
        else:
            menu_items = ["Chat", "Readability"]
            icons = ["chat-dots", "book"]

        selected = option_menu(
            menu_title=None,  # already have title
            options=menu_items,
            icons=icons,
            menu_icon="layers",
            default_index=0,
            styles={
                "container": {"padding": "0", "background-color": "#020617"},
                "icon": {"color": "#38bdf8", "font-size": "18px"},
                "nav-link": {
                    "color": "#cbd5e1",
                    "font-size": "15px",
                    "text-align": "left",
                    "margin": "4px 0",
                    "border-radius": "12px",
                    "padding": "6px 12px",
                    "transition": "all 0.3s ease"
                },
                "nav-link-selected": {
                    "background": "linear-gradient(135deg,#6366f1,#22d3ee)",
                    "color": "#f8fafc",
                    "font-weight": "700",
                    "font-size": "16px",
                    "box-shadow": "0 8px 20px rgba(56,189,248,0.6)"
                },
                "icon-selected": {"color": "#f8fafc"},
            }
        )

        st.markdown("---")

        if st.button("Logout", use_container_width=True):
            logout()

    return selected
# ========================================
# --- MAIN APP ROUTING ---
# ========================================

token = st.session_state.get("jwt_token")
payload = verify_token(token) if token else None

if payload:
    # Restore user context
    st.session_state["user"] = payload.get("sub")
    st.session_state["role"] = payload.get("role", "user")

    # 🔹 SIDEBAR CONTROLS PAGE
    selected = sidebar_navigation()

    if selected == "Chat":
        dashboard_page()
    elif selected == "Readability":
        readability_page()
    elif selected == "Admin":
        admin_dashboard()

else:
    # 🔓 PUBLIC ROUTES
    page = st.session_state.get("page", "login")

    if page == "signup":
        signup_page()
    elif page == "otp":
        otp_verify_page()
    elif page == "forgot":
        forgot_password_page()
    elif page == "forgot_verify":
        forgot_verify_page()
    elif page == "reset":
        reset_password_page()
    else:
        login_page()
