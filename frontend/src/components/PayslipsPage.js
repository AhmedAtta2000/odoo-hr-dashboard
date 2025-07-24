// In frontend/src/components/PayslipsPage.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';

// MUI Imports
import Container from '@mui/material/Container';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import DownloadIcon from '@mui/icons-material/Download'; // Icon for download button
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong'; // Icon for page title


// Removed: import './PayslipsPage.css';

function PayslipsPage() {
  const [payslips, setPayslips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [downloadingId, setDownloadingId] = useState(null);

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
        setPayslips([]); // Clear on error
      } finally {
        setLoading(false);
      }
    };
    fetchPayslips();
  }, []);

  const handleDownload = async (payslipId, filenameFromOdoo) => {
      if (downloadingId) return;
      setDownloadingId(payslipId);
      setError(''); // Clear general errors, specific download errors handled below

      try {
          const response = await axios.get(`/api/v1/payslip/${payslipId}/download`, {
              responseType: 'blob',
          });
          const url = window.URL.createObjectURL(new Blob([response.data]));
          const link = document.createElement('a');
          link.href = url;

          // Use filename from Odoo's Content-Disposition if available, else construct one
          const contentDisposition = response.headers['content-disposition'];
          let filename = filenameFromOdoo || `payslip_${payslipId}.pdf`; // Fallback filename
          if (contentDisposition) {
              const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i);
              if (filenameMatch && filenameMatch.length > 1) {
                  filename = filenameMatch[1];
              }
          }
          link.setAttribute('download', filename);
          document.body.appendChild(link);
          link.click();
          link.parentNode.removeChild(link);
          window.URL.revokeObjectURL(url);
      } catch (err) {
          console.error(`Error downloading payslip ${payslipId}:`, err);
          let downloadErrorMsg = `Could not download payslip ${payslipId}. `;
          if (err.response && err.response.data) {
              // Try to parse error from blob if it's JSON (some APIs might return JSON error for blob request)
              try {
                  const errorJson = JSON.parse(await err.response.data.text());
                  downloadErrorMsg += errorJson.detail || 'Please try again later.';
              } catch (parseError) {
                  downloadErrorMsg += 'Please try again later.';
              }
          } else {
            downloadErrorMsg += 'Network or server error.';
          }
          setError(downloadErrorMsg); // Set general error state for display
      } finally {
          setDownloadingId(null);
      }
  };

  const formatCurrency = (amount) => {
    // Basic currency formatting, consider using Intl.NumberFormat for better localization
    return `$${Number(amount).toFixed(2)}`;
  };

  if (loading) {
    return (
        <Container maxWidth="lg" sx={{ mt: 4, display: 'flex', justifyContent: 'center' }}>
            <CircularProgress /> <Typography sx={{ml:1}}>Loading Payslips...</Typography>
        </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Paper elevation={3} sx={{ padding: { xs: 2, sm: 3 } }}>
        <Typography variant="h4" component="h1" gutterBottom align="center" sx={{display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            <ReceiptLongIcon sx={{mr: 1, fontSize: '2.2rem'}} color="primary"/> My Payslips
        </Typography>

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        {payslips.length === 0 && !loading && !error ? (
          <Typography variant="subtitle1" align="center" sx={{ my: 3 }}>
            No payslips found.
          </Typography>
        ) : (
          <TableContainer component={Paper} elevation={0} sx={{ mt: 2, border: '1px solid', borderColor: 'divider' }}>
            <Table aria-label="payslips table">
              <TableHead sx={{ backgroundColor: 'action.hover' }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 'bold' }}>Month/Period</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 'bold' }}>Net Amount</TableCell>
                  <TableCell align="center" sx={{ fontWeight: 'bold' }}>Status</TableCell>
                  <TableCell align="center" sx={{ fontWeight: 'bold' }}>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {payslips.map((slip) => (
                  <TableRow
                    key={slip.id}
                    sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                    hover
                  >
                    <TableCell component="th" scope="row">
                      {slip.month}
                      {slip.date_from && slip.date_to && (
                        <Typography variant="caption" display="block" color="text.secondary">
                            {new Date(slip.date_from + 'T00:00:00').toLocaleDateString()} - {new Date(slip.date_to + 'T00:00:00').toLocaleDateString()}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell align="right">{formatCurrency(slip.total)}</TableCell>
                    <TableCell align="center">
                      <Box
                        component="span"
                        sx={{
                          display: 'inline-block',
                          px: 1.5, py: 0.5, borderRadius: '12px', fontSize: '0.8rem', fontWeight: 'medium',
                          color: 'common.white',
                          bgcolor: slip.status.toLowerCase() === 'paid' || slip.status.toLowerCase() === 'done' ? 'success.main' :
                                   slip.status.toLowerCase() === 'draft' ? 'warning.main' : 'grey.500',
                        }}
                      >
                        {slip.status}
                      </Box>
                    </TableCell>
                    <TableCell align="center">
                      <Button
                        variant="outlined"
                        size="small"
                        startIcon={downloadingId === slip.id ? <CircularProgress size={16} color="inherit"/> : <DownloadIcon />}
                        onClick={() => handleDownload(slip.id, `${slip.month.replace(/\s+/g, '_')}_Payslip.pdf`)}
                        disabled={!slip.pdf_available || !!downloadingId}
                      >
                        {downloadingId === slip.id ? 'Downloading...' : 'Download'}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>
    </Container>
  );
}

export default PayslipsPage;