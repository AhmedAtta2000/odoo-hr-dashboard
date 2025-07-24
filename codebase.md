# backend\auth.py

```py
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- OAuth2 Scheme ---
# This tells FastAPI where to look for the token (in the Authorization header)
# tokenUrl is the relative path to your login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")

# --- Utility Functions ---
def verify_password(plain_password, hashed_password):
    """Verifies a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Hashes a plain password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Dependency for protected routes (we'll use this later) ---
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Decodes the token and returns the user identifier (e.g., email or ID)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # --- IMPORTANT: Adapt this to your user identifier ---
        # We are storing 'sub' (subject) which is typically the username/email
        user_identifier: str = payload.get("sub")
        if user_identifier is None:
            raise credentials_exception
        # You might want to add token expiry check here as well,
        # although jwt.decode should handle it.
        # You could also fetch the user from DB here to ensure they still exist/are active
    except JWTError:
        raise credentials_exception
    # For now, just return the identifier (e.g., email) stored in the token
    return {"user_identifier": user_identifier}
```

# backend\main.py

```py
import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm # Use this for login form data
from fastapi.middleware.cors import CORSMiddleware
from datetime import timedelta
from pydantic import BaseModel, EmailStr
from typing import Optional # If not already imported
from datetime import date # For date types
from typing import List # For list responses
from fastapi.responses import Response 

# Import functions and variables from auth.py
from auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_user # Import the dependency for protected routes
)

# --- Dummy User Database (Replace with real DB lookup later) ---
# NEVER store plain text passwords. Hash them first!
# Use a separate script or the python REPL to generate the hash:
# >>> from auth import get_password_hash
# >>> print(get_password_hash("testpassword"))
# Copy the resulting hash below
FAKE_USERS_DB = {
    "test@example.com": {
        "email": "test@example.com",
        "hashed_password": "$2b$12$iABt5H9B5W1w4n8CJNL2huIshbFGu7dpcFLdLcJoJHocm/P/jnUCO", # Replace with your generated hash for "testpassword"
        "full_name": "Test User",
        "job_title": "Software Tester", # Job Title
        "phone": "123-456-7890", # Phone
        "address": "123 Main St, Anytown, AT 12345", # Address
        "department": "Quality Assurance", # Department
        "disabled": False, # You might use this later
        # Add other user info as needed
    }
    # Add more dummy users if you like
}

FAKE_LEAVE_TYPES = [
    {"id": 1, "name": "Legal Leaves / Annual Vacation"},
    {"id": 2, "name": "Sick Time Off"},
    {"id": 3, "name": "Unpaid"},
    {"id": 99, "name": "Other (Specify in reason)"},
]

# Associate payslips with users (using email as key for now)
FAKE_PAYSLIPS_DB = {
    "test@example.com": [
        {"id": 101, "month": "September 2023", "total": 3500.50, "status": "Paid", "pdf_available": True},
        {"id": 100, "month": "August 2023", "total": 3450.00, "status": "Paid", "pdf_available": True},
        {"id": 99, "month": "July 2023", "total": 3480.75, "status": "Paid", "pdf_available": False}, # Example where PDF might not be ready
         {"id": 102, "month": "October 2023", "total": 0.00, "status": "Draft", "pdf_available": False},
    ],
    # Add payslips for other dummy users if needed
}

# --- Helper Function (Simulates fetching user) ---
def get_user(db, email: str):
    if email in db:
        return db[email]
    return None

# --- FastAPI App Initialization ---
app = FastAPI()

# CORS Configuration (already set up)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models (Data Shapes) ---
# Define the shape of the data we expect to return for a user profile
class UserProfile(BaseModel):
    email: EmailStr
    full_name: str
    job_title: Optional[str] = None # Mark fields from requirements as Optional for flexibility
    phone: Optional[str] = None
    address: Optional[str] = None
    department: Optional[str] = None

    class Config:
        # Allow Pydantic to work with ORM objects directly later if needed
        # Keep it for now even with dicts
        from_attributes = True # formerly orm_mode = True

class LeaveType(BaseModel):
    id: int
    name: str

class LeaveRequestPayload(BaseModel):
    leave_type_id: int
    from_date: date # Use date type for validation
    to_date: date   # Use date type for validation
    note: Optional[str] = None # Reason is optional

class PayslipListItem(BaseModel):
    id: int # Needed to identify which payslip to download
    month: str # e.g., "September 2023"
    total: float # Use float for monetary values
    status: str # e.g., "Paid", "Draft"
    pdf_available: bool # Flag to enable/disable download button

# --- Helper Function (Simulates fetching user) ---
# No changes needed here for now
def get_user(db, email: str):
    if email in db:
        return db[email]
    return None

# --- FastAPI App Initialization ---
# ... (no changes needed here)

# --- API Endpoints ---
# ... (root and login endpoints unchanged)

# --- EXAMPLE PROTECTED ENDPOINT (Requires Login) ---
# Add response_model=UserProfile to automatically validate and filter the output
@app.get("/api/v1/users/me", response_model=UserProfile)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    user_email = current_user.get("user_identifier")
    user_info_dict = get_user(FAKE_USERS_DB, user_email) # Get the full dict
    if not user_info_dict:
         raise HTTPException(status_code=404, detail="User not found")

    # Pydantic will automatically convert the relevant keys from the dict
    # into a UserProfile object and filter out extra keys (like hashed_password)
    return user_info_dict # FastAPI handles the conversion based on response_model

# --- API Endpoints ---
@app.get("/")
async def read_root():
    return {"message": "ESS SaaS Backend is running!"}


# --- LOGIN ENDPOINT ---
@app.post("/api/v1/login")
# Use OAuth2PasswordRequestForm: it expects form data with 'username' and 'password' fields
# Note: It uses 'username' field name by default, which we'll map to email.
@app.post("/api/v1/login")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    print("--- Login Attempt ---") # ADD THIS LINE
    print(f"Received username (email): {form_data.username}") # ADD THIS LINE
    # Don't print the raw password for security, but check its length if needed
    print(f"Received password length: {len(form_data.password) if form_data.password else 0}") # ADD THIS LINE

    user = get_user(FAKE_USERS_DB, form_data.username)
    print(f"User found in DB: {'Yes' if user else 'No'}") # ADD THIS LINE

    if not user:
        print("Raising HTTPException: User not found") # ADD THIS LINE
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    print(f"Stored Hashed Password: {user.get('hashed_password')}") # ADD THIS LINE
    # Explicitly call verify_password and print the result
    is_password_correct = verify_password(form_data.password, user["hashed_password"])
    print(f"Password verification result: {is_password_correct}") # ADD THIS LINE

    if not is_password_correct:
         print("Raising HTTPException: Password incorrect") # ADD THIS LINE
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
         )

    # Check if user is active (optional)
    # ... (rest of the function) ...

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    print("--- Login Success ---") # ADD THIS LINE
    return {"access_token": access_token, "token_type": "bearer"}


# --- EXAMPLE PROTECTED ENDPOINT (Requires Login) ---
@app.get("/api/v1/users/me")
# Add Depends(get_current_user) to protect this route
# It will automatically validate the token from the Authorization header
async def read_users_me(current_user: dict = Depends(get_current_user)):
    # current_user will contain the payload from get_current_user (e.g., {'user_identifier': 'test@example.com'})
    # You can now use this identifier to fetch more detailed user info
    user_email = current_user.get("user_identifier")
    user_info = get_user(FAKE_USERS_DB, user_email) # Get full info again (or from DB later)
    if not user_info:
         raise HTTPException(status_code=404, detail="User not found") # Should not happen if token is valid

    # Don't return the hashed password!
    return {"email": user_info["email"], "full_name": user_info["full_name"]}

@app.get("/api/v1/leave-types", response_model=List[LeaveType])
async def get_leave_types(current_user: dict = Depends(get_current_user)):
    # In a real app, fetch these from Odoo (hr.leave.type) or your DB
    print(f"User {current_user.get('user_identifier')} requested leave types.")
    return FAKE_LEAVE_TYPES

# --- POST Leave Request (Protected) ---
@app.post("/api/v1/leave-request", status_code=status.HTTP_201_CREATED) # Indicate resource creation
async def submit_leave_request(
    payload: LeaveRequestPayload, # Use the Pydantic model to validate incoming JSON
    current_user: dict = Depends(get_current_user)
):
    user_email = current_user.get("user_identifier")
    print(f"--- Leave Request Received from {user_email} ---")
    print(f"Leave Type ID: {payload.leave_type_id}")
    print(f"From Date: {payload.from_date}")
    print(f"To Date: {payload.to_date}")
    print(f"Reason: {payload.note}")
    print("--- End Leave Request ---")

    return {"message": "Leave request submitted successfully."}

    # --- GET Payslip List (Protected) ---
@app.get("/api/v1/payslips", response_model=List[PayslipListItem])
async def get_payslip_list(current_user: dict = Depends(get_current_user)):
    user_email = current_user.get("user_identifier")
    print(f"User {user_email} requested payslip list.")
    # Retrieve payslips for the logged-in user from our fake DB
    user_payslips = FAKE_PAYSLIPS_DB.get(user_email, [])
    return user_payslips

# --- GET Payslip PDF Download (Protected) ---
@app.get("/api/v1/payslip/{payslip_id}/download")
async def download_payslip_pdf(payslip_id: int, current_user: dict = Depends(get_current_user)):
    user_email = current_user.get("user_identifier")
    print(f"User {user_email} requested download for payslip ID: {payslip_id}")

    # --- TODO Later: ---
    # 1. Verify this payslip_id actually belongs to this user (check FAKE_PAYSLIPS_DB or real DB)
    # 2. Verify PDF is available (check the 'pdf_available' flag or Odoo status)
    # 3. Fetch the actual PDF content from Odoo (e.g., using report generation or finding attached file)
    # 4. Return using FastAPI's FileResponse or StreamingResponse:
    #    from fastapi.responses import FileResponse
    #    pdf_path = "path/to/generated/payslip.pdf" # Get the path
    #    return FileResponse(pdf_path, media_type='application/pdf', filename=f"payslip_{payslip_id}.pdf")

    # --- For Now: Simulate download ---
    # First, basic check if user and payslip seem valid (based on dummy data)
    user_payslips = FAKE_PAYSLIPS_DB.get(user_email, [])
    payslip_info = next((p for p in user_payslips if p["id"] == payslip_id and p["pdf_available"]), None)

    if not payslip_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payslip not found or PDF not available for download.")

    # Simulate PDF content as simple text
    pdf_simulation_content = f"Simulated PDF Content for Payslip ID {payslip_id}\nMonth: {payslip_info['month']}\nUser: {user_email}"
    # Set headers to make the browser *try* to download it
    headers = {
        'Content-Disposition': f'attachment; filename="payslip_{payslip_id}_simulated.txt"'
    }
    # Return plain text for now, pretending it's a PDF download
    return Response(content=pdf_simulation_content, media_type="text/plain", headers=headers)

```

# frontend\.gitignore

```
# See https://help.github.com/articles/ignoring-files/ for more about ignoring files.

# dependencies
/node_modules
/.pnp
.pnp.js

# testing
/coverage

# production
/build

# misc
.DS_Store
.env.local
.env.development.local
.env.test.local
.env.production.local

npm-debug.log*
yarn-debug.log*
yarn-error.log*

```

# frontend\package.json

```json
{
  "name": "frontend",
  "version": "0.1.0",
  "private": true,
  "dependencies": {
    "@testing-library/dom": "^10.4.0",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.3.0",
    "@testing-library/user-event": "^13.5.0",
    "axios": "^1.9.0",
    "react": "^19.1.0",
    "react-datepicker": "^8.3.0",
    "react-dom": "^19.1.0",
    "react-router-dom": "^7.5.3",
    "react-scripts": "5.0.1",
    "web-vitals": "^2.1.4"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test",
    "eject": "react-scripts eject"
  },
  "eslintConfig": {
    "extends": [
      "react-app",
      "react-app/jest"
    ]
  },
  "browserslist": {
    "production": [
      ">0.2%",
      "not dead",
      "not op_mini all"
    ],
    "development": [
      "last 1 chrome version",
      "last 1 firefox version",
      "last 1 safari version"
    ]
  }
}

```

# frontend\public\favicon.ico

This is a binary file of the type: Binary

# frontend\public\index.html

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%PUBLIC_URL%/favicon.ico" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#000000" />
    <meta
      name="description"
      content="Web site created using create-react-app"
    />
    <link rel="apple-touch-icon" href="%PUBLIC_URL%/logo192.png" />
    <!--
      manifest.json provides metadata used when your web app is installed on a
      user's mobile device or desktop. See https://developers.google.com/web/fundamentals/web-app-manifest/
    -->
    <link rel="manifest" href="%PUBLIC_URL%/manifest.json" />
    <!--
      Notice the use of %PUBLIC_URL% in the tags above.
      It will be replaced with the URL of the `public` folder during the build.
      Only files inside the `public` folder can be referenced from the HTML.

      Unlike "/favicon.ico" or "favicon.ico", "%PUBLIC_URL%/favicon.ico" will
      work correctly both with client-side routing and a non-root public URL.
      Learn how to configure a non-root public URL by running `npm run build`.
    -->
    <title>React App</title>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
    <!--
      This HTML file is a template.
      If you open it directly in the browser, you will see an empty page.

      You can add webfonts, meta tags, or analytics to this file.
      The build step will place the bundled scripts into the <body> tag.

      To begin the development, run `npm start` or `yarn start`.
      To create a production bundle, use `npm run build` or `yarn build`.
    -->
  </body>
</html>

```

# frontend\public\logo192.png

This is a binary file of the type: Image

# frontend\public\logo512.png

This is a binary file of the type: Image

# frontend\public\manifest.json

```json
{
  "short_name": "React App",
  "name": "Create React App Sample",
  "icons": [
    {
      "src": "favicon.ico",
      "sizes": "64x64 32x32 24x24 16x16",
      "type": "image/x-icon"
    },
    {
      "src": "logo192.png",
      "type": "image/png",
      "sizes": "192x192"
    },
    {
      "src": "logo512.png",
      "type": "image/png",
      "sizes": "512x512"
    }
  ],
  "start_url": ".",
  "display": "standalone",
  "theme_color": "#000000",
  "background_color": "#ffffff"
}

```

# frontend\public\robots.txt

```txt
# https://www.robotstxt.org/robotstxt.html
User-agent: *
Disallow:

```

# frontend\README.md

```md
# Getting Started with Create React App

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will reload when you make changes.\
You may also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can't go back!**

If you aren't satisfied with the build tool and configuration choices, you can `eject` at any time. This command will remove the single build dependency from your project.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you're on your own.

You don't have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn't feel obligated to use this feature. However we understand that this tool wouldn't be useful if you couldn't customize it when you are ready for it.

## Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).

### Code Splitting

This section has moved here: [https://facebook.github.io/create-react-app/docs/code-splitting](https://facebook.github.io/create-react-app/docs/code-splitting)

### Analyzing the Bundle Size

This section has moved here: [https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size](https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size)

### Making a Progressive Web App

This section has moved here: [https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app](https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app)

### Advanced Configuration

This section has moved here: [https://facebook.github.io/create-react-app/docs/advanced-configuration](https://facebook.github.io/create-react-app/docs/advanced-configuration)

### Deployment

This section has moved here: [https://facebook.github.io/create-react-app/docs/deployment](https://facebook.github.io/create-react-app/docs/deployment)

### `npm run build` fails to minify

This section has moved here: [https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify](https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify)

```

# frontend\src\App.css

```css
.App {
  text-align: center;
}

.App-logo {
  height: 40vmin;
  pointer-events: none;
}

@media (prefers-reduced-motion: no-preference) {
  .App-logo {
    animation: App-logo-spin infinite 20s linear;
  }
}

.App-header {
  background-color: #282c34;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: calc(10px + 2vmin);
  color: white;
}

.App-link {
  color: #61dafb;
}

@keyframes App-logo-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
/* Keep existing styles or reset them */
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background-color: #f4f7f6; /* Light background for the whole page */
}

.App {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

/* Header Styling */
.app-header {
  background-color: #282c34; /* Dark header */
  padding: 10px 20px;
  color: white;
}

.header-content {
    max-width: 1200px; /* Limit width and center content */
    margin: 0 auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header-content nav a {
    color: #61dafb;
    text-decoration: none;
    margin: 0 15px;
    transition: color 0.2s ease;
}
.header-content nav a:hover {
    color: white;
}


.logout-button {
  background-color: #dc3545;
  color: white;
  border: none;
  padding: 8px 15px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: background-color 0.2s ease;
}

.logout-button:hover {
  background-color: #c82333;
}


/* Main Content Area */
.app-main-content {
  flex-grow: 1; /* Take up remaining vertical space */
  padding: 0; /* Remove padding if pages handle their own */
  max-width: 1200px; /* Optional: Limit width and center */
  width: 100%;
  margin: 0 auto; /* Center content area */
  box-sizing: border-box;
}

/* Fullscreen Loading Indicator */
.loading-fullscreen {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  font-size: 1.5rem;
  color: #555;
}

/* General Error Message Style (reuse from LoginPage if desired) */
.error-message {
  color: #dc3545;
  background-color: #f8d7da;
  border: 1px solid #f5c6cb;
  padding: 0.75rem;
  border-radius: 4px;
  margin: 1rem auto; /* Center error message */
  text-align: center;
  max-width: 500px;
}

/* You might want to move LoginPage specific styles entirely into LoginPage.css */
/* Example: Remove .login-container styles from App.css if they only apply to login */
```

# frontend\src\App.js

```js
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BrowserRouter as Router, Routes, Route, Navigate, Link } from 'react-router-dom'; // Import Router components

import LoginPage from './components/LoginPage';
import DashboardPage from './components/DashboardPage'; // Import Dashboard
// Import other page components here later (e.g., ProfilePage, LeavePage)

import './App.css';

import ProfilePage from './components/ProfilePage'; // Import ProfilePage

import LeaveRequestPage from './components/LeaveRequestPage'; // Import LeaveRequestPage

function App() {
  const [token, setToken] = useState(localStorage.getItem('authToken')); // Try loading token from localStorage
  const [userData, setUserData] = useState(null);
  const [loadingUser, setLoadingUser] = useState(false);
  const [authError, setAuthError] = useState(''); // Specific error for auth/user fetch

  // --- Function to fetch user data using the token ---
  const fetchUserData = async (currentToken) => {
    if (!currentToken) return;
    setLoadingUser(true);
    setAuthError(''); // Clear previous auth errors
    try {
      const response = await axios.get('http://127.0.0.1:8000/api/v1/users/me', {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      setUserData(response.data);
    } catch (err) {
      console.error("Error fetching user data:", err);
      setAuthError("Could not fetch user data. Your session might be invalid.");
      handleLogout(); // Logout if token is invalid or fetching fails
    } finally {
      setLoadingUser(false);
    }
  };

  // --- Effect to fetch user data if token exists on load ---
  useEffect(() => {
    if (token) {
      console.log("Token found, fetching user data...");
      // Set Authorization header for all subsequent axios requests
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchUserData(token);
    } else {
         // Clear Authorization header if no token
         delete axios.defaults.headers.common['Authorization'];
    }
  }, [token]); // Re-run this effect if the token changes

  // --- Login Handler ---
  const handleLoginSuccess = (receivedToken) => {
    localStorage.setItem('authToken', receivedToken); // Store token in localStorage for persistence
    setToken(receivedToken);
    // User data will be fetched by the useEffect hook now
  };

  // --- Logout Handler ---
  const handleLogout = () => {
    localStorage.removeItem('authToken'); // Remove token from storage
    setToken(null);
    setUserData(null);
    delete axios.defaults.headers.common['Authorization']; // Clear auth header
    console.log("User logged out");
    // No need to navigate here, the routing logic will handle it
  };

  // --- Loading State ---
  // Show loading indicator while checking token validity on initial load
  // We check loadingUser state AFTER we tried loading token from localStorage
  const isLoadingInitialAuth = token && loadingUser && !userData && !authError;
  if (isLoadingInitialAuth) {
      return <div className="loading-fullscreen">Checking authentication...</div>; // Add some basic CSS for this
  }

  // --- Render Logic with Router ---
  return (
    <Router>
      <div className="App">
        {/* Basic Header shown only when logged in */}
        {token && userData && (
          <header className="app-header">
             <div className="header-content">
                <span>Welcome, {userData.full_name}!</span>
                <nav>
                  <Link to="/dashboard">Dashboard</Link>
                  <Link to="/profile">My Profile</Link>
                  <Link to="/leave-request">Request Leave</Link>
                  {/* Add links to Leave etc. later */}
                </nav>
                <button onClick={handleLogout} className="logout-button">Logout</button>
             </div>
          </header>
        )}

        <main className="app-main-content">
          {authError && !token && <p className="error-message">{authError}</p>} {/* Show auth error on login page if needed */}
          <Routes>
            {/* Login Route */}
            <Route
              path="/login"
              element={
                !token ? (
                  <LoginPage onLoginSuccess={handleLoginSuccess} />
                ) : (
                  <Navigate to="/dashboard" replace /> // If logged in, redirect from /login to /dashboard
                )
              }
            />

            {/* Dashboard Route (Protected) */}
            <Route
              path="/dashboard"
              element={
                token ? (
                  <DashboardPage userData={userData} /> // Pass user data if needed
                ) : (
                  <Navigate to="/login" replace /> // If not logged in, redirect to /login
                )
              }
            />

            {/* Profile Route (Protected) */}
            <Route
              path="/profile"
              element={
                token ? (
                  <ProfilePage /> // Render ProfilePage if logged in
                ) : (
                  <Navigate to="/login" replace /> // Redirect to login if not logged in
                )
              }
            />

            {/* Leave Request Route (Protected) */}
            <Route
              path="/leave-request"
              element={
                token ? (
                  <LeaveRequestPage /> // Render LeaveRequestPage if logged in
                ) : (
                  <Navigate to="/login" replace /> // Redirect to login if not logged in
                )
              }
            />

            {/* Add other routes here later (e.g., /profile, /leaves) */}
            {/* Example Protected Profile Route:
            <Route
              path="/profile"
              element={
                token ? (
                  <ProfilePage userData={userData} />
                ) : (
                  <Navigate to="/login" replace />
                )
              }
            />
            */}


            {/* Default Route */}
            <Route
              path="*" // Matches any other path
              element={
                token ? (
                  <Navigate to="/dashboard" replace /> // If logged in, go to dashboard
                ) : (
                  <Navigate to="/login" replace /> // If not logged in, go to login
                )
              }
            />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
```

# frontend\src\App.test.js

```js
import { render, screen } from '@testing-library/react';
import App from './App';

test('renders learn react link', () => {
  render(<App />);
  const linkElement = screen.getByText(/learn react/i);
  expect(linkElement).toBeInTheDocument();
});

```

# frontend\src\components\DashboardPage.css

```css
.dashboard-container {
    padding: 2rem;
  }
  
  .dashboard-container h2 {
    margin-bottom: 1.5rem;
    color: #333;
    border-bottom: 1px solid #eee;
    padding-bottom: 0.5rem;
  }
  
  .dashboard-widgets {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); /* Responsive grid */
    gap: 1.5rem; /* Space between widgets */
  }
  
  .widget {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 1.5rem;
    background-color: #ffffff;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    transition: box-shadow 0.2s ease-in-out;
  }
  
  .widget:hover {
     box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  }
  
  .widget h3 {
    margin-top: 0;
    margin-bottom: 1rem;
    color: #444;
    font-size: 1.1rem;
  }
  
  .widget p {
    margin-bottom: 1rem;
    color: #666;
    line-height: 1.5;
  }
  
  .widget strong {
      color: #333;
  }
  
  .widget a {
    color: #007bff;
    text-decoration: none;
    font-weight: bold;
  }
  
  .widget a:hover {
    text-decoration: underline;
  }
```

# frontend\src\components\DashboardPage.js

```js
import React from 'react';
import './DashboardPage.css'; // We'll create this later

// This component might receive user data as a prop later
function DashboardPage({ userData }) {
  const userName = userData ? userData.full_name : 'User'; // Use actual name if available

  return (
    <div className="dashboard-container">
      <h2>Welcome, {userName}!</h2>

      <div className="dashboard-widgets">
        {/* Widget 1: Pending Leaves (Placeholder) */}
        <div className="widget">
          <h3>Pending Leaves</h3>
          <p>You have <strong>2</strong> pending leave requests.</p>
          {/* Link to leave page later */}
          <a href="#">View Details</a>
        </div>

        {/* Widget 2: Next Day Off (Placeholder) */}
        <div className="widget">
          <h3>Next Scheduled Day Off</h3>
          <p>Your next scheduled day off is <strong>Friday, October 27th</strong>.</p>
          {/* Link to schedule/attendance later */}
          <a href="#">View Schedule</a>
        </div>

        {/* Widget 3: Latest Payslip (Placeholder) */}
        <div className="widget">
          <h3>Latest Payslip Status</h3>
          <p>Your payslip for September is <strong>Available</strong>.</p>
          {/* Link to payslips page later */}
          <a href="#">View Payslips</a>
        </div>

         {/* Add more widgets as needed */}

      </div>
    </div>
  );
}

export default DashboardPage;
```

# frontend\src\components\LeaveRequestPage.css

```css
.leave-request-container {
    padding: 2rem;
    max-width: 700px;
    margin: 2rem auto;
    background-color: #ffffff;
    border-radius: 8px;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
  }
  
  .leave-request-container h2 {
    text-align: center;
    margin-top: 0;
    margin-bottom: 2rem;
    color: #333;
    border-bottom: 1px solid #eee;
    padding-bottom: 1rem;
  }
  
  .leave-request-form .form-group {
    margin-bottom: 1.5rem;
  }
  
  .leave-request-form label {
    display: block;
    margin-bottom: 0.5rem;
    color: #555;
    font-weight: bold;
  }
  
  .leave-request-form select,
  .leave-request-form textarea,
  .leave-request-form .date-picker-input { /* Style the date picker input */
    width: 100%;
    padding: 0.75rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    box-sizing: border-box;
    font-size: 1rem;
  }
  
  /* Enhance date picker appearance */
  .react-datepicker-wrapper {
      width: 100%; /* Make the wrapper take full width */
  }
  .date-picker-input {
      background-color: white; /* Ensure background is white */
      cursor: pointer;
  }
  
  .leave-request-form textarea {
    resize: vertical; /* Allow vertical resize */
  }
  
  .date-group {
      display: grid;
      grid-template-columns: 1fr 1fr; /* Two equal columns */
      gap: 1rem; /* Space between date pickers */
  }
  
  .leave-request-form button {
    display: block;
    width: 100%;
    padding: 0.8rem 1.5rem;
    background-color: #28a745; /* Green for submit */
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1.1rem;
    transition: background-color 0.2s ease;
    margin-top: 1rem;
  }
  
  .leave-request-form button:disabled {
    background-color: #ccc;
    cursor: not-allowed;
  }
  
  .leave-request-form button:hover:not(:disabled) {
    background-color: #218838;
  }
  
  /* Use styles similar to existing error/success messages */
  .error-message {
    color: #dc3545;
    background-color: #f8d7da;
    border: 1px solid #f5c6cb;
    padding: 0.75rem;
    border-radius: 4px;
    margin-bottom: 1.5rem;
    text-align: center;
  }
  
  .success-message {
    color: #155724;
    background-color: #d4edda;
    border: 1px solid #c3e6cb;
    padding: 0.75rem;
    border-radius: 4px;
    margin-bottom: 1.5rem;
    text-align: center;
  }
  
```

# frontend\src\components\LeaveRequestPage.js

```js
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import DatePicker from 'react-datepicker'; // Import date picker

import 'react-datepicker/dist/react-datepicker.css'; // Import date picker CSS
import './LeaveRequestPage.css'; // Create this CSS file

function LeaveRequestPage() {
  // State for form fields
  const [leaveTypes, setLeaveTypes] = useState([]);
  const [selectedLeaveTypeId, setSelectedLeaveTypeId] = useState('');
  const [fromDate, setFromDate] = useState(null); // Use null for date picker initial state
  const [toDate, setToDate] = useState(null);
  const [reason, setReason] = useState('');

  // State for UI feedback
  const [loadingLeaveTypes, setLoadingLeaveTypes] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Fetch leave types on component mount
  useEffect(() => {
    const fetchTypes = async () => {
      setLoadingLeaveTypes(true);
      setError(''); // Clear previous errors
      try {
        const response = await axios.get('/api/v1/leave-types'); // Use relative URL if base URL is set, or full URL
        setLeaveTypes(response.data || []);
        if (response.data && response.data.length > 0) {
          // Optionally set a default selection
          // setSelectedLeaveTypeId(response.data[0].id);
        }
      } catch (err) {
        console.error("Error fetching leave types:", err);
        setError("Could not load leave types. Please try again later.");
        // Handle auth error potentially
      } finally {
        setLoadingLeaveTypes(false);
      }
    };
    fetchTypes();
  }, []); // Run once on mount

  // Handle form submission
  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSuccessMessage('');

    // Basic validation
    if (!selectedLeaveTypeId || !fromDate || !toDate) {
      setError("Please select leave type and both dates.");
      return;
    }
    if (toDate < fromDate) {
      setError("The 'To Date' cannot be earlier than the 'From Date'.");
      return;
    }

    setIsSubmitting(true);

    // Format dates to YYYY-MM-DD string expected by backend 'date' type
    const formattedFromDate = fromDate.toISOString().split('T')[0];
    const formattedToDate = toDate.toISOString().split('T')[0];


    const payload = {
      leave_type_id: parseInt(selectedLeaveTypeId, 10), // Ensure it's an integer
      from_date: formattedFromDate,
      to_date: formattedToDate,
      note: reason,
    };

    try {
      console.log("Submitting leave request:", payload);
      const response = await axios.post('/api/v1/leave-request', payload);
      setSuccessMessage(response.data.message || "Leave request submitted successfully!");
      // Reset form after successful submission
      setSelectedLeaveTypeId('');
      setFromDate(null);
      setToDate(null);
      setReason('');
    } catch (err) {
      console.error("Error submitting leave request:", err);
      if (err.response && err.response.data && err.response.data.detail) {
         // Handle Pydantic validation errors or other specific errors
         if (Array.isArray(err.response.data.detail)) {
             const errorDetails = err.response.data.detail.map(d => `${d.loc[1]}: ${d.msg}`).join('; ');
             setError(`Submission failed: ${errorDetails}`);
         } else {
             setError(`Submission failed: ${err.response.data.detail}`);
         }
      } else {
        setError("Could not submit leave request. Please try again later.");
      }
       // Handle auth error potentially
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="leave-request-container">
      <h2>Request Time Off</h2>

      {loadingLeaveTypes && <p>Loading leave types...</p>}

      {error && <p className="error-message">{error}</p>}
      {successMessage && <p className="success-message">{successMessage}</p>}

      {!loadingLeaveTypes && (
        <form onSubmit={handleSubmit} className="leave-request-form">
          {/* Leave Type Dropdown */}
          <div className="form-group">
            <label htmlFor="leaveType">Leave Type:</label>
            <select
              id="leaveType"
              value={selectedLeaveTypeId}
              onChange={(e) => setSelectedLeaveTypeId(e.target.value)}
              required
              disabled={isSubmitting}
            >
              <option value="" disabled>-- Select Leave Type --</option>
              {leaveTypes.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.name}
                </option>
              ))}
            </select>
          </div>

          {/* Date Pickers */}
          <div className="form-group date-group">
             <div>
                <label htmlFor="fromDate">From Date:</label>
                <DatePicker
                  id="fromDate"
                  selected={fromDate}
                  onChange={(date) => setFromDate(date)}
                  selectsStart
                  startDate={fromDate}
                  endDate={toDate}
                  dateFormat="yyyy-MM-dd"
                  placeholderText="Select start date"
                  required
                  disabled={isSubmitting}
                  className="date-picker-input" // Add class for styling
                />
             </div>
             <div>
                <label htmlFor="toDate">To Date:</label>
                <DatePicker
                  id="toDate"
                  selected={toDate}
                  onChange={(date) => setToDate(date)}
                  selectsEnd
                  startDate={fromDate}
                  endDate={toDate}
                  minDate={fromDate} // Prevent selecting end date before start date
                  dateFormat="yyyy-MM-dd"
                  placeholderText="Select end date"
                  required
                  disabled={isSubmitting}
                   className="date-picker-input" // Add class for styling
                />
             </div>
          </div>

          {/* Reason Text Area */}
          <div className="form-group">
            <label htmlFor="reason">Reason (Optional):</label>
            <textarea
              id="reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows="4"
              disabled={isSubmitting}
            />
          </div>

          {/* Submit Button */}
          <button type="submit" disabled={isSubmitting || loadingLeaveTypes}>
            {isSubmitting ? 'Submitting...' : 'Submit Request'}
          </button>
        </form>
      )}
    </div>
  );
}

export default LeaveRequestPage;
```

# frontend\src\components\LoginPage.css

```css
.login-container {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 80vh; /* Center vertically */
  }
  
  .login-form {
    padding: 2rem;
    border: 1px solid #ccc;
    border-radius: 8px;
    background-color: #f9f9f9;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    width: 100%;
    max-width: 400px; /* Limit form width */
  }
  
  .login-form h2 {
    text-align: center;
    margin-bottom: 1.5rem;
    color: #333;
  }
  
  .form-group {
    margin-bottom: 1rem;
  }
  
  .form-group label {
    display: block;
    margin-bottom: 0.5rem;
    color: #555;
  }
  
  .form-group input {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    box-sizing: border-box; /* Include padding in width */
  }
  
  .login-form button {
    width: 100%;
    padding: 0.75rem;
    background-color: #007bff;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
    transition: background-color 0.2s ease;
  }
  
  .login-form button:disabled {
    background-color: #ccc;
    cursor: not-allowed;
  }
  
  .login-form button:hover:not(:disabled) {
    background-color: #0056b3;
  }
  
  .error-message {
    color: #dc3545; /* Red color for errors */
    background-color: #f8d7da;
    border: 1px solid #f5c6cb;
    padding: 0.75rem;
    border-radius: 4px;
    margin-bottom: 1rem;
    text-align: center;
  }
```

# frontend\src\components\LoginPage.js

```js
import React, { useState } from 'react';
import axios from 'axios';
import './LoginPage.css'; // We'll create this CSS file next

// This component receives a function 'onLoginSuccess' from its parent (App.js)
// It will call this function when login is successful, passing the token.
function LoginPage({ onLoginSuccess }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault(); // Prevent default form submission page reload
    setError(''); // Clear previous errors
    setLoading(true); // Show loading indicator

    // --- IMPORTANT: Use FormData for OAuth2PasswordRequestForm ---
    // FastAPI's OAuth2PasswordRequestForm expects form data, not JSON
    const formData = new FormData();
    formData.append('username', email); // 'username' is the expected field name
    formData.append('password', password);

    try {
      // Make POST request to the backend login endpoint
      const response = await axios.post(
        'http://127.0.0.1:8000/api/v1/login', // Your backend login URL
        formData,
        { // Set Content-Type header for form data
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        }
      );

      // Assuming the backend returns { access_token: "...", token_type: "bearer" }
      const token = response.data.access_token;

      if (token) {
        console.log('Login successful, token:', token);
        onLoginSuccess(token); // Call the parent function with the token
      } else {
         setError('Login failed: No token received.');
      }

    } catch (err) {
      console.error('Login error:', err);
      if (err.response && err.response.data && err.response.data.detail) {
        setError(`Login failed: ${err.response.data.detail}`); // Show backend error message
      } else {
        setError('Login failed. Please try again.'); // Generic error
      }
    } finally {
        setLoading(false); // Hide loading indicator
    }
  };

  return (
    <div className="login-container">
      <form onSubmit={handleSubmit} className="login-form">
        <h2>ESS Portal Login</h2>
        {error && <p className="error-message">{error}</p>}
        <div className="form-group">
          <label htmlFor="email">Email:</label>
          <input
            type="email"
            id="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            disabled={loading}
          />
        </div>
        <div className="form-group">
          <label htmlFor="password">Password:</label>
          <input
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            disabled={loading}
          />
        </div>
        <button type="submit" disabled={loading}>
          {loading ? 'Logging in...' : 'Login'}
        </button>
        {/* Add Forgot Password link later */}
      </form>
    </div>
  );
}

export default LoginPage;
```

# frontend\src\components\PayslipsPage.css

```css
.payslips-container {
    padding: 2rem;
    max-width: 900px; /* Wider for table */
    margin: 2rem auto;
    background-color: #ffffff;
    border-radius: 8px;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
  }
  
  .payslips-container.loading {
      text-align: center;
      padding: 3rem;
      font-size: 1.2rem;
      color: #555;
  }
  
  .payslips-container h2 {
    text-align: center;
    margin-top: 0;
    margin-bottom: 2rem;
    color: #333;
    border-bottom: 1px solid #eee;
    padding-bottom: 1rem;
  }
  
  /* Use styles similar to existing error messages */
  .payslips-container .error-message {
      color: #dc3545;
      background-color: #f8d7da;
      border: 1px solid #f5c6cb;
      padding: 0.75rem;
      border-radius: 4px;
      margin-bottom: 1.5rem;
      text-align: center;
  }
  
  
  .payslips-table {
    width: 100%;
    border-collapse: collapse; /* Remove space between borders */
    margin-top: 1.5rem;
  }
  
  .payslips-table th,
  .payslips-table td {
    border: 1px solid #e0e0e0;
    padding: 0.8rem 1rem;
    text-align: left;
    vertical-align: middle;
  }
  
  .payslips-table th {
    background-color: #f8f9fa; /* Light grey header */
    font-weight: bold;
    color: #444;
  }
  
  .payslips-table tbody tr:nth-child(even) {
    background-color: #fdfdfd; /* Slightly off-white for alternating rows */
  }
   .payslips-table tbody tr:hover {
      background-color: #f1f1f1; /* Highlight on hover */
   }
  
  
  /* Status Styling */
  .status {
      padding: 0.3rem 0.6rem;
      border-radius: 15px; /* Pill shape */
      font-size: 0.85rem;
      font-weight: bold;
      color: white;
      text-transform: capitalize;
  }
  
  .status-paid { background-color: #28a745; } /* Green */
  .status-draft { background-color: #ffc107; color: #333 } /* Yellow */
  .status-cancelled { background-color: #dc3545; } /* Red */
  /* Add other statuses as needed */
  
  
  .download-button {
      padding: 0.5rem 1rem;
      background-color: #007bff;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 0.9rem;
      transition: background-color 0.2s ease;
      white-space: nowrap; /* Prevent button text wrapping */
  }
  
  .download-button:disabled {
      background-color: #ccc;
      cursor: not-allowed;
      opacity: 0.7;
  }
  
  .download-button:hover:not(:disabled) {
      background-color: #0056b3;
  }
```

# frontend\src\components\PayslipsPage.js

```js
import React, { useState, useEffect } from 'react';
import axios from 'axios'; // Ensure axios is imported
import './PayslipsPage.css'; // Create this CSS file

function PayslipsPage() {
  const [payslips, setPayslips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [downloadingId, setDownloadingId] = useState(null); // Track which slip is downloading

  // Fetch payslips on component mount
  useEffect(() => {
    const fetchPayslips = async () => {
      setLoading(true);
      setError('');
      try {
        const response = await axios.get('/api/v1/payslips');
        setPayslips(response.data || []);
      } catch (err) {
        console.error("Error fetching payslips:", err);
        setError("Could not load payslip information. Please try again later.");
         // Handle auth error potentially
      } finally {
        setLoading(false);
      }
    };
    fetchPayslips();
  }, []);

  // Handle download click
  const handleDownload = async (payslipId) => {
      if (downloadingId) return; // Prevent multiple simultaneous downloads
      setDownloadingId(payslipId);
      setError(''); // Clear previous errors specifically for download

      try {
          // Make request to the download endpoint
          const response = await axios.get(`/api/v1/payslip/${payslipId}/download`, {
              responseType: 'blob', // Important: Expect binary data (even if it's text now)
          });

          // Create a URL for the blob data
          const url = window.URL.createObjectURL(new Blob([response.data]));
          const link = document.createElement('a');
          link.href = url;

          // Try to extract filename from Content-Disposition header
          const contentDisposition = response.headers['content-disposition'];
          let filename = `payslip_${payslipId}_download.pdf`; // Default filename
          if (contentDisposition) {
              const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i);
              if (filenameMatch && filenameMatch.length > 1) {
                  filename = filenameMatch[1];
              }
          }

          link.setAttribute('download', filename); // Set filename for download
          document.body.appendChild(link); // Append link to body
          link.click(); // Programmatically click the link to trigger download
          link.parentNode.removeChild(link); // Clean up the link
          window.URL.revokeObjectURL(url); // Release the blob URL

      } catch (err) {
          console.error(`Error downloading payslip ${payslipId}:`, err);
           if (err.response && err.response.status === 404) {
               setError(`Could not download payslip ${payslipId}: Not found or PDF not available.`);
           } else {
               setError(`Could not download payslip ${payslipId}. Please try again later.`);
           }
           // Handle auth error potentially
      } finally {
          setDownloadingId(null); // Reset downloading state
      }
  };


  if (loading) {
    return <div className="payslips-container loading">Loading Payslips...</div>;
  }

  if (error) {
    // Display error prominently, maybe above the list if it's a general fetch error
     return (
         <div className="payslips-container">
             <h2>My Payslips</h2>
             <p className="error-message">{error}</p>
         </div>
     );
  }

  return (
    <div className="payslips-container">
      <h2>My Payslips</h2>

      {/* Display specific download error here if needed */}
      {error && !loading && <p className="error-message">{error}</p>}

      {payslips.length === 0 ? (
        <p>No payslips found.</p>
      ) : (
        <table className="payslips-table">
          <thead>
            <tr>
              <th>Month</th>
              <th>Total Amount</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {payslips.map((slip) => (
              <tr key={slip.id}>
                <td>{slip.month}</td>
                {/* Format currency nicely - basic example */}
                <td>${slip.total.toFixed(2)}</td>
                <td>
                    <span className={`status status-${slip.status.toLowerCase()}`}>
                        {slip.status}
                    </span>
                </td>
                <td>
                  <button
                    onClick={() => handleDownload(slip.id)}
                    disabled={!slip.pdf_available || downloadingId === slip.id} // Disable if PDF not ready or during download
                    className="download-button"
                  >
                    {downloadingId === slip.id ? 'Downloading...' : 'Download PDF'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default PayslipsPage;
```

# frontend\src\components\ProfilePage.css

```css
.profile-container {
    padding: 2rem;
    max-width: 800px;
    margin: 2rem auto; /* Center the profile card */
    background-color: #ffffff;
    border-radius: 8px;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
  }
  
  .profile-container.loading,
  .profile-container.error {
    text-align: center;
    padding: 3rem;
    font-size: 1.2rem;
    color: #555;
  }
   .profile-container.error {
      color: #dc3545;
      background-color: #f8d7da;
      border: 1px solid #f5c6cb;
   }
  
  
  .profile-container h2 {
    margin-top: 0;
    margin-bottom: 2rem;
    color: #333;
    border-bottom: 1px solid #eee;
    padding-bottom: 1rem;
    text-align: center;
  }
  
  .profile-details {
    display: grid;
    /* Create two columns */
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1rem 2rem; /* Row gap and column gap */
    margin-bottom: 2rem;
  }
  
  .profile-field {
    display: flex;
    flex-direction: column; /* Stack label and value */
    padding: 0.5rem 0;
    border-bottom: 1px dashed #eee; /* Subtle separator */
  }
  
   .profile-field:last-child {
      border-bottom: none;
   }
  
  
  .field-label {
    font-weight: bold;
    color: #555;
    margin-bottom: 0.3rem;
    font-size: 0.9rem;
  }
  
  .field-value {
    color: #333;
    font-size: 1rem;
    word-wrap: break-word; /* Wrap long values */
  }
  
  .address-value {
    white-space: pre-wrap; /* Respect line breaks if any in address */
    line-height: 1.5;
  }
  
  .edit-button {
      display: block;
      margin: 1.5rem auto 0; /* Center button */
      padding: 0.75rem 1.5rem;
      background-color: #007bff;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 1rem;
      transition: background-color 0.2s ease;
  }
  .edit-button:hover {
      background-color: #0056b3;
  }
  
  .sync-note {
      text-align: center;
      color: #888;
      font-style: italic;
      font-size: 0.9rem;
      margin-top: 2rem;
  }
```

# frontend\src\components\ProfilePage.js

```js
import React, { useState, useEffect } from 'react';
import axios from 'axios'; // Make sure axios is imported
import './ProfilePage.css'; // We'll create this CSS file next

function ProfilePage() {
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchProfile = async () => {
      setLoading(true);
      setError('');
      try {
        // The auth token should already be set in axios defaults by App.js
        const response = await axios.get('http://127.0.0.1:8000/api/v1/users/me');
        setProfileData(response.data);
      } catch (err) {
        console.error("Error fetching profile data:", err);
        if (err.response && err.response.status === 401) {
             setError("Authentication error. Please log in again.");
             // Optionally redirect to login or trigger logout in App.js
        } else {
            setError("Could not load profile information. Please try again later.");
        }
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, []); // Empty dependency array means run only once on mount

  if (loading) {
    return <div className="profile-container loading">Loading Profile...</div>;
  }

  if (error) {
    return <div className="profile-container error">{error}</div>;
  }

  if (!profileData) {
    return <div className="profile-container">No profile data found.</div>; // Should ideally not happen if loading/error handled
  }

  // Display the profile data (read-only for now)
  return (
    <div className="profile-container">
      <h2>My Profile</h2>
      <div className="profile-details">
        <div className="profile-field">
          <span className="field-label">Full Name:</span>
          <span className="field-value">{profileData.full_name || 'N/A'}</span>
        </div>
        <div className="profile-field">
          <span className="field-label">Job Title:</span>
          <span className="field-value">{profileData.job_title || 'N/A'}</span>
        </div>
        <div className="profile-field">
          <span className="field-label">Work Email:</span>
          <span className="field-value">{profileData.email || 'N/A'}</span>
        </div>
        <div className="profile-field">
          <span className="field-label">Phone:</span>
          <span className="field-value">{profileData.phone || 'N/A'}</span>
        </div>
        <div className="profile-field">
          <span className="field-label">Department:</span>
          <span className="field-value">{profileData.department || 'N/A'}</span>
        </div>
        <div className="profile-field">
          <span className="field-label">Address:</span>
          {/* Address might be long, use a pre-wrap style */}
          <span className="field-value address-value">{profileData.address || 'N/A'}</span>
        </div>
      </div>
      {/* Add Edit button/logic later based on 'editable' requirement */}
      {/* <button className="edit-button">Edit Profile</button> */}
      <p className="sync-note">Profile data synced from HR System.</p>
    </div>
  );
}

export default ProfilePage;
```

# frontend\src\index.css

```css
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

code {
  font-family: source-code-pro, Menlo, Monaco, Consolas, 'Courier New',
    monospace;
}

```

# frontend\src\index.js

```js
import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import axios from 'axios'; // Import axios here

axios.defaults.baseURL = 'http://127.0.0.1:8000'; // Or http://localhost:8000 if that's your backend address

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();

```

# frontend\src\logo.svg

This is a file of the type: SVG Image

# frontend\src\reportWebVitals.js

```js
const reportWebVitals = onPerfEntry => {
  if (onPerfEntry && onPerfEntry instanceof Function) {
    import('web-vitals').then(({ getCLS, getFID, getFCP, getLCP, getTTFB }) => {
      getCLS(onPerfEntry);
      getFID(onPerfEntry);
      getFCP(onPerfEntry);
      getLCP(onPerfEntry);
      getTTFB(onPerfEntry);
    });
  }
};

export default reportWebVitals;

```

# frontend\src\setupTests.js

```js
// jest-dom adds custom jest matchers for asserting on DOM nodes.
// allows you to do things like:
// expect(element).toHaveTextContent(/react/i)
// learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom';

```

