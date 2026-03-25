import streamlit as st
import jwt
import datetime
import time
import re
from pymongo import MongoClient
# --- Configuration ---
# In production, use environment variable
SECRET_KEY = "super_secret_key_for_demo"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --- MongoDB Configuration ---
# MongoDB connection string (set your own credentials here)
MONGO_URI = "mongodb+srv://<db_username>:<db_password>@<cluster_url>/?appName=Cluster0"

client = MongoClient(MONGO_URI)
db = client["policynav_db"]
users_collection = db["users"]

# --- MongoDB Helper Functions ---


def get_user_by_email(email):
    return users_collection.find_one({"email": email})


def get_user_by_username(username):
    return users_collection.find_one({"username": username})


def create_user(user_data):
    users_collection.insert_one(user_data)

# --- JWT Utils ---


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow(
    ) + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
# --- Validation Utils ---


def is_valid_email(email):
    # Regex for standard email format
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    try:
        if re.match(pattern, email):
            return True
    except:
        return False
    return False


def is_valid_password(password):
    # Alphanumeric check and min length 8
    if len(password) < 8:
        return False

    pattern = r'^[a-zA-Z0-9]+$'
    return bool(re.match(pattern, password))


# --- Session State Management ---
if 'jwt_token' not in st.session_state:
    st.session_state['jwt_token'] = None
if 'page' not in st.session_state:
    st.session_state['page'] = 'login'

# --- Styling ---
st.set_page_config(page_title="Infosys SpringBoard Intern",
                   page_icon="🤖", layout="wide")

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
# --- Views ---


def login_page():
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 3, 2])

    with col2:
        st.markdown('''
        <h1 style="
            text-align: center;
            font-size: 3rem;
            font-weight: 800;
            color: #2563eb;
            margin-bottom: 0.2em;
        ">
        PolicyNav – Public Policy Navigation Using AI
        </h1>
        ''', unsafe_allow_html=True)

        st.markdown(
            "<h4 style='text-align:center; color:#94a3b8;'>Please sign in to continue</h4>", unsafe_allow_html=True)

        with st.form("login_form"):
            email = st.text_input("Email Address")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In")

            # ----- FIELD-BY-FIELD VALIDATION -----
            if submitted:
                if not email:
                    st.error("Email is required")
                elif not is_valid_email(email):
                    st.error("Invalid email format (e.g. user@domain.com)")

                if not password:
                    st.error("Password is required")

                # Only check DB if inputs are valid
                if email and password and is_valid_email(email):
                    user = get_user_by_email(email)

                    if not user:
                        st.error("No account found with this email")
                    elif user["password"] != password:
                        st.error("Incorrect password")
                    else:
                        token = create_access_token({
                            "sub": email,
                            "username": user["username"]
                        })

                        st.session_state["jwt_token"] = token
                        st.success("Login successful")
                        time.sleep(0.5)
                        st.rerun()

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Forgot Password?", use_container_width=True):
                st.session_state['page'] = 'forgot'
                st.rerun()

        with c2:
            if st.button("Create an Account", use_container_width=True):
                st.session_state['page'] = 'signup'
                st.rerun()


def signup_page():
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 3, 2])

    with col2:
        st.title("Create Account")

        with st.form("signup_form"):
            username = st.text_input("Username (Required)").strip()
            email = st.text_input(
                "Email Address (@domain.com required)").strip()
            password = st.text_input(
                "Password (min 8 chars, alphanumeric)").strip()
            confirm_password = st.text_input(
                "Confirm Password", type="password").strip()
            security_question = st.selectbox(
                "Security Question",
                [
                    "What is your pet name?",
                    "What is your college name?",
                    "Who is your favorite teacher?"
                ]
            )

            security_answer = st.text_input("Security Answer").strip()
            submitted = st.form_submit_button("Sign Up")

            if submitted:
                errors = []

                # Username Validation
                if not username:
                    errors.append("Username is mandatory.")
                elif get_user_by_username(username):
                    errors.append(f"Username '{username}' is already taken.")

                # Email Validation
                if not email:
                    errors.append("Email is mandatory.")
                elif not is_valid_email(email):
                    errors.append(
                        "Invalid Email format (e.g. user@domain.com).")
                elif get_user_by_email(email):
                    errors.append(f"Email '{email}' is already registered.")

                # Password Validation
                if not password:
                    errors.append("Password is mandatory.")
                elif not is_valid_password(password):
                    errors.append(
                        "Password must be at least 8 characters long and contain only alphanumeric characters.")

                # Confirm Password
                if password != confirm_password:
                    errors.append("Passwords do not match.")

                # Security Answer
                if not security_answer:
                    errors.append("Security answer is mandatory.")

                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    user_data = {
                        "username": username,
                        "email": email,
                        "password": password,  # NOTE: Plain text for Milestone-1 only
                        "security_question": security_question,
                        "security_answer": security_answer,
                        "created_at": datetime.datetime.utcnow()
                    }

                    create_user(user_data)

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

            if user and answer == user['security_answer']:
                reset_token = create_access_token({
                    "email": st.session_state['fp_email'],
                    "purpose": "password_reset"
                })

                st.session_state['reset_token'] = reset_token
                st.session_state['page'] = 'reset'
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

        if st.button("Reset Password"):
            if new_password != confirm_password:
                st.error("Passwords do not match")
            elif not is_valid_password(new_password):
                st.error(
                    "Password must be at least 8 characters long and contain only alphanumeric characters.")
            else:
                users_collection.update_one(
                    {"email": email},
                    {"$set": {"password": new_password}}
                )

                st.success("Password reset successful! Please login.")
                st.session_state["reset_token"] = None
                time.sleep(1)
                st.session_state["page"] = "login"
                st.rerun()


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

    with st.sidebar:
        st.title("🤖 LLM")
        st.markdown("---")
        if st.button("➕ New Chat", use_container_width=True):
            st.info("Started new chat!")

        st.markdown("### History")
        st.markdown("- Project analysis")
        st.markdown("- NLP")
        st.markdown("---")
        st.markdown("### Settings")
        if st.button("Logout", use_container_width=True):
            st.session_state['jwt_token'] = None
            st.session_state['page'] = 'login'
            st.rerun()
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
        st.markdown(
            '<div class="bot-msg">Hello! I am LLM. Ask me anything about LLM!</div>', unsafe_allow_html=True)
        # Assuming we might store chat history in session state later

    # User input area at bottom
    with st.form(key='chat_form', clear_on_submit=True):
        col1, col2 = st.columns([6, 1])
        with col1:
            user_input = st.text_input(
                "Message LLM...", placeholder="Ask me anything about LLM...", label_visibility="collapsed")
        with col2:
            submit_button = st.form_submit_button("Send")

        if submit_button and user_input:
            # Just append messages visually for demo
            st.markdown(
                f'<div class="user-msg">{user_input}</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="bot-msg">I am a demo bot. I received your message!</div>', unsafe_allow_html=True)


# --- Main App Logic ---
token = st.session_state.get('jwt_token')
if token:
    if verify_token(token):
        dashboard_page()
    else:
        st.session_state['jwt_token'] = None
        st.session_state['page'] = 'login'
        st.rerun()
else:
    if st.session_state['page'] == 'signup':
        signup_page()
    elif st.session_state['page'] == 'forgot':
        forgot_password_page()
    elif st.session_state['page'] == 'forgot_verify':
        forgot_verify_page()
    elif st.session_state['page'] == 'reset':
        reset_password_page()
    else:
        login_page()

