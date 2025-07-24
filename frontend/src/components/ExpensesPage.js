import React, { useState, useRef } from 'react';
import axios from 'axios';
import DatePicker from 'react-datepicker';

import 'react-datepicker/dist/react-datepicker.css';
import './ExpensesPage.css'; // Create this CSS file

function ExpensesPage() {
  // State for form fields
  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [date, setDate] = useState(new Date()); // Default to today
  const [receiptFile, setReceiptFile] = useState(null);

  // Ref for the file input to allow programmatic clearing
  const fileInputRef = useRef(null);

  // State for UI feedback
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Handle file selection
  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      // Optional: Add file size validation here
       const allowedTypes = ["image/jpeg", "image/png", "application/pdf"];
       if (!allowedTypes.includes(file.type)) {
           setError("Invalid file type. Please upload JPG, PNG, or PDF.");
           setReceiptFile(null); // Clear invalid file
           if(fileInputRef.current) { fileInputRef.current.value = ""; } // Reset file input
           return;
       }
       setError(''); // Clear previous file type error
       setReceiptFile(file);
    } else {
      setReceiptFile(null);
    }
  };

  // Handle form submission
  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSuccessMessage('');

    // Basic validation
    if (!description || !amount || !date || !receiptFile) {
      setError("Please fill in all fields and select a receipt file.");
      return;
    }
    if (isNaN(parseFloat(amount)) || parseFloat(amount) <= 0) {
        setError("Please enter a valid positive amount.");
        return;
    }


    setIsSubmitting(true);

    // --- Use FormData for multipart/form-data ---
    const formData = new FormData();
    formData.append('description', description);
    formData.append('amount', parseFloat(amount)); // Ensure amount is a number
    formData.append('date', date.toISOString().split('T')[0]); // Format date YYYY-MM-DD
    formData.append('receipt', receiptFile); // Append the file object

    try {
      console.log("Submitting expense...");
      // Make sure headers are NOT explicitly set to multipart/form-data
      // Axios (and the browser) will set the correct Content-Type with boundary
      // automatically when you pass a FormData object.
      const response = await axios.post('/api/v1/expenses', formData);

      setSuccessMessage(response.data.message || "Expense submitted successfully!");
      // Reset form
      setDescription('');
      setAmount('');
      setDate(new Date());
      setReceiptFile(null);
       if(fileInputRef.current) { fileInputRef.current.value = ""; } // Reset file input visually

    } catch (err) {
      console.error("Error submitting expense:", err);
      if (err.response && err.response.data && err.response.data.detail) {
          setError(`Submission failed: ${err.response.data.detail}`);
      } else {
        setError("Could not submit expense. Please try again later.");
      }
      // Handle auth error potentially
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="expense-request-container">
      <h2>Submit Expense</h2>

      {error && <p className="error-message">{error}</p>}
      {successMessage && <p className="success-message">{successMessage}</p>}

      <form onSubmit={handleSubmit} className="expense-request-form">
        {/* Description */}
        <div className="form-group">
          <label htmlFor="description">Description:</label>
          <input
            type="text"
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
            disabled={isSubmitting}
          />
        </div>

        {/* Amount & Date side-by-side */}
        <div className="form-group form-row">
          <div className="form-subgroup">
             <label htmlFor="amount">Amount ($):</label>
             <input
                type="number"
                id="amount"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                required
                min="0.01" // Minimum amount
                step="0.01" // Allow cents
                disabled={isSubmitting}
             />
          </div>
          <div className="form-subgroup">
             <label htmlFor="date">Date of Expense:</label>
             <DatePicker
                id="date"
                selected={date}
                onChange={(d) => setDate(d)}
                dateFormat="yyyy-MM-dd"
                required
                disabled={isSubmitting}
                className="date-picker-input" // Reuse class
             />
          </div>
        </div>

         {/* Receipt Upload */}
         <div className="form-group">
            <label htmlFor="receipt">Receipt File (JPG, PNG, PDF):</label>
            <input
                type="file"
                id="receipt"
                ref={fileInputRef} // Assign ref
                onChange={handleFileChange}
                accept=".jpg, .jpeg, .png, .pdf" // Hint for browser file picker
                required
                disabled={isSubmitting}
            />
            {receiptFile && <span className="file-name">Selected: {receiptFile.name}</span>}
         </div>


        {/* Submit Button */}
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Submitting...' : 'Submit Expense'}
        </button>
      </form>
    </div>
  );
}

export default ExpensesPage;