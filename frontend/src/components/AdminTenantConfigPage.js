// In frontend/src/components/AdminTenantConfigPage.js
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

// MUI Imports
import Container from '@mui/material/Container';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Divider from '@mui/material/Divider';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import IconButton from '@mui/material/IconButton';
import EditIcon from '@mui/icons-material/Edit';
import ToggleOnIcon from '@mui/icons-material/ToggleOn';
import ToggleOffIcon from '@mui/icons-material/ToggleOff';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import SettingsIcon from '@mui/icons-material/Settings'; // For page title
import DeleteIcon from '@mui/icons-material/Delete'; // <-- IMPORT DELETE ICON
import Tooltip from '@mui/material/Tooltip'; // <-- IMPORT TOOLTIP


function AdminTenantConfigPage() {
    const [tenants, setTenants] = useState([]);
    const [selectedTenant, setSelectedTenant] = useState(null);
    const [currentOdooConfig, setCurrentOdooConfig] = useState(null);
    const [isLoadingTenants, setIsLoadingTenants] = useState(true);
    const [isLoadingOdooConfig, setIsLoadingOdooConfig] = useState(false);

    const [formBaseUrl, setFormBaseUrl] = useState('');
    const [formDbName, setFormDbName] = useState('');
    const [formUsername, setFormUsername] = useState('');
    const [formApiKey, setFormApiKey] = useState('');

    const [showCreateTenantForm, setShowCreateTenantForm] = useState(false);
    const [newTenantName, setNewTenantName] = useState('');
    const [isCreatingTenant, setIsCreatingTenant] = useState(false);

    const [error, setError] = useState('');
    const [successMessage, setSuccessMessage] = useState('');
    const [isSavingOdooConfig, setIsSavingOdooConfig] = useState(false);

    const [isTestingConnection, setIsTestingConnection] = useState(false);
    const [testConnectionResult, setTestConnectionResult] = useState(null);

    const clearMessages = () => { setError(''); setSuccessMessage(''); setTestConnectionResult(null);};

    const fetchTenants = useCallback(async () => {
        setIsLoadingTenants(true); clearMessages();
        try {
            const response = await axios.get('/api/v1/admin/tenants');
            setTenants(response.data || []);
        } catch (err) { handleApiError(err, "Could not load tenants."); setTenants([]); }
        finally { setIsLoadingTenants(false); }
    }, []); // Added empty dependency array to useCallback as fetchTenants itself doesn't change

    useEffect(() => { fetchTenants(); }, [fetchTenants]);

    useEffect(() => {
        if (!selectedTenant) {
            setCurrentOdooConfig(null);
            setFormBaseUrl(''); setFormDbName(''); setFormUsername(''); setFormApiKey('');
            setTestConnectionResult(null);
            // clearMessages(); // Not strictly needed here as it's cleared when selecting new tenant
            return;
        }
        const fetchTenantOdooConfig = async () => {
            setIsLoadingOdooConfig(true); clearMessages(); // Clear messages when loading new config
            try {
                const response = await axios.get(`/api/v1/admin/tenant/${selectedTenant.id}/odoo-config`);
                const config = response.data;
                setCurrentOdooConfig(config);
                setFormBaseUrl(config?.odoo_base_url || '');
                setFormDbName(config?.odoo_db_name || '');
                setFormUsername(config?.odoo_username || '');
                setFormApiKey('');
            } catch (err) {
                handleApiError(err, `Could not load Odoo config for ${selectedTenant.name}.`);
                setCurrentOdooConfig(null);
            } finally { setIsLoadingOdooConfig(false); }
        };
        fetchTenantOdooConfig();
    }, [selectedTenant]); // Re-run when selectedTenant changes

    const handleSelectTenantForConfig = (tenant) => {
        // If clicking the same tenant, deselect it to hide the config form
        if (selectedTenant && selectedTenant.id === tenant.id) {
            setSelectedTenant(null);
        } else {
            setSelectedTenant(tenant);
        }
        setShowCreateTenantForm(false);
        clearMessages(); // Clear messages when selecting a new tenant or deselecting
    };

    const handleOdooConfigSave = async (event) => {
        event.preventDefault();
        if (!selectedTenant) { setError("Please select a tenant."); return; }
        if (!formBaseUrl || !formDbName || !formUsername || !formApiKey) {
            setError("Odoo URL, DB Name, Username, and API Key are required to save."); return;
        }
        setIsSavingOdooConfig(true); clearMessages();
        const payload = {
            odoo_base_url: formBaseUrl, odoo_db_name: formDbName,
            odoo_username: formUsername, odoo_api_key: formApiKey,
        };
        try {
            await axios.put(`/api/v1/admin/tenant/${selectedTenant.id}/odoo-config`, payload);
            setSuccessMessage("Odoo configuration saved successfully!");
            setFormApiKey('');
            const response = await axios.get(`/api/v1/admin/tenant/${selectedTenant.id}/odoo-config`);
            setCurrentOdooConfig(response.data);
        } catch (err) { handleApiError(err, "Could not save Odoo configuration."); }
        finally { setIsSavingOdooConfig(false); }
    };

    const handleCreateTenant = async (event) => {
        event.preventDefault();
        if (!newTenantName.trim()) { setError("Tenant name cannot be empty."); return; }
        setIsCreatingTenant(true); clearMessages();
        try {
            await axios.post('/api/v1/admin/tenants', { name: newTenantName.trim(), is_active: true });
            setSuccessMessage(`Tenant "${newTenantName.trim()}" created successfully!`);
            setNewTenantName(''); setShowCreateTenantForm(false); fetchTenants();
        } catch (err) { handleApiError(err, "Could not create tenant."); }
        finally { setIsCreatingTenant(false); }
    };

    const handleToggleTenantStatus = async (tenantToUpdate) => {
        clearMessages();
        const newStatus = !tenantToUpdate.is_active;
        try {
            await axios.put(`/api/v1/admin/tenant/${tenantToUpdate.id}/status`, { is_active: newStatus });
            setSuccessMessage(`Tenant "${tenantToUpdate.name}" status updated.`);
            fetchTenants();
            if (selectedTenant && selectedTenant.id === tenantToUpdate.id) {
                setSelectedTenant(prev => prev ? {...prev, is_active: newStatus} : null);
            }
        } catch (err) { handleApiError(err, `Could not update status for tenant "${tenantToUpdate.name}".`);}
    };

    // --- NEW: Delete Tenant Handler ---
    const handleDeleteTenant = async (tenantId, tenantName) => {
        clearMessages(); // Clear previous page-level messages
        if (window.confirm(`Are you sure you want to delete tenant "${tenantName}" (ID: ${tenantId})? This action cannot be undone and might fail if resources (like users) are still associated with it.`)) {
            try {
                await axios.delete(`/api/v1/admin/tenant/${tenantId}`);
                setSuccessMessage(`Tenant "${tenantName}" deleted successfully.`);
                fetchTenants(); // Refresh the list of tenants
                // If the deleted tenant was the selected one for Odoo config, clear the selection
                if (selectedTenant && selectedTenant.id === tenantId) {
                    setSelectedTenant(null);
                }
            } catch (err) {
                console.error(`Error deleting tenant ${tenantId}:`, err);
                setError(err.response?.data?.detail || `Could not delete tenant "${tenantName}".`);
            }
        }
    };
    // --------------------------------

    const handleTestOdooConnection = async () => {
        if (!selectedTenant) { setError("Please select a tenant."); return; }
        if (!currentOdooConfig || !currentOdooConfig.odoo_base_url) {
            setError("No Odoo configuration saved for this tenant to test. Please save a configuration first.");
            setTestConnectionResult(null); return;
        }
        setIsTestingConnection(true); setTestConnectionResult(null); clearMessages();
        try {
            const response = await axios.post(`/api/v1/admin/tenant/${selectedTenant.id}/test-odoo-connection`);
            setTestConnectionResult(response.data);
        } catch (err) {
            handleApiError(err, "Connection test failed due to a network or server error.", setTestConnectionResult);
             if (err.response && err.response.data) {
                setTestConnectionResult({ status: 'failure', message: err.response.data.detail || "Connection test failed." });
            } else {
                setTestConnectionResult({ status: 'failure', message: "Could not test Odoo connection." });
            }
        } finally { setIsTestingConnection(false); }
    };

    const handleApiError = (err, defaultMessage, specificErrorSetter) => {
        let message = defaultMessage;
        if (err.response && err.response.data && err.response.data.detail) {
            message = err.response.data.detail;
        }
        if (specificErrorSetter) {
            specificErrorSetter({ status: 'failure', message }); // Assuming specificErrorSetter expects an object
        } else {
            setError(message);
        }
        console.error(defaultMessage, err);
    };

    if (isLoadingTenants) {
        return (
            <Container maxWidth="lg" sx={{ mt: 4, display: 'flex', justifyContent: 'center' }}>
                <CircularProgress /> <Typography sx={{ml:1}}>Loading Tenants...</Typography>
            </Container>
        );
    }

    return (
        <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
            <Paper elevation={3} sx={{ p: { xs: 2, sm: 3 } }}>
                <Typography variant="h4" component="h1" gutterBottom align="center" sx={{display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
                    <SettingsIcon sx={{mr:1, fontSize: '2.2rem'}} color="primary"/> Admin: Tenant Management
                </Typography>
                {/* ... (Rest of the page structure: Create Tenant, Tenant List, Odoo Config) ... */}
                {/* General Page Level Messages */}
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                {successMessage && <Alert severity="success" sx={{ mb: 2 }}>{successMessage}</Alert>}

                {/* Create New Tenant Section */}
                <Box sx={{ mb: 3 }}>
                    <Button
                        variant="contained"
                        startIcon={<AddCircleOutlineIcon />}
                        onClick={() => { setShowCreateTenantForm(!showCreateTenantForm); clearMessages(); }}
                        sx={{ mb: showCreateTenantForm ? 1 : 0 }}
                    >
                        {showCreateTenantForm ? 'Cancel Create' : 'Create New Tenant'}
                    </Button>
                    {showCreateTenantForm && (
                        <Paper variant="outlined" sx={{ p: 2, mt: 1 }}>
                            <Typography variant="h6" gutterBottom>New Tenant</Typography>
                            <Box component="form" onSubmit={handleCreateTenant} noValidate>
                                <TextField
                                    label="Tenant Name"
                                    fullWidth required
                                    value={newTenantName}
                                    onChange={(e) => setNewTenantName(e.target.value)}
                                    disabled={isCreatingTenant}
                                    variant="outlined" size="small" sx={{ mb: 1 }}
                                />
                                <Button type="submit" variant="contained" color="secondary" disabled={isCreatingTenant}>
                                    {isCreatingTenant ? <CircularProgress size={24} color="inherit" /> : 'Save Tenant'}
                                </Button>
                            </Box>
                        </Paper>
                    )}
                </Box>

                {/* Tenant List Section */}
                <Typography variant="h5" component="h2" gutterBottom>Existing Tenants</Typography>
                {tenants.length === 0 && !isLoadingTenants && !error ? (
                    <Typography>No tenants found. Create one above.</Typography>
                ) : (
                    <TableContainer component={Paper} elevation={1} variant="outlined">
                        <Table size="small">
                            <TableHead sx={{ backgroundColor: 'action.hover' }}>
                                <TableRow>
                                    <TableCell sx={{ fontWeight: 'bold' }}>ID</TableCell>
                                    <TableCell sx={{ fontWeight: 'bold' }}>Name</TableCell>
                                    <TableCell align="center" sx={{ fontWeight: 'bold' }}>Status</TableCell>
                                    <TableCell align="center" sx={{ fontWeight: 'bold' }}>Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {tenants.map(tenant => (
                                    <TableRow key={tenant.id} hover selected={selectedTenant?.id === tenant.id}>
                                        <TableCell>{tenant.id}</TableCell>
                                        <TableCell>{tenant.name}</TableCell>
                                        <TableCell align="center">
                                            <Box component="span" sx={{
                                                px: 1.5, py: 0.5, borderRadius: '12px', fontSize: '0.8rem',
                                                color: 'common.white', fontWeight: 'medium',
                                                bgcolor: tenant.is_active ? 'success.main' : 'error.main',
                                            }}>
                                                {tenant.is_active ? 'Active' : 'Inactive'}
                                            </Box>
                                        </TableCell>
                                        <TableCell align="center">
                                            <Tooltip title="Configure Odoo Settings">
                                                <IconButton size="small" onClick={(e) => { e.stopPropagation(); handleSelectTenantForConfig(tenant);}} color="primary">
                                                    <EditIcon fontSize="inherit" />
                                                </IconButton>
                                            </Tooltip>
                                            <Tooltip title={tenant.is_active ? "Deactivate Tenant" : "Activate Tenant"}>
                                                <IconButton size="small" onClick={(e) => { e.stopPropagation(); handleToggleTenantStatus(tenant);}}>
                                                    {tenant.is_active ? <ToggleOffIcon color="error" /> : <ToggleOnIcon color="success" />}
                                                </IconButton>
                                            </Tooltip>
                                            {/* --- ADDED DELETE BUTTON --- */}
                                            <Tooltip title="Delete Tenant">
                                                <IconButton
                                                    size="small"
                                                    onClick={(e) => { e.stopPropagation(); handleDeleteTenant(tenant.id, tenant.name);}}
                                                    color="error"
                                                >
                                                    <DeleteIcon fontSize="inherit" />
                                                </IconButton>
                                            </Tooltip>
                                            {/* -------------------------- */}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}
                <Divider sx={{ my: 3 }} />

                {/* Odoo Configuration Section */}
                {selectedTenant && (
                    <Paper variant="outlined" sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>Odoo Configuration for: {selectedTenant.name}</Typography>

                        {testConnectionResult && (
                            <Alert severity={testConnectionResult.status === 'success' ? 'success' : 'error'} sx={{ mb: 2 }}>
                                <strong>Connection Test:</strong> {testConnectionResult.message}
                            </Alert>
                        )}

                        {isLoadingOdooConfig ? <CircularProgress sx={{display: 'block', margin: 'auto'}}/> : (
                            <Box component="form" onSubmit={handleOdooConfigSave} noValidate sx={{ mt: 1 }}>
                                <Grid container spacing={2}>
                                    <Grid item xs={12}>
                                        <TextField label="Odoo Base URL" fullWidth required value={formBaseUrl} onChange={e => setFormBaseUrl(e.target.value)} placeholder="https://your-odoo.example.com" variant="outlined" size="small" disabled={isSavingOdooConfig}/>
                                    </Grid>
                                    <Grid item xs={12} sm={6}>
                                        <TextField label="Odoo Database Name" fullWidth required value={formDbName} onChange={e => setFormDbName(e.target.value)} placeholder="your_odoo_db" variant="outlined" size="small" disabled={isSavingOdooConfig}/>
                                    </Grid>
                                    <Grid item xs={12} sm={6}>
                                        <TextField label="Odoo Username (for API)" fullWidth required value={formUsername} onChange={e => setFormUsername(e.target.value)} placeholder="admin_or_api_user" variant="outlined" size="small" disabled={isSavingOdooConfig}/>
                                    </Grid>
                                    <Grid item xs={12}>
                                        <TextField label="Odoo API Key/Token (Enter to update)" type="password" fullWidth required value={formApiKey} onChange={e => setFormApiKey(e.target.value)} placeholder="Enter new or existing Odoo API Key" variant="outlined" size="small" disabled={isSavingOdooConfig}/>
                                        <Typography variant="caption" display="block" sx={{mt: 0.5}}>Leave blank only if not changing the key and other details are being updated (this field is required on save).</Typography>
                                    </Grid>
                                    <Grid item xs={12} sx={{ display: 'flex', gap: 1, mt: 1 }}>
                                        <Button type="submit" variant="contained" color="primary" disabled={isSavingOdooConfig}>
                                            {isSavingOdooConfig ? <CircularProgress size={24} color="inherit" /> : 'Save Odoo Config'}
                                        </Button>
                                        <Button variant="outlined" color="secondary" onClick={handleTestOdooConnection} disabled={isTestingConnection || !currentOdooConfig?.odoo_base_url}>
                                            {isTestingConnection ? <CircularProgress size={24} color="inherit" /> : 'Test Connection'}
                                        </Button>
                                    </Grid>
                                </Grid>
                            </Box>
                        )}
                    </Paper>
                )}
            </Paper>
        </Container>
    );
}
export default AdminTenantConfigPage;