// In frontend/src/components/RequestPasswordResetPage.js
import React, { useState } from 'react';
import axios from 'axios';
import { Link as RouterLink } from 'react-router-dom';

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
import LockResetIcon from '@mui/icons-material/LockReset'; // Icon for password reset

// Removed: import './RequestPasswordResetPage.css';

function RequestPasswordResetPage() {
    const [email, setEmail] = useState('');
    const [message, setMessage] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isError, setIsError] = useState(false);

    const handleSubmit = async (event) => {
        event.preventDefault();
        setIsSubmitting(true);
        setMessage('');
        setIsError(false);

        try {
            const response = await axios.post('/api/v1/auth/request-password-reset', { email });
            setMessage(response.data.message || "If an account with that email exists, instructions to reset your password have been sent.");
            setIsError(false); // Explicitly set no error on success
            setEmail(''); // Clear email field on success
        } catch (err) {
            console.error("Error requesting password reset:", err);
            setIsError(true);
            if (err.response && err.response.data && err.response.data.detail) {
                setMessage(`${err.response.data.detail}`); // Use backticks for consistency
            } else {
                setMessage("An error occurred. Please try again later.");
            }
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <Container component="main" maxWidth="xs" sx={{ mt: 8, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <Paper elevation={3} sx={{ padding: 4, display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%' }}>
                <Avatar sx={{ m: 1, bgcolor: 'primary.main' }}> {/* Use theme primary color */}
                    <LockResetIcon />
                </Avatar>
                <Typography component="h1" variant="h5" sx={{ mb: 1 }}>
                    Forgot Password?
                </Typography>
                <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 3 }}>
                    No worries! Enter your email address below and we'll send you a link to reset your password.
                </Typography>

                {message && (
                    <Alert severity={isError ? 'error' : 'success'} sx={{ width: '100%', mb: 2 }}>
                        {message}
                    </Alert>
                )}

                <Box component="form" onSubmit={handleSubmit} noValidate sx={{ width: '100%' }}>
                    <TextField
                        margin="normal"
                        required
                        fullWidth
                        id="email"
                        label="Email Address"
                        name="email"
                        autoComplete="email"
                        autoFocus
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        disabled={isSubmitting}
                        error={isError && !!email} // Optionally highlight on error if email was entered
                    />
                    <Button
                        type="submit"
                        fullWidth
                        variant="contained"
                        sx={{ mt: 2, mb: 2 }}
                        disabled={isSubmitting}
                    >
                        {isSubmitting ? <CircularProgress size={24} color="inherit" /> : 'Send Password Reset Link'}
                    </Button>
                    <Box sx={{ textAlign: 'center' }}>
                        <Link component={RouterLink} to="/login" variant="body2">
                            Back to Sign In
                        </Link>
                    </Box>
                </Box>
            </Paper>
            <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 5 }}>
                {'Copyright © '}
                <Link color="inherit" href="#"> {/* Replace with your website later */}
                    Your Company
                </Link>{' '}
                {new Date().getFullYear()}
                {'.'}
            </Typography>
        </Container>
    );
}

export default RequestPasswordResetPage;