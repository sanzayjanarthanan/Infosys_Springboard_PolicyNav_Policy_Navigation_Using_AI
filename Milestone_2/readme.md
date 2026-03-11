# Milestone 2 – OTP Authentication,Admin Interface,Readability Dashboard

## Description

In this milestone, we developed a secure user authentication system for the PolicyNav application using Streamlit, JWT (JSON Web Tokens), and SQL Lite. The system enables users to create accounts, log in securely, reset forgotten passwords using security questions, and access a protected dashboard after authentication.
Integrated otp verification for Forgot password.Added seperate Admin and User interfaces and a Readability dashboard.

## Features Implemented
- All sensitive and personal data added to Colab Secrets

- OTP-based authentication for Forgot Password along with Security Question

- Account lock after 3 wrong password attempts (5-minute lock)

- Secure Forgot Password (no reuse of old passwords) - Password History

- Admin Login + Admin Dashboard

- Readability Dashboard 
## How to Run

1. Install required dependencies  
   ```bash
   pip install streamlit pyngrok pyjwt watchdog dotenv bcrypt PyPDF2 streamlit-option-menu readability-lxml textstat plotly
2. Run the Streamlit application
   ```bash
   streamlit run app.py
3. Use ngrok to expose the application (if required)
   ```bash
   ngrok http 8501

## Screenshots

- Signup Page
  <img width="1918" height="967" alt="image" src="https://github.com/user-attachments/assets/d519ed27-5125-408a-a8c9-936be853d0de" />

- Login Page
  <img width="1918" height="967" alt="image" src="https://github.com/user-attachments/assets/837e98d3-2cf8-47d1-a835-37b93a51e0dd" />
  
- Admin Dashboard
  ![WhatsApp Image 2026-03-11 at 6 24 12 PM](https://github.com/user-attachments/assets/d2c343ee-733c-4d48-ad32-1e53baf35062)



- User Dashboard
  ![WhatsApp Image 2026-03-11 at 6 24 44 PM](https://github.com/user-attachments/assets/3d133881-3094-436d-9398-95828270b6a3)

- Readability Dashboard
  ![WhatsApp Image 2026-03-11 at 6 25 29 PM](https://github.com/user-attachments/assets/fb22f3b6-03f1-4827-a32a-9425a1b05cdb)

![WhatsApp Image 2026-03-11 at 6 54 13 PM](https://github.com/user-attachments/assets/441489b4-0e74-4de0-b85e-3494cf741190)


  ![WhatsApp Image 2026-03-11 at 6 27 27 PM](https://github.com/user-attachments/assets/c378bcc0-36fb-4b10-a4e4-b63dc261e46e)

  ![WhatsApp Image 2026-03-11 at 6 27 59 PM](https://github.com/user-attachments/assets/6c9675f3-cc51-4540-ae65-7d2b586ace32)


- Forgot Password Page
  <img width="1918" height="966" alt="image" src="https://github.com/user-attachments/assets/39b6cc00-fd11-4851-a5df-3db6145c3656" />
  <img width="1918" height="966" alt="image" src="https://github.com/user-attachments/assets/2c266a68-63d2-48ab-86e9-2286e3863065" />

- OTP Verification Page
  <img width="1918" height="966" alt="image" src="https://github.com/user-attachments/assets/cce47ae5-bbe5-40a8-92e8-4d27f7c8e2ec" />

- OTP Message 
  <img width="1512" height="767" alt="image" src="https://github.com/user-attachments/assets/feadd571-c893-4085-a1ae-0ee679365119" />


- Reset Password Page
<img width="1918" height="967" alt="image" src="https://github.com/user-attachments/assets/cb5466b4-df7e-4752-b9d3-59de9b718a39" />

## Notes
- JWT is used for session management and password reset flow.
- Added Readability Dashboard,Admin Dashboard.
- Changed the database from MongoDB Atlas to SqLite

 
## Author
Sanjay j

