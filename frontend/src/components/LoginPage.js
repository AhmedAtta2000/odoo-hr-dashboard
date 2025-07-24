// In frontend/src/components/LoginPage.js
import React, { useState } from 'react';
import axios from 'axios';
// import { Link as RouterLink, useNavigate } from 'react-router-dom';

// MUI Imports
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Link from '@mui/material/Link';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
// import IconButton from '@mui/material/IconButton';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Avatar from '@mui/material/Avatar';
import Paper from '@mui/material/Paper'; // <-- ENSURED IMPORT

// MUI Icons
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import LockResetIcon from '@mui/icons-material/LockReset';
import KeyIcon from '@mui/icons-material/Key'; // <-- ENSURED IMPORT



function LoginPage({ onLoginSuccess }) {
  // --- Sign In State ---
  const [signInEmail, setSignInEmail] = useState('');
  const [signInPassword, setSignInPassword] = useState('');
  const [signInError, setSignInError] = useState('');
  const [isSigningIn, setIsSigningIn] = useState(false);

  // --- Forgot Password State ---
  const [forgotPasswordEmail, setForgotPasswordEmail] = useState('');
  const [forgotPasswordMessage, setForgotPasswordMessage] = useState('');
  const [isRequestingReset, setIsRequestingReset] = useState(false);
  const [forgotPasswordIsError, setForgotPasswordIsError] = useState(false);

  // --- OTP State ---
  const [otpRequired, setOtpRequired] = useState(false);
  const [userEmailForOtp, setUserEmailForOtp] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [loadingOtp, setLoadingOtp] = useState(false);


  // State to control the active panel (false for Sign In, true for Forgot Password)
  const [isForgotPasswordActive, setIsForgotPasswordActive] = useState(false);
  // const navigate = useNavigate();


  const clearAllMessages = () => {
    setSignInError('');
    setForgotPasswordMessage('');
    setForgotPasswordIsError(false);
  };

  const handleSignInSubmit = async (event) => {
    event.preventDefault();
    clearAllMessages();
    setIsSigningIn(true);
    const formData = new FormData();
    formData.append('username', signInEmail);
    formData.append('password', signInPassword);
    try {
      const response = await axios.post('/api/v1/login', formData,
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      );
      if (response.data.otp_required) {
        setOtpRequired(true);
        setUserEmailForOtp(response.data.user_email);
        setSignInPassword(''); // Clear password
        setIsSigningIn(false);
      } else if (response.data.access_token && response.data.refresh_token) {
        onLoginSuccess(response.data);
      } else {
        setSignInError('Login failed: Invalid server response.');
        setIsSigningIn(false);
      }
    } catch (err) {
      console.error('Sign In error:', err);
      setSignInError(err.response?.data?.detail || 'Login failed. Check credentials.');
      setIsSigningIn(false);
    }
  };

  const handleOtpSubmit = async (event) => {
    event.preventDefault();
    clearAllMessages(); // Clear signInError specifically if it was set by password step
    setLoadingOtp(true);
    try {
      const response = await axios.post('/api/v1/auth/login-otp-verify', {
        email: userEmailForOtp, otp_code: otpCode,
      });
      if (response.data.access_token && response.data.refresh_token) {
        onLoginSuccess(response.data);
      } else {
        setSignInError('OTP Login failed: Invalid server response.'); // Re-use signInError for OTP step
      }
    } catch (err) {
      console.error('OTP Login error:', err);
      setSignInError(err.response?.data?.detail || 'OTP Login failed. Check code.'); // Re-use signInError
    } finally {
      setLoadingOtp(false);
    }
  };


  const handleForgotPasswordSubmit = async (event) => {
    event.preventDefault();
    clearAllMessages();
    setIsRequestingReset(true);
    try {
      const response = await axios.post('/api/v1/auth/request-password-reset', { email: forgotPasswordEmail });
      setForgotPasswordMessage(response.data.message || "Reset instructions sent if email is valid.");
      setForgotPasswordIsError(false);
      setForgotPasswordEmail('');
    } catch (err) {
      console.error("Error requesting password reset:", err);
      setForgotPasswordMessage(err.response?.data?.detail || "Failed to send reset instructions.");
      setForgotPasswordIsError(true);
    } finally {
      setIsRequestingReset(false);
    }
  };

  const commonInputStyles = { bgcolor: '#eee', border: 'none', borderRadius: '8px', width: '100%' };
  const formSubmitButtonStyles = {
    bgcolor: 'primary.main', color: '#fff', padding: '10px 45px', border: '1px solid transparent',
    borderRadius: '8px', fontWeight: 600, letterSpacing: '0.5px', textTransform: 'uppercase',
    marginTop: '10px', '&:hover': { bgcolor: 'primary.dark' },
  };
  const overlayButtonStyles = {
    ...formSubmitButtonStyles, bgcolor: 'transparent', borderColor: '#fff', borderWidth: '1px', borderStyle: 'solid',
    '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.1)' },
  };

  if (otpRequired) {
    return (
        <Box sx={{ bgcolor: (theme) => theme.palette.background.default, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', minHeight: '100vh', py: 4 }}>
            <Container component="main" maxWidth="xs"> {/* Ensure Container is wrapping */}
                <Paper elevation={3} sx={{ padding: 4, display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%' }}>
                    <Avatar sx={{ m: 1, bgcolor: 'primary.main' }}><KeyIcon /></Avatar> {/* KeyIcon for OTP */}
                    <Typography component="h1" variant="h5" sx={{ mb: 1 }}>Two-Factor Authentication</Typography>
                    <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 2 }}>
                        Enter the code from your authenticator app for {userEmailForOtp}.
                    </Typography>
                    <Box component="form" onSubmit={handleOtpSubmit} noValidate sx={{ mt: 1, width: '100%' }}>
                        {signInError && <Alert severity="error" sx={{ width: '100%', mb: 2 }}>{signInError}</Alert>}
                        <TextField margin="normal" required fullWidth name="otpCode" label="OTP Code" type="text" id="otpCode" autoFocus value={otpCode} onChange={(e) => setOtpCode(e.target.value)} disabled={loadingOtp} error={!!signInError} inputProps={{ maxLength: 6, pattern: "[0-9]*" }} />
                        <Button type="submit" fullWidth variant="contained" sx={{ mt: 3, mb: 2 }} disabled={loadingOtp}>
                            {loadingOtp ? <CircularProgress size={24} color="inherit" /> : 'Verify Code'}
                        </Button>
                        <Box sx={{ textAlign: 'center' }}>
                            <Link component="button" variant="body2" onClick={() => { setOtpRequired(false); clearAllMessages(); }} sx={{ cursor: 'pointer' }}>
                                Back to password entry
                            </Link>
                        </Box>
                    </Box>
                </Paper>
            </Container>
        </Box>
    );
  }


  return (
    <Box sx={{ bgcolor: (theme) => theme.palette.background.default, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', minHeight: '100vh', py: 4 }}>
      <Container // Main container for the animated form
        maxWidth={false} // Allow it to be wider
        disableGutters // Remove default padding
        sx={{
          bgcolor: '#fff', borderRadius: '30px', boxShadow: '0 5px 15px rgba(0, 0, 0, 0.35)',
          position: 'relative', overflow: 'hidden', width: { xs: '90%', sm: '768px' },
          maxWidth: '100%', minHeight: '480px',
        }}
      >
        {/* Request Password Reset Form Panel (replaces Sign-Up) */}
        <Box
          sx={{
            position: 'absolute', top: 0, height: '100%',
            left: 0, width: '50%',
            opacity: isForgotPasswordActive ? 1 : 0,
            zIndex: isForgotPasswordActive ? 5 : 1,
            transform: isForgotPasswordActive ? 'translateX(100%)' : 'translateX(0%)',
            transition: 'all 0.6s ease-in-out',
            display: 'flex', alignItems: 'center', justifyContent: 'center', // Center content
          }}
        >
          <Box component="form" onSubmit={handleForgotPasswordSubmit} sx={{ width: '100%', padding: '0 40px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <Avatar sx={{ m: 1, bgcolor: 'primary.main' }}><LockResetIcon /></Avatar>
            <Typography component="h1" variant="h5" sx={{ fontWeight: 'bold', mb: 1 }}>Forgot Password?</Typography>
            {forgotPasswordMessage && <Alert severity={forgotPasswordIsError ? 'error' : 'success'} sx={{ width: '100%', my: 1, fontSize: '0.8rem', p: '2px 8px' }}>{forgotPasswordMessage}</Alert>}
            <Typography variant="caption" sx={{ fontSize: '12px', mb: 1, textAlign: 'center' }}>Enter your email to receive a reset link.</Typography>
            <TextField
              placeholder="Email" type="email" variant="filled" size="small"
              sx={commonInputStyles} value={forgotPasswordEmail}
              onChange={(e) => setForgotPasswordEmail(e.target.value)}
              disabled={isRequestingReset} required autoFocus fullWidth
            />
            <Button type="submit" sx={formSubmitButtonStyles} disabled={isRequestingReset}>
              {isRequestingReset ? <CircularProgress size={24} sx={{ color: 'white' }} /> : 'Send Reset Link'}
            </Button>
          </Box>
        </Box>

        {/* Sign-In Form Panel */}
        <Box
          sx={{
            position: 'absolute', top: 0, height: '100%',
            left: 0, width: '50%', zIndex: 2,
            opacity: isForgotPasswordActive ? 0 : 1,
            transform: isForgotPasswordActive ? 'translateX(100%)' : 'translateX(0%)',
            transition: 'all 0.6s ease-in-out',
            display: 'flex', alignItems: 'center', justifyContent: 'center', // Center content
          }}
        >
          <Box component="form" onSubmit={handleSignInSubmit} sx={{ width: '100%', padding: '0 40px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <Avatar sx={{ m: 1, bgcolor: 'secondary.main' }}><LockOutlinedIcon /></Avatar>
            <Typography component="h1" variant="h5" sx={{ fontWeight: 'bold', mb: 1 }}>Sign In</Typography>
            {signInError && <Alert severity="error" sx={{ width: '100%', mb: 1, fontSize: '0.8rem', p: '2px 8px' }}>{signInError}</Alert>}
            <TextField placeholder="Email" type="email" variant="filled" size="small" sx={commonInputStyles} value={signInEmail} onChange={(e) => setSignInEmail(e.target.value)} disabled={isSigningIn} required autoFocus fullWidth />
            <TextField placeholder="Password" type="password" variant="filled" size="small" sx={{...commonInputStyles, mt:1}} value={signInPassword} onChange={(e) => setSignInPassword(e.target.value)} disabled={isSigningIn} required fullWidth />
            <Button type="submit" sx={formSubmitButtonStyles} disabled={isSigningIn}>
              {isSigningIn ? <CircularProgress size={24} sx={{ color: 'white' }} /> : 'Sign In'}
            </Button>
          </Box>
        </Box>

        {/* Toggle Container */}
        <Box
          sx={{
            position: 'absolute', top: 0, left: '50%', width: '50%', height: '100%',
            overflow: 'hidden', zIndex: 100, transition: 'all 0.6s ease-in-out',
            transform: isForgotPasswordActive ? 'translateX(-100%)' : 'translateX(0)',
          }}
        >
          <Box
            sx={{
              bgcolor: 'primary.main', color: '#fff', position: 'relative',
              left: '-100%', height: '100%', width: '200%',
              transform: isForgotPasswordActive ? 'translateX(50%)' : 'translateX(0)',
              transition: 'all 0.6s ease-in-out',
              display: 'flex', // Added to help child Box components center
            }}
          >
            {/* Toggle Left Panel (Now prompts "Back to Sign In?") */}
            <Box
              sx={{
                width: '50%', height: '100%', // Takes half of its 200% width parent
                display: 'flex', justifyContent: 'center', alignItems: 'center', flexDirection: 'column',
                padding: '0 30px', textAlign: 'center',
                transform: isForgotPasswordActive ? 'translateX(0)' : 'translateX(-100%)', // Adjusted based on parent's transform
                transition: 'all 0.6s ease-in-out',
              }}
            >
              <Typography component="h1" variant="h5" sx={{ fontWeight: 'bold', mb: 1 }}>Already With Us?</Typography>
              <Typography variant="body2" sx={{ fontSize: '14px', lineHeight: '20px', letterSpacing: '0.3px', margin: '15px 0' }}>
                If you remember your password, just sign in.
              </Typography>
              <Button sx={overlayButtonStyles} onClick={() => {setIsForgotPasswordActive(false); clearAllMessages();}}>
                Sign In
              </Button>
            </Box>

            {/* Toggle Right Panel (Now prompts "Forgot Password?") */}
            <Box
              sx={{
                width: '50%', height: '100%',  // Takes half of its 200% width parent
                display: 'flex', justifyContent: 'center', alignItems: 'center', flexDirection: 'column',
                padding: '0 30px', textAlign: 'center',
                transform: isForgotPasswordActive ? 'translateX(100%)' : 'translateX(0)', // Adjusted
                transition: 'all 0.6s ease-in-out',
              }}
            >
              <Typography component="h1" variant="h5" sx={{ fontWeight: 'bold', mb: 1 }}>Can't Sign In?</Typography>
              <Typography variant="body2" sx={{ fontSize: '14px', lineHeight: '20px', letterSpacing: '0.3px', margin: '15px 0' }}>
                No problem! Click here to reset your password.
              </Typography>
              <Button sx={overlayButtonStyles} onClick={() => {setIsForgotPasswordActive(true); clearAllMessages();}}>
                Forgot Password?
              </Button>
            </Box>
          </Box>
        </Box>
      </Container>
    </Box>
  );
}

export default LoginPage;