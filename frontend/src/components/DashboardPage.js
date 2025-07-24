import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './DashboardPage.css';

// Helper function to format date nicely (optional, can be done inline)
const formatDateForDisplay = (dateString) => {
    if (!dateString) return "N/A";
    try {
        const date = new Date(dateString + 'T00:00:00'); // Add time to avoid timezone issues with just date
        return date.toLocaleDateString(undefined, { // undefined for user's locale
            weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
        });
    } catch (e) {
        return "Invalid Date";
    }
};


function DashboardPage({ userData }) {
  const userName = userData ? userData.full_name : 'User';

  // State for Pending Leaves Widget
  const [pendingLeavesCount, setPendingLeavesCount] = useState(null);
  const [loadingLeaves, setLoadingLeaves] = useState(true);

  // State for Latest Payslip Widget
  const [latestPayslip, setLatestPayslip] = useState(null);
  const [loadingPayslip, setLoadingPayslip] = useState(true);

  // --- State for Next Day Off Widget ---
  const [nextDayOffData, setNextDayOffData] = useState(null); // Stores { next_day_off: 'YYYY-MM-DD', leave_name: '...', message: '...' } or 'error'
  const [loadingNextDayOff, setLoadingNextDayOff] = useState(true);
  // ------------------------------------

  // --- Effect to fetch dashboard data ---
  useEffect(() => {
    if (!userData) {
      setLoadingLeaves(false); setPendingLeavesCount(null);
      setLoadingPayslip(false); setLatestPayslip(null);
      setLoadingNextDayOff(false); setNextDayOffData(null); // Reset next day off state
      return;
    }

    // Fetch Pending Leaves (existing logic)
    const fetchPendingLeaves = async () => {
      setLoadingLeaves(true);
      try {
        const response = await axios.get('/api/v1/dashboard/pending-leaves-count');
        setPendingLeavesCount(response.data.pending_leave_count);
      } catch (error) { console.error("Error fetching pending leaves:", error); setPendingLeavesCount('error');
      } finally { setLoadingLeaves(false); }
    };

    // Fetch Latest Payslip Info (existing logic)
    const fetchLatestPayslip = async () => {
        setLoadingPayslip(true);
        try {
            const response = await axios.get('/api/v1/payslips');
            const payslips = response.data;
            if (payslips && payslips.length > 0) {
                setLatestPayslip({
                    month: payslips[0].month, status: payslips[0].status,
                    id: payslips[0].id, pdf_available: payslips[0].pdf_available
                });
            } else { setLatestPayslip(null); }
        } catch (error) { console.error("Error fetching latest payslip:", error); setLatestPayslip('error');
        } finally { setLoadingPayslip(false); }
    };

    // --- Fetch Next Scheduled Day Off ---
    const fetchNextDayOff = async () => {
        setLoadingNextDayOff(true);
        try {
            const response = await axios.get('/api/v1/dashboard/next-day-off');
            setNextDayOffData(response.data); // Store the whole response object
        } catch (error) {
            console.error("Error fetching next day off:", error);
            setNextDayOffData({ error: true, message: "Could not load data." }); // Store error state
        } finally {
            setLoadingNextDayOff(false);
        }
    };
    // ---------------------------------

    fetchPendingLeaves();
    fetchLatestPayslip();
    fetchNextDayOff(); // Call the new fetch function

  }, [userData]); // Re-fetch if userData changes
  // ---------------------------------


  return (
    <div className="dashboard-container">
      <h2>Welcome, {userName}!</h2>

      <div className="dashboard-widgets">
        {/* Widget 1: Pending Leaves (dynamic) */}
        <div className="widget">
          <h3>Pending Leaves</h3>
          {loadingLeaves ? ( <p>Loading...</p>
          ) : pendingLeavesCount === 'error' ? ( <p className="widget-error">Could not load data.</p>
          ) : pendingLeavesCount !== null ? (
            <p>You have <strong>{pendingLeavesCount}</strong> pending leave request{pendingLeavesCount !== 1 ? 's' : ''}.</p>
          ) : ( <p>No data available.</p> )}
          <a href="/leave-request">View/Request Leaves</a>
        </div>

        {/* Widget 2: Next Scheduled Day Off */}
        <div className="widget">
          <h3>Next Scheduled Day Off</h3>
          {loadingNextDayOff ? (
            <p>Loading...</p>
          ) : nextDayOffData && nextDayOffData.error ? (
            <p className="widget-error">{nextDayOffData.message || "Could not load data."}</p>
          ) : nextDayOffData && nextDayOffData.next_day_off ? (
            <p>
              Your next day off is <strong>{formatDateForDisplay(nextDayOffData.next_day_off)}</strong>
              {nextDayOffData.leave_name && ` (${nextDayOffData.leave_name})`}.
            </p>
          ) : nextDayOffData && nextDayOffData.message ? (
             <p>{nextDayOffData.message}</p> // e.g., "No upcoming approved leave found."
          ) : (
            <p>No upcoming days off scheduled.</p>
          )}
          {/* Link to Attendance or Leave page later */}
          <a href="/leave-request">View Leaves</a>
        </div>

        {/* Widget 3: Latest Payslip Status (dynamic) */}
        <div className="widget">
          <h3>Latest Payslip</h3>
          {loadingPayslip ? ( <p>Loading...</p>
          ) : latestPayslip === 'error' ? ( <p className="widget-error">Could not load payslip data.</p>
          ) : latestPayslip ? (
            <>
              <p>
                Your payslip for <strong>{latestPayslip.month}</strong> is <strong>{latestPayslip.status}</strong>.
              </p>
              {latestPayslip.pdf_available && (
                  <a href={`/payslips`} title="View All Payslips & Download">Download/View</a>
              )}
            </>
          ) : ( <p>No payslip information available.</p> )}
           <a href="/payslips" style={{display: 'block', marginTop: '10px'}}>View All Payslips</a>
        </div>

      </div>
    </div>
  );
}

export default DashboardPage;