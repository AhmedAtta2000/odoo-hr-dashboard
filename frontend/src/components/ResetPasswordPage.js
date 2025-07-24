// In frontend/src/components/ResetPasswordPage.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate, useSearchParams, Link as RouterLink } from 'react-router-dom';

// MUI Imports
import Avatar from '@mui/material/Avatar';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Link from '@mui/material/Link';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import Paper from '@mui/material/Paper';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import LockResetIcon from '@mui/icons-material/LockReset'; // Or a different icon like VpnKeyIcon

// Removed: import './ResetPasswordPage.css';

function ResetPasswordPage() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();

    const [urlToken, setUrlToken] = useState(''); // Store the token from URL
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [message, setMessage] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isError, setIsError] = useState(false);
    const [showForm, setShowForm] = useState(false); // Control form visibility based on token validity

    useEffect(() => {
        const resetTokenFromUrl = searchParams.get('token');
        if (resetTokenFromUrl) {
            setUrlToken(resetTokenFromUrl);
            setShowForm(true); // Token found, show the form
            setMessage(''); // Clear any initial messages
            setIsError(false);
        } else {
            setIsError(true);
            setMessage("Password reset link is invalid or token is missing. Please request a new one.");
            setShowForm(false); // No token, don't show the form
        }
    }, [searchParams]);

    const handleSubmit = async (event) => {
        event.preventDefault();
        setMessage(''); // Clear previous messages
        setIsError(false);

        if (!urlToken) { // Should not happen if form is shown, but as a safeguard
            setIsError(true);
            setMessage("Password reset token is missing.");
            return;
        }
        if (newPassword !== confirmPassword) {
            setIsError(true);
            setMessage("Passwords do not match.");
            return;
        }
        if (newPassword.length < 8) { // Basic password length validation
            setIsError(true);
            setMessage("Password must be at least 8 characters long.");
            return;
        }

        setIsSubmitting(true);

        try {
            const response = await axios.post('/api/v1/auth/reset-password', {
                token: urlToken,
                new_password: newPassword
            });
            setIsError(false); // Success
            setMessage(response.data.message || "Password has been reset successfully!");
            setShowForm(false); // Hide form on success
            setTimeout(() => {
                navigate('/login', { state: { message: "Password reset successful. Please log in with your new password." }});
            }, 3000);
        } catch (err) {
            console.error("Error resetting password:", err);
            setIsError(true);
            if (err.response && err.response.data && err.response.data.detail) {
                setMessage(`${err.response.data.detail}`);
            } else {
                setMessage("Failed to reset password. The link may have expired or already been used.");
            }
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <Container component="main" maxWidth="xs" sx={{ mt: 8, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <Paper elevation={3} sx={{ padding: 4, display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%' }}>
                <Avatar sx={{ m: 1, bgcolor: 'primary.main' }}>
                    <LockResetIcon />
                </Avatar>
                <Typography component="h1" variant="h5" sx={{ mb: 2 }}>
                    Reset Your Password
                </Typography>

                {message && (
                    <Alert severity={isError ? 'error' : 'success'} sx={{ width: '100%', mb: 2 }}>
                        {message}
                    </Alert>
                )}

                {showForm && !isError && !(message && !isError) && ( // Show form if token valid and no success message yet
                    <Box component="form" onSubmit={handleSubmit} noValidate sx={{ width: '100%' }}>
                        <TextField
                            margin="normal"
                            required
                            fullWidth
                            name="newPassword"
                            label="New Password"
                            type="password"
                            id="newPassword"
                            value={newPassword}
                            onChange={(e) => setNewPassword(e.target.value)}
                            disabled={isSubmitting}
                            error={isError && !!newPassword} // Basic error indication
                        />
                        <TextField
                            margin="normal"
                            required
                            fullWidth
                            name="confirmPassword"
                            label="Confirm New Password"
                            type="password"
                            id="confirmPassword"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            disabled={isSubmitting}
                            error={isError && !!confirmPassword && newPassword !== confirmPassword}
                        />
                        <Button
                            type="submit"
                            fullWidth
                            variant="contained"
                            sx={{ mt: 3, mb: 2 }}
                            disabled={isSubmitting || !urlToken}
                        >
                            {isSubmitting ? <CircularProgress size={24} color="inherit" /> : 'Set New Password'}
                        </Button>
                    </Box>
                )}

                {(!showForm || (message && !isError)) && ( // If form not shown, or success message shown
                     <Box sx={{ textAlign: 'center', mt: 2 }}>
                        <Link component={RouterLink} to="/login" variant="body2">
                            Back to Sign In
                        </Link>
                        {isError && !urlToken && // If initial token error
                            <Typography variant="body2" sx={{mt:1}}>
                                <Link component={RouterLink} to="/request-password-reset">
                                    Request a new reset link
                                </Link>
                            </Typography>
                        }
                    </Box>
                )}
            </Paper>
            <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 5 }}>
                {'Copyright © '}
                <Link color="inherit" href="#">
                    Your Company
                </Link>{' '}
                {new Date().getFullYear()}
                {'.'}
            </Typography>
        </Container>
    );
}

export default ResetPasswordPage;