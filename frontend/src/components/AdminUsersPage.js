// In frontend/src/components/AdminUsersPage.js
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import debounce from 'lodash.debounce';

// MUI Imports
import Container from '@mui/material/Container';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import IconButton from '@mui/material/IconButton';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Tooltip from '@mui/material/Tooltip';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import TextField from '@mui/material/TextField';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import Grid from '@mui/material/Grid';
import Divider from '@mui/material/Divider';
import Autocomplete from '@mui/material/Autocomplete';

// Icons
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';

const initialUserModel = {
    email: '',
    password: '', // For create modal
    full_name: '',
    tenant_id: '', // Will be int after selection
    is_admin: false,
    is_active: true,
    odoo_employee_id: '', // Will be int after selection or empty string
    job_title: '',       // SaaS specific, can be pre-filled
    phone: '',          // SaaS specific, can be pre-filled
};

// For edit form, password is named differently to distinguish
const initialEditUserModel = { ...initialUserModel, new_password: '' };
delete initialEditUserModel.password;


function AdminUsersPage() {
    const [users, setUsers] = useState([]);
    const [allTenants, setAllTenants] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [pageError, setPageError] = useState('');
    const [successMessage, setSuccessMessage] = useState('');

    // Create Modal State
    const [openCreateModal, setOpenCreateModal] = useState(false);
    const [createUserForm, setCreateUserForm] = useState({ ...initialUserModel });
    const [isCreating, setIsCreating] = useState(false);
    const [createError, setCreateError] = useState('');

    // Edit Modal State
    const [openEditModal, setOpenEditModal] = useState(false);
    const [editUserForm, setEditUserForm] = useState({ ...initialEditUserModel });
    const [currentUserEditing, setCurrentUserEditing] = useState(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editError, setEditError] = useState('');

    // Odoo Employee Search State (for Create Modal)
    const [odooEmpSearchTermCreate, setOdooEmpSearchTermCreate] = useState('');
    const [odooEmpSearchResultsCreate, setOdooEmpSearchResultsCreate] = useState([]);
    const [isLoadingOdooEmpsCreate, setIsLoadingOdooEmpsCreate] = useState(false);

    // Odoo Employee Search State (for Edit Modal - if you implement it there)
    // const [odooEmpSearchTermEdit, setOdooEmpSearchTermEdit] = useState('');
    // const [odooEmpSearchResultsEdit, setOdooEmpSearchResultsEdit] = useState([]);
    // const [isLoadingOdooEmpsEdit, setIsLoadingOdooEmpsEdit] = useState(false);


    const clearMessages = () => {
        setPageError(''); setSuccessMessage('');
        setCreateError(''); setEditError('');
    };

    const fetchAllData = useCallback(async () => {
        setIsLoading(true); clearMessages();
        try {
            const [usersRes, tenantsRes] = await Promise.all([
                axios.get('/api/v1/admin/users'),
                axios.get('/api/v1/admin/tenants')
            ]);
            setUsers(usersRes.data || []);
            setAllTenants(tenantsRes.data || []);
        } catch (err) {
            console.error("Error fetching initial admin data:", err);
            setPageError(err.response?.data?.detail || "Could not load initial data for user management.");
        } finally { setIsLoading(false); }
    }, []);

    useEffect(() => { fetchAllData(); }, [fetchAllData]);

    // --- Odoo Employee Search Logic (generic for Create/Edit if needed) ---
    const fetchOdooEmployees = async (searchTerm, tenantId, setSearchResults, setLoadingState) => {
        if (!searchTerm || searchTerm.length < 2 || !tenantId) {
            setSearchResults([]);
            return;
        }
        setLoadingState(true);
        try {
            const response = await axios.get(`/api/v1/admin/odoo-employees/search`, {
                params: { tenant_id: tenantId, term: searchTerm, limit: 10 }
            });
            setSearchResults(response.data || []);
        } catch (err) {
            console.error("Error searching Odoo employees:", err);
            setSearchResults([]);
        } finally {
            setLoadingState(false);
        }
    };

    const debouncedFetchOdooEmployeesForCreate = useMemo(
        () => debounce((term, tenantId) => fetchOdooEmployees(term, tenantId, setOdooEmpSearchResultsCreate, setIsLoadingOdooEmpsCreate), 500),
        []
    );

    const handleOdooEmpSearchInputChangeCreate = (event, newInputValue) => {
        setOdooEmpSearchTermCreate(newInputValue);
        if (createUserForm.tenant_id) {
            debouncedFetchOdooEmployeesForCreate(newInputValue, createUserForm.tenant_id);
        } else {
            setOdooEmpSearchResultsCreate([]);
        }
    };

    const handleOdooEmpSelectionCreate = (event, selectedOdooEmp) => {
        if (selectedOdooEmp && selectedOdooEmp.id) {
            setCreateUserForm(prev => ({
                ...prev,
                odoo_employee_id: selectedOdooEmp.id.toString(),
                full_name: selectedOdooEmp.name || prev.full_name || '',
                email: selectedOdooEmp.work_email || prev.email || '',
                job_title: selectedOdooEmp.job_title || prev.job_title || '',
                phone: selectedOdooEmp.work_phone || selectedOdooEmp.mobile_phone || prev.phone || '',
            }));
            setOdooEmpSearchTermCreate(`${selectedOdooEmp.name} (ID: ${selectedOdooEmp.id})`);
        } else {
            setCreateUserForm(prev => ({ ...prev, odoo_employee_id: '' }));
            setOdooEmpSearchTermCreate('');
        }
        setOdooEmpSearchResultsCreate([]);
    };


    // --- Create User Handlers ---
    const handleOpenCreateModal = () => {
        setCreateUserForm({ ...initialUserModel });
        setOdooEmpSearchTermCreate('');
        setOdooEmpSearchResultsCreate([]);
        clearMessages();
        setOpenCreateModal(true);
    };
    const handleCloseCreateModal = () => { setOpenCreateModal(false); setCreateError(''); };
    const handleCreateFormChange = (e) => {
        const { name, value, type, checked } = e.target;
        setCreateUserForm(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
    };
    const handleCreateSubmit = async (e) => {
        e.preventDefault();
        clearMessages();
        if (!createUserForm.email.trim()){ setCreateError("Email is required."); return; }
        if (!createUserForm.password){ setCreateError("Password is required."); return; }
        if (createUserForm.password.length < 8) {
            setCreateError("Password must be at least 8 characters."); return;
        }
        if (!createUserForm.tenant_id) {
            setCreateError("Tenant selection is required."); return;
        }
        setIsCreating(true);
        const payload = { ...createUserForm,
            odoo_employee_id: createUserForm.odoo_employee_id ? parseInt(createUserForm.odoo_employee_id, 10) : null,
            tenant_id: parseInt(createUserForm.tenant_id, 10)
        };
        if (!payload.job_title) delete payload.job_title;
        if (!payload.phone) delete payload.phone;
        if (!payload.full_name) delete payload.full_name;


        try {
            await axios.post('/api/v1/admin/users', payload);
            setSuccessMessage(`User ${payload.email} created successfully.`);
            handleCloseCreateModal();
            fetchAllData();
        } catch (err) {
            setCreateError(err.response?.data?.detail || "Failed to create user.");
            console.error("Create user error:", err);
        } finally {
            setIsCreating(false);
        }
    };

    // --- Edit User Handlers ---
    const handleOpenEditModal = (user) => {
        setCurrentUserEditing(user);
        setEditUserForm({
            email: user.email || '',
            full_name: user.full_name || '',
            tenant_id: user.tenant_id || '',
            is_admin: user.is_admin || false,
            is_active: user.is_active || false,
            odoo_employee_id: user.odoo_employee_id ? user.odoo_employee_id.toString() : '',
            job_title: user.job_title || '',
            phone: user.phone || '',
            new_password: '',
        });
        clearMessages();
        setOpenEditModal(true);
    };
    const handleCloseEditModal = () => { setOpenEditModal(false); setEditError(''); setCurrentUserEditing(null); };
    const handleEditFormChange = (e) => {
        const { name, value, type, checked } = e.target;
        setEditUserForm(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
    };
    const handleEditSubmit = async (e) => {
        e.preventDefault();
        if (!currentUserEditing) return;
        clearMessages();
        if (editUserForm.new_password && editUserForm.new_password.length < 8) {
            setEditError("New password must be at least 8 characters if provided."); return;
        }
        if (!editUserForm.tenant_id) {
            setEditError("Tenant selection is required."); return;
        }
        setIsEditing(true);
        const payload = { ...editUserForm,
            odoo_employee_id: editUserForm.odoo_employee_id ? parseInt(editUserForm.odoo_employee_id, 10) : null,
            tenant_id: parseInt(editUserForm.tenant_id, 10)
        };
        if (payload.new_password && payload.new_password.trim() !== '') {
            payload.password = payload.new_password;
        }
        delete payload.new_password;
        if (!payload.job_title) delete payload.job_title;
        if (!payload.phone) delete payload.phone;
        if (!payload.full_name) delete payload.full_name;


        try {
            await axios.put(`/api/v1/admin/user/${currentUserEditing.id}`, payload);
            setSuccessMessage(`User ${payload.email || currentUserEditing.email} updated successfully.`);
            handleCloseEditModal();
            fetchAllData();
        } catch (err) {
            setEditError(err.response?.data?.detail || "Failed to update user.");
            console.error("Update user error:", err);
        } finally {
            setIsEditing(false);
        }
    };

    // --- Delete User Handler ---
    const handleDeleteUser = async (userId, userEmail) => {
        clearMessages();
        if (window.confirm(`Are you sure you want to delete user: ${userEmail} (ID: ${userId})? This action cannot be undone.`)) {
            try {
                await axios.delete(`/api/v1/admin/user/${userId}`);
                setSuccessMessage(`User ${userEmail} deleted successfully.`);
                fetchAllData();
            } catch (err) {
                setPageError(err.response?.data?.detail || `Failed to delete user ${userEmail}.`);
                console.error("Delete user error:", err);
            }
        }
    };

    const renderUserTable = () => (
        <TableContainer component={Paper} elevation={1} variant="outlined">
            <Table size="small" aria-label="SaaS users table">
                <TableHead sx={{ backgroundColor: 'action.hover' }}>
                    <TableRow>
                        <TableCell sx={{ fontWeight: 'bold' }}>ID</TableCell>
                        <TableCell sx={{ fontWeight: 'bold' }}>Email</TableCell>
                        <TableCell sx={{ fontWeight: 'bold' }}>Full Name</TableCell>
                        <TableCell align="center" sx={{ fontWeight: 'bold' }}>Tenant ID</TableCell>
                        <TableCell align="center" sx={{ fontWeight: 'bold' }}>Admin</TableCell>
                        <TableCell align="center" sx={{ fontWeight: 'bold' }}>Active</TableCell>
                        <TableCell align="center" sx={{ fontWeight: 'bold' }}>Odoo Emp. ID</TableCell>
                        <TableCell align="center" sx={{ fontWeight: 'bold' }}>Actions</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {users.map((user) => (
                        <TableRow key={user.id} hover sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
                            <TableCell component="th" scope="row">{user.id}</TableCell>
                            <TableCell>{user.email}</TableCell>
                            <TableCell>{user.full_name || 'N/A'}</TableCell>
                            <TableCell align="center">{user.tenant_id}</TableCell>
                            <TableCell align="center">{user.is_admin ? <CheckCircleIcon color="success" fontSize="small"/> : <CancelIcon color="action" fontSize="small"/>}</TableCell>
                            <TableCell align="center">{user.is_active ? <CheckCircleIcon color="success" fontSize="small"/> : <CancelIcon color="error" fontSize="small"/>}</TableCell>
                            <TableCell align="center">{user.odoo_employee_id || 'N/A'}</TableCell>
                            <TableCell align="center">
                                <Tooltip title="Edit User">
                                    <IconButton size="small" onClick={() => handleOpenEditModal(user)} color="primary">
                                        <EditIcon fontSize="inherit" />
                                    </IconButton>
                                </Tooltip>
                                <Tooltip title="Delete User">
                                    <IconButton size="small" onClick={() => handleDeleteUser(user.id, user.email)} color="error">
                                        <DeleteIcon fontSize="inherit" />
                                    </IconButton>
                                </Tooltip>
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </TableContainer>
    );

    const renderCreateUserModal = () => (
        <Dialog open={openCreateModal} onClose={handleCloseCreateModal} maxWidth="md" fullWidth>
            <DialogTitle>Create New User</DialogTitle>
            <Box component="form" onSubmit={handleCreateSubmit} noValidate>
                <DialogContent>
                    {createError && <Alert severity="error" sx={{ mb: 2 }}>{createError}</Alert>}
                    <Grid container spacing={2}>
                        <Grid item xs={12} sm={6}><TextField autoFocus margin="dense" name="email" label="Email Address" type="email" fullWidth variant="outlined" size="small" value={createUserForm.email} onChange={handleCreateFormChange} required error={!!(createError && !createUserForm.email.trim())}/></Grid>
                        <Grid item xs={12} sm={6}><TextField margin="dense" name="password" label="Password" type="password" fullWidth variant="outlined" size="small" value={createUserForm.password} onChange={handleCreateFormChange} required error={!!(createError && (!createUserForm.password || createUserForm.password.length < 8))} helperText="Min 8 characters" /></Grid>
                        <Grid item xs={12} sm={6}><TextField margin="dense" name="full_name" label="Full Name" type="text" fullWidth variant="outlined" size="small" value={createUserForm.full_name} onChange={handleCreateFormChange} /></Grid>
                        <Grid item xs={12} sm={12} md={6}>
                            <FormControl fullWidth margin="dense" size="small" required error={!!(createError && !createUserForm.tenant_id)}>
                                <InputLabel id="create-tenant-select-label">Tenant *</InputLabel>
                                <Select labelId="create-tenant-select-label" name="tenant_id" value={createUserForm.tenant_id} label="Tenant *" onChange={handleCreateFormChange}>
                                    <MenuItem value="" disabled><em>-- Select Tenant --</em></MenuItem>
                                    {allTenants.map((tenant) => (<MenuItem key={tenant.id} value={tenant.id}>{tenant.name} (ID: {tenant.id})</MenuItem>))}
                                </Select>
                            </FormControl>
                        </Grid>
                        <Grid item xs={12} sm={7}> {/* Autocomplete takes more space */}
                            <Autocomplete
                                id="odoo-employee-search-create" fullWidth size="small"
                                options={odooEmpSearchResultsCreate}
                                getOptionLabel={(option) => option.name ? `${option.name} (ID: ${option.id}) - ${option.work_email || 'No Email'}` : ''}
                                inputValue={odooEmpSearchTermCreate}
                                onInputChange={handleOdooEmpSearchInputChangeCreate}
                                onChange={handleOdooEmpSelectionCreate}
                                loading={isLoadingOdooEmpsCreate}
                                disabled={!createUserForm.tenant_id || isCreating}
                                renderInput={(params) => (
                                    <TextField {...params} label="Search Odoo Employee" variant="outlined" margin="dense"
                                        InputProps={{ ...params.InputProps,
                                            endAdornment: (<>{isLoadingOdooEmpsCreate ? <CircularProgress color="inherit" size={20} /> : null}{params.InputProps.endAdornment}</>)
                                        }} />
                                )}
                                renderOption={(props, option) => (<li {...props} key={option.id}><Box><Typography variant="body2">{option.name} (ID: {option.id})</Typography><Typography variant="caption" color="textSecondary">{option.job_title || 'No Title'} - {option.work_email || 'No Email'}</Typography></Box></li>)}
                                isOptionEqualToValue={(option, value) => option.id === value.id}
                                noOptionsText={!createUserForm.tenant_id ? "Select a tenant first" : (odooEmpSearchTermCreate.length < 2 ? "Type min 2 chars" : "No employees found")}
                            />
                        </Grid>
                        <Grid item xs={12} sm={5}><TextField margin="dense" name="odoo_employee_id" label="Selected Odoo Emp. ID" type="number" fullWidth variant="outlined" size="small" value={createUserForm.odoo_employee_id} onChange={handleCreateFormChange} InputProps={{ readOnly: true }} helperText="Populated by search" /></Grid>
                        <Grid item xs={12} sm={6}><TextField margin="dense" name="job_title" label="Job Title (SaaS)" type="text" fullWidth variant="outlined" size="small" value={createUserForm.job_title} onChange={handleCreateFormChange} /></Grid>
                        <Grid item xs={12} sm={6}><TextField margin="dense" name="phone" label="Phone (SaaS)" type="tel" fullWidth variant="outlined" size="small" value={createUserForm.phone} onChange={handleCreateFormChange} /></Grid>
                        <Grid item xs={12} sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, justifyContent: 'space-around', pt: 1 }}>
                            <FormControlLabel control={<Switch checked={createUserForm.is_admin} onChange={handleCreateFormChange} name="is_admin" />} label="SaaS Admin?" />
                            <FormControlLabel control={<Switch checked={createUserForm.is_active} onChange={handleCreateFormChange} name="is_active" />} label="SaaS Active?" />
                        </Grid>
                    </Grid>
                </DialogContent>
                <DialogActions sx={{ p: '16px 24px' }}><Button onClick={handleCloseCreateModal} color="inherit" disabled={isCreating}>Cancel</Button><Button type="submit" variant="contained" color="primary" disabled={isCreating}>{isCreating ? <CircularProgress size={22} /> : "Create User"}</Button></DialogActions>
            </Box>
        </Dialog>
    );

    const renderEditUserModal = () => (
        currentUserEditing && (
            <Dialog open={openEditModal} onClose={handleCloseEditModal} maxWidth="md" fullWidth>
                <DialogTitle>Edit User: {currentUserEditing.email}</DialogTitle>
                <Box component="form" onSubmit={handleEditSubmit} noValidate>
                    <DialogContent>
                        {editError && <Alert severity="error" sx={{ mb: 2 }}>{editError}</Alert>}
                        <Grid container spacing={2}>
                            {/* Fields similar to create, but pre-filled and password is optional new_password */}
                            <Grid item xs={12} sm={6}><TextField autoFocus margin="dense" name="email" label="Email Address" type="email" fullWidth variant="outlined" size="small" value={editUserForm.email} onChange={handleEditFormChange} required error={!!(editError && !editUserForm.email.trim())}/></Grid>
                            <Grid item xs={12} sm={6}><TextField margin="dense" name="full_name" label="Full Name" type="text" fullWidth variant="outlined" size="small" value={editUserForm.full_name} onChange={handleEditFormChange} /></Grid>
                            <Grid item xs={12} sm={6}><TextField margin="dense" name="new_password" label="New Password (Optional)" type="password" fullWidth variant="outlined" size="small" value={editUserForm.new_password} onChange={handleEditFormChange} helperText="Leave blank to keep. Min 8 if changing." error={!!(editError && editUserForm.new_password && editUserForm.new_password.length < 8)}/></Grid>
                            <Grid item xs={12} sm={6}>
                                <FormControl fullWidth margin="dense" size="small" required error={!!(editError && !editUserForm.tenant_id)}>
                                    <InputLabel id="edit-tenant-select-label">Tenant *</InputLabel>
                                    <Select labelId="edit-tenant-select-label" name="tenant_id" value={editUserForm.tenant_id} label="Tenant *" onChange={handleEditFormChange}>
                                        {allTenants.map((tenant) => (<MenuItem key={tenant.id} value={tenant.id}>{tenant.name} (ID: {tenant.id})</MenuItem>))}
                                    </Select>
                                </FormControl>
                            </Grid>
                            {/* TODO: Add Odoo Employee Search/Link for Edit Modal if desired */}
                            <Grid item xs={12} sm={6}><TextField margin="dense" name="odoo_employee_id" label="Odoo Employee ID (Optional)" type="number" fullWidth variant="outlined" size="small" value={editUserForm.odoo_employee_id} onChange={handleEditFormChange} /></Grid>
                            <Grid item xs={12} sm={6}><TextField margin="dense" name="job_title" label="Job Title (SaaS)" type="text" fullWidth variant="outlined" size="small" value={editUserForm.job_title} onChange={handleEditFormChange} /></Grid>
                            <Grid item xs={12} sm={6}><TextField margin="dense" name="phone" label="Phone (SaaS)" type="tel" fullWidth variant="outlined" size="small" value={editUserForm.phone} onChange={handleEditFormChange} /></Grid>

                            <Grid item xs={12} sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, justifyContent: 'space-around', pt: 1 }}>
                                <FormControlLabel control={<Switch checked={editUserForm.is_admin} onChange={handleEditFormChange} name="is_admin" />} label="SaaS Admin?" />
                                <FormControlLabel control={<Switch checked={editUserForm.is_active} onChange={handleEditFormChange} name="is_active" />} label="SaaS Active?" />
                            </Grid>
                        </Grid>
                    </DialogContent>
                    <DialogActions sx={{ p: '16px 24px' }}><Button onClick={handleCloseEditModal} color="inherit" disabled={isEditing}>Cancel</Button><Button type="submit" variant="contained" color="primary" disabled={isEditing}>{isEditing ? <CircularProgress size={22} /> : "Save Changes"}</Button></DialogActions>
                </Box>
            </Dialog>
        )
    );

    return (
        <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
            <Paper elevation={3} sx={{ padding: { xs: 2, sm: 3 } }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="h4" component="h1" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                        <GroupAddIcon sx={{ mr: 1, fontSize: '2.2rem' }} color="primary" /> User Management
                    </Typography>
                    <Button variant="contained" startIcon={<AddCircleOutlineIcon />} onClick={handleOpenCreateModal}>
                        Create New User
                    </Button>
                </Box>
                <Divider sx={{ my: 2 }} />

                {pageError && <Alert severity="error" sx={{ mb: 2 }}>{pageError}</Alert>}
                {successMessage && <Alert severity="success" sx={{ mb: 2 }}>{successMessage}</Alert>}

                {isLoading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', my: 3 }}><CircularProgress /></Box>
                ) : users.length === 0 && !pageError ? (
                    <Typography sx={{ my: 2, fontStyle: 'italic', textAlign: 'center' }}>
                        No users found. Click "Create New User" to add one.
                    </Typography>
                ) : !pageError ? (
                    renderUserTable()
                ) : null}
            </Paper>

            {renderCreateUserModal()}
            {renderEditUserModal()}
        </Container>
    );
}

export default AdminUsersPage;