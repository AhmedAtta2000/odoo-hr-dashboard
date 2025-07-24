// In frontend/src/theme.js
import { createTheme } from '@mui/material/styles';

// Example Odoo-like primary blue and a neutral grey
const odooPrimaryBlue = '#00A0E0'; // A common Odoo blue (adjust as needed)
const odooSecondaryGrey = '#6c757d'; // A neutral grey

const theme = createTheme({
  palette: {
    primary: {
      main: odooPrimaryBlue, // Your primary color
    },
    secondary: {
      main: odooSecondaryGrey, // Your secondary color
    },
    background: {
      default: '#f4f7f6', // Light grey background, similar to your App.css
      paper: '#ffffff',   // Background for elements like Cards
    },
    // You can customize text colors, error colors, etc.
  },
  typography: {
    fontFamily: [
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
      '"Apple Color Emoji"',
      '"Segoe UI Emoji"',
      '"Segoe UI Symbol"',
    ].join(','),
    h2: {
        fontSize: '1.75rem',
        fontWeight: 500,
        marginBottom: '1rem',
    },
    // Define other typography variants as needed
  },
  components: {
    // Example: Default props for Button
    MuiButton: {
      defaultProps: {
        disableElevation: true, // For a flatter look like Odoo buttons
      },
      styleOverrides: {
        root: {
          textTransform: 'none', // Odoo buttons often don't use all caps
          borderRadius: '4px',   // Default Mui is often more rounded
        },
      },
    },
    MuiTextField: {
        defaultProps: {
            variant: 'outlined', // Common style
            size: 'small',
        }
    },
    MuiCard: {
        styleOverrides: {
            root: {
                borderRadius: '8px', // Consistent border radius
                boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24)' // Softer shadow
            }
        }
    }
    // Add overrides for other components (Card, TextField, etc.)
  },
});

export default theme;