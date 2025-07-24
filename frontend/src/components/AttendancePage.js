// In frontend/src/components/AttendancePage.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';

// MUI Imports
import Container from '@mui/material/Container';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import Divider from '@mui/material/Divider';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import AccessTimeIcon from '@mui/icons-material/AccessTime'; // For current status
import HistoryIcon from '@mui/icons-material/History'; // For log

// Removed: import './AttendancePage.css';

function AttendancePage() {
  const [attendanceStatus, setAttendanceStatus] = useState(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [isProcessingAction, setIsProcessingAction] = useState(false);
  const [actionError, setActionError] = useState('');

  const [todaysLog, setTodaysLog] = useState([]);
  const [loadingLog, setLoadingLog] = useState(true);
  const [logError, setLogError] = useState('');

  const fetchCurrentStatus = async () => {
    setLoadingStatus(true); setActionError('');
    try {
      const response = await axios.get('/api/v1/attendance/status');
      setAttendanceStatus(response.data || { status: 'unknown', message: 'Could not determine status.' });
    } catch (err) {
      console.error("Error fetching current attendance status:", err);
      setActionError("Could not load current attendance status.");
      setAttendanceStatus({ status: 'error', message: 'Error loading status.' });
    } finally { setLoadingStatus(false); }
  };

  const fetchTodaysLog = async () => {
    setLoadingLog(true); setLogError('');
    try {
      const response = await axios.get('/api/v1/attendance/today-log');
      setTodaysLog(response.data.attendance_log || []);
      if (response.data.message && (!response.data.attendance_log || response.data.attendance_log.length === 0)) {
        setLogError(response.data.message);
      }
    } catch (err) {
      console.error("Error fetching today's attendance log:", err);
      setLogError("Could not load today's attendance log.");
      setTodaysLog([]);
    } finally { setLoadingLog(false); }
  };

  useEffect(() => {
    fetchCurrentStatus();
    fetchTodaysLog();
  }, []);

  const handleAttendanceAction = async () => {
    if (!attendanceStatus || isProcessingAction) return;
    const action = attendanceStatus.status === 'checked_out' ? 'check-in' : 'check-out';
    const endpoint = `/api/v1/attendance/${action}`;
    setIsProcessingAction(true); setActionError('');
    try {
      const response = await axios.post(endpoint);
      setAttendanceStatus(response.data);
      await fetchTodaysLog(); // Refresh log
      // await fetchCurrentStatus(); // Status is updated by response.data, but can refresh if needed
    } catch (err) {
      console.error(`Error during ${action}:`, err);
      if (err.response && err.response.data && err.response.data.detail) {
        setActionError(`${err.response.data.detail}`);
      } else { setActionError(`Could not perform ${action}. Please try again.`); }
    } finally { setIsProcessingAction(false); }
  };

  const getButtonProps = () => {
    if (!attendanceStatus || attendanceStatus.status === 'error' || attendanceStatus.status === 'unknown') {
       return { text: 'Status Unavailable', disabled: true, color: 'inherit' };
    }
    if (attendanceStatus.status === 'checked_out') {
      return { text: 'Check In', disabled: isProcessingAction, color: 'success' }; // Green for Check In
    }
    if (attendanceStatus.status === 'checked_in') {
       return { text: 'Check Out', disabled: isProcessingAction, color: 'error' }; // Red for Check Out
    }
    return { text: '...', disabled: true, color: 'inherit' };
  };
  const buttonProps = getButtonProps();

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
      <Paper elevation={3} sx={{ padding: { xs: 2, sm: 3 } }}>
        <Typography variant="h4" component="h1" gutterBottom align="center" sx={{display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            <AccessTimeIcon sx={{mr: 1, fontSize: '2rem'}} color="primary" /> Attendance
        </Typography>
        <Divider sx={{ my: 2 }} />

        {/* Current Status and Action Button */}
        <Box className="status-display-box" sx={{ textAlign: 'center', mb: 3, p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
          <Typography variant="h6" gutterBottom>Current Status</Typography>
          {loadingStatus ? (
            <CircularProgress size={24} />
          ) : (
            <>
              {actionError && <Alert severity="error" sx={{ mb: 2 }}>{actionError}</Alert>}
              {attendanceStatus && attendanceStatus.message && (
                <Typography
                    variant="subtitle1"
                    color={attendanceStatus.status === 'checked_in' ? 'error.main' : attendanceStatus.status === 'checked_out' ? 'success.main' : 'text.secondary'}
                    sx={{ fontWeight: 'medium', mb: 2 }}
                >
                  {attendanceStatus.message}
                </Typography>
              )}
              <Button
                onClick={handleAttendanceAction}
                disabled={buttonProps.disabled || loadingStatus}
                variant="contained"
                color={buttonProps.color}
                size="large"
                sx={{ minWidth: '150px' }}
              >
                {isProcessingAction ? <CircularProgress size={24} color="inherit" /> : buttonProps.text}
              </Button>
            </>
          )}
        </Box>

        {/* Today's Attendance Log Section */}
        <Box className="today-log-box">
          <Typography variant="h6" gutterBottom sx={{display: 'flex', alignItems: 'center'}}>
            <HistoryIcon sx={{mr: 1}} color="action"/> Today's Log
          </Typography>
          {loadingLog ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 2 }}><CircularProgress size={24} /></Box>
          ) : logError ? (
            <Alert severity="warning" sx={{mt: 1}}>{logError}</Alert> // Warning for "Not linked" or "No records"
          ) : todaysLog.length > 0 ? (
            <List dense sx={{ bgcolor: 'background.paper', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
              {todaysLog.map((logEntry, index) => (
                <React.Fragment key={logEntry.id}>
                  <ListItem>
                    <ListItemText
                      primary={
                        <Typography component="span" variant="body2">
                          <strong>In:</strong> {logEntry.check_in || '--:--:--'}
                          <Box component="span" sx={{ mx: 1 }}>|</Box>
                          <strong>Out:</strong> {logEntry.check_out || '--:--:--'}
                        </Typography>
                      }
                      secondary={logEntry.worked_hours !== null ? `Hours: ${logEntry.worked_hours.toFixed(2)}` : 'Duration pending...'}
                    />
                  </ListItem>
                  {index < todaysLog.length - 1 && <Divider component="li" />}
                </React.Fragment>
              ))}
            </List>
          ) : (
            <Typography variant="body2" color="text.secondary" sx={{mt:1, fontStyle: 'italic'}}>No attendance records for today.</Typography>
          )}
        </Box>
      </Paper>
    </Container>
  );
}

export default AttendancePage;