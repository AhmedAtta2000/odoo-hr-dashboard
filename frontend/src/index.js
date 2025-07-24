// In frontend/src/index.js
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import reportWebVitals from './reportWebVitals';
import axios from 'axios';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import theme from './theme';

axios.defaults.baseURL = 'http://127.0.0.1:8000'; // Your backend base URL

// --- Axios Interceptors for Token Refresh ---
let isRefreshing = false;
let failedQueue = []; // Store requests that failed due to 401

const processQueue = (error, token = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

axios.interceptors.response.use(
  (response) => {
    return response; // Pass through successful responses
  },
  async (error) => {
    const originalRequest = error.config;

    // Check if it's a 401 error and not a retry request or refresh token request itself
    if (error.response && error.response.status === 401 && !originalRequest._retry) {
      if (originalRequest.url === '/api/v1/auth/refresh-token') {
        // If refresh token request itself fails with 401, logout immediately
        console.error("Refresh token failed. Logging out.");
        localStorage.removeItem('authToken');
        localStorage.removeItem('refreshToken');
        delete axios.defaults.headers.common['Authorization'];
        // Force a redirect to login - can be tricky without access to useNavigate here
        // Best to let App.js handle this state change by setting token to null.
        // This might require a custom event or state management for global logout.
        // For now, we'll rely on subsequent calls failing or App.js logic.
        window.location.href = '/login'; // Simple redirect
        return Promise.reject(error);
      }

      if (isRefreshing) {
        // If already refreshing, add request to queue to retry after refresh
        return new Promise(function(resolve, reject) {
          failedQueue.push({ resolve, reject });
        })
          .then(token => {
            originalRequest.headers['Authorization'] = 'Bearer ' + token;
            return axios(originalRequest); // Retry with new token
          })
          .catch(err => {
            return Promise.reject(err); // Propagate error if queue processing fails
          });
      }

      originalRequest._retry = true; // Mark that we've tried to refresh for this request
      isRefreshing = true;

      const refreshToken = localStorage.getItem('refreshToken');
      if (!refreshToken) {
        console.log("No refresh token found, cannot refresh. Logging out.");
        isRefreshing = false;
        processQueue(error, null); // Reject queued requests
        // Handle logout (similar to refresh token failure)
        localStorage.removeItem('authToken');
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        console.log("Attempting to refresh access token...");
        const refreshResponse = await axios.post('/api/v1/auth/refresh-token', {
          refresh_token: refreshToken
        });

        const { access_token: newAccessToken, refresh_token: newRefreshToken } = refreshResponse.data;
        
        localStorage.setItem('authToken', newAccessToken);
        localStorage.setItem('refreshToken', newRefreshToken); // Store new refresh token (rotation)
        axios.defaults.headers.common['Authorization'] = 'Bearer ' + newAccessToken;
        
        processQueue(null, newAccessToken); // Process queued requests with new token
        originalRequest.headers['Authorization'] = 'Bearer ' + newAccessToken;
        return axios(originalRequest); // Retry original request

      } catch (refreshError) {
        console.error("Error refreshing token:", refreshError);
        processQueue(refreshError, null); // Reject queued requests
        // Handle logout (e.g., redirect to login)
        localStorage.removeItem('authToken');
        localStorage.removeItem('refreshToken');
        delete axios.defaults.headers.common['Authorization'];
        window.location.href = '/login'; // Simple redirect
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
    // For other errors, just pass them through
    return Promise.reject(error);
  }
);
// --- End Axios Interceptors ---


const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  </React.StrictMode>
);

reportWebVitals();