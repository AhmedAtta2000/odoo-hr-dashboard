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