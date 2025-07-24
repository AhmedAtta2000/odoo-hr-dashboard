// In frontend/src/App.js
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { BrowserRouter as Router, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';

// MUI Imports
import Alert from '@mui/material/Alert';
import Container from '@mui/material/Container'; // If using for global error display

// Page Components
import LoginPage from './components/LoginPage';
import DashboardPage from './components/DashboardPage';
import ProfilePage from './components/ProfilePage';
import LeaveRequestPage from './components/LeaveRequestPage';
import PayslipsPage from './components/PayslipsPage';
import ExpensesPage from './components/ExpensesPage';
import DocumentsPage from './components/DocumentsPage';
import AttendancePage from './components/AttendancePage';
import AdminTenantConfigPage from './components/AdminTenantConfigPage';
import RequestPasswordResetPage from './components/RequestPasswordResetPage';
import ResetPasswordPage from './components/ResetPasswordPage';
import AdminUsersPage from './components/AdminUsersPage'; // <-- IMPORT AdminUsersPage

import './App.css'; // Your main App CSS

// ProtectedRoute Helper (remains the same)
function ProtectedRoute({ children, isLoggedIn, isAdminRoute = false, isUserAdmin = false }) {
  const location = useLocation();
  if (!isLoggedIn) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  if (isAdminRoute && !isUserAdmin) {
    return <Navigate to="/dashboard" state={{ message: "Access Denied: Administrator access required." }} replace />;
  }
  return children;
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('authToken'));
  const [userData, setUserData] = useState(null);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);
  const [authError, setAuthError] = useState('');

  const handleLogout = useCallback(() => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('refreshToken');
    setToken(null);
    setUserData(null);
    delete axios.defaults.headers.common['Authorization'];
    console.log("User logged out from App.js");
  }, []);

  useEffect(() => {
    const fetchUserData = async (currentToken) => {
      if (!currentToken) {
        setUserData(null); setIsLoadingAuth(false); return;
      }
      setIsLoadingAuth(true); setAuthError('');
      try {
        axios.defaults.headers.common['Authorization'] = `Bearer ${currentToken}`;
        const response = await axios.get('/api/v1/users/me');
        setUserData(response.data);
      } catch (err) {
        console.error("Error fetching user data (useEffect[token]):", err);
        if (err.response && err.response.status === 401) {
          setAuthError("Your session may have expired. Please log in again.");
        } else {
          setAuthError("Could not fetch user data.");
        }
        handleLogout();
      } finally {
        setIsLoadingAuth(false);
      }
    };

    if (token) {
      fetchUserData(token);
    } else {
      delete axios.defaults.headers.common['Authorization'];
      setUserData(null);
      setIsLoadingAuth(false);
    }
  }, [token, handleLogout]);

  const handleLoginSuccess = (loginData) => {
    localStorage.setItem('authToken', loginData.access_token);
    localStorage.setItem('refreshToken', loginData.refresh_token);
    setToken(loginData.access_token);
  };

  if (isLoadingAuth && token) {
    return <div className="loading-fullscreen">Authenticating...</div>;
  }

  return (
    <Router>
      <div className="App">
        {/* Using the original header structure from App.js */}
        {token && userData && (
          <header className="app-header"> {/* Your existing app-header class */}
            <div className="header-content"> {/* Your existing header-content class */}
              <span>Welcome, {userData.full_name}! {userData.is_admin && <strong style={{color: 'orange'}}>(Admin)</strong>}</span>
              <nav>
                <Link to="/dashboard">Dashboard</Link>
                <Link to="/profile">My Profile</Link>
                <Link to="/leave-request">Request Leave</Link>
                <Link to="/payslips">Payslips</Link>
                <Link to="/expenses">Submit Expense</Link>
                <Link to="/documents">Documents</Link>
                <Link to="/attendance">Attendance</Link>
                {userData.is_admin && (
                  <>
                    <Link to="/admin/tenants" style={{ color: 'orange', fontWeight: 'bold', marginLeft: '15px' }}>Tenant Config</Link>
                    {/* --- ADDED LINK FOR SAAS USER MANAGEMENT --- */}
                    <Link to="/admin/users" style={{ color: 'lightgreen', fontWeight: 'bold', marginLeft: '15px' }}>Manage Users</Link>
                    {/* ------------------------------------------ */}
                  </>
                )}
              </nav>
              <button onClick={handleLogout} className="logout-button">Logout</button>
            </div>
          </header>
        )}

        <main className="app-main-content"> {/* Add your main content class if you have one */}
          {authError && !token && (
            <Container maxWidth="sm" sx={{mt:2}}>
                <Alert severity="error" sx={{ width: '100%' }}>{authError}</Alert>
            </Container>
          )}

          <Routes>
            {/* Public Routes */}
            <Route
              path="/login"
              element={!token ? <LoginPage onLoginSuccess={handleLoginSuccess} /> : <Navigate to="/dashboard" replace />}
            />
            <Route path="/request-password-reset" element={<RequestPasswordResetPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />

            {/* Protected Employee Routes */}
            <Route path="/dashboard" element={<ProtectedRoute isLoggedIn={!!token && !!userData}><DashboardPage userData={userData} /></ProtectedRoute>} />
            <Route path="/profile" element={<ProtectedRoute isLoggedIn={!!token && !!userData}><ProfilePage /></ProtectedRoute>} />
            <Route path="/leave-request" element={<ProtectedRoute isLoggedIn={!!token && !!userData}><LeaveRequestPage /></ProtectedRoute>} />
            <Route path="/payslips" element={<ProtectedRoute isLoggedIn={!!token && !!userData}><PayslipsPage /></ProtectedRoute>} />
            <Route path="/expenses" element={<ProtectedRoute isLoggedIn={!!token && !!userData}><ExpensesPage /></ProtectedRoute>} />
            <Route path="/documents" element={<ProtectedRoute isLoggedIn={!!token && !!userData}><DocumentsPage /></ProtectedRoute>} />
            <Route path="/attendance" element={<ProtectedRoute isLoggedIn={!!token && !!userData}><AttendancePage /></ProtectedRoute>} />

            {/* Protected Admin Routes */}
            <Route
              path="/admin/tenants"
              element={
                <ProtectedRoute isLoggedIn={!!token && !!userData} isAdminRoute={true} isUserAdmin={!!userData?.is_admin}>
                  <AdminTenantConfigPage />
                </ProtectedRoute>
              }
            />
            {/* --- ADDED ROUTE FOR SAAS USER MANAGEMENT --- */}
            <Route
              path="/admin/users"
              element={
                <ProtectedRoute isLoggedIn={!!token && !!userData} isAdminRoute={true} isUserAdmin={!!userData?.is_admin}>
                  <AdminUsersPage />
                </ProtectedRoute>
              }
            />
            {/* ----------------------------------------- */}

            {/* Default Route */}
            <Route
              path="*"
              element={token && userData ? <Navigate to="/dashboard" replace /> : <Navigate to="/login" replace />}
            />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;