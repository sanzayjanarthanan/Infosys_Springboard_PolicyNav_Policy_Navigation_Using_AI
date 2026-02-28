# Milestone 1 – PolicyNav Authentication System

## Features

- Signup with validation
  
- Login with JWT
- Dashboard
- Forgot password
- SQLite database
- Ngrok public URL (ngrok.com)

## How to run

```bash
pip install streamlit pyjwt pyngrok
```

```bash
streamlit run app.py
```

```bash
ngrok http 8501
```

## Screenshots
Signup
<img width="1600" height="805" alt="image" src="https://github.com/user-attachments/assets/80cd8c01-6391-4e0e-b644-2169236d1c98" />



Login
<img width="1600" height="805" alt="image" src="https://github.com/user-attachments/assets/f3733704-0bfb-456f-b662-ead563df726e" />


Dashboard


<img width="1600" height="802" alt="image" src="https://github.com/user-attachments/assets/b40c1f24-8028-4371-9559-08938b8c14da" />
Forgot Password
<img width="1600" height="802" alt="image" src="https://github.com/user-attachments/assets/61dc5a74-5cde-4beb-b197-ab764ee78228" />

## Notes

- The SQLite database (`users.db`) is created automatically on first run
- All user inputs are validated to prevent empty or invalid entries
- Passwords are stored securely using SHA-256 hashing
- JWT tokens are used for session management and authentication
- Password validation rules are enforced during signup and password reset
- The dashboard is accessible only after successful authentication
