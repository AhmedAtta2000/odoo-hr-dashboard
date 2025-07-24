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