// In frontend/src/components/DocumentsPage.js
import React, { useState, useEffect, useRef, useCallback } from 'react'; // Added useCallback
import axios from 'axios';
import './DocumentsPage.css'; // Your custom CSS

function DocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState('');

  const [documentType, setDocumentType] = useState('');
  const [fileToUpload, setFileToUpload] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState('');
  const fileInputRef = useRef(null);

  const [downloadingId, setDownloadingId] = useState(null);
  const [downloadError, setDownloadError] = useState('');

  // --- State for Delete Confirmation ---
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false); // To control modal/confirm visibility
  const [docToDelete, setDocToDelete] = useState(null); // Stores { id, filename }
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const [deleteSuccess, setDeleteSuccess] = useState('');
  // ------------------------------------

  const DOC_TYPES = ["ID Card", "Contract", "Certification", "Other"]; // Kept as is

  const fetchDocuments = useCallback(async () => { // Added useCallback
    setLoadingList(true);
    setListError('');
    setDeleteSuccess(''); // Clear delete success message on refresh
    setDeleteError('');   // Clear delete error message on refresh
    try {
      const response = await axios.get('/api/v1/documents'); // This now fetches from Odoo via FastAPI
      setDocuments(response.data || []);
    } catch (err) {
      console.error("Error fetching documents:", err);
      setListError(err.response?.data?.detail || "Could not load document list.");
      setDocuments([]);
    } finally {
      setLoadingList(false);
    }
  }, []); // fetchDocuments doesn't change

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      const allowedTypes = ["image/jpeg", "image/png", "application/pdf"];
      if (!allowedTypes.includes(file.type)) {
        setUploadError("Invalid file type (JPG, PNG, PDF only).");
        setFileToUpload(null);
        if (fileInputRef.current) { fileInputRef.current.value = ""; }
        return;
      }
      if (file.size > 10 * 1024 * 1024) { // Example: 10MB limit
        setUploadError("File is too large. Maximum size is 10MB.");
        setFileToUpload(null);
        if (fileInputRef.current) { fileInputRef.current.value = ""; }
        return;
      }
      setUploadError('');
      setFileToUpload(file);
    } else {
      setFileToUpload(null);
    }
  };

  const handleUploadSubmit = async (event) => {
    event.preventDefault();
    setUploadError(''); setUploadSuccess('');
    setDownloadError(''); setDeleteError(''); setDeleteSuccess(''); // Clear other messages

    if (!documentType || !fileToUpload) {
      setUploadError("Please select a document type and a file.");
      return;
    }
    setIsUploading(true);
    const formData = new FormData();
    formData.append('document_type', documentType);
    formData.append('file', fileToUpload);
    try {
      const response = await axios.post('/api/v1/documents', formData); // Uploads to Odoo via FastAPI
      setUploadSuccess(response.data.message || "Document uploaded successfully!");
      fetchDocuments(); // Refresh list
      setDocumentType('');
      setFileToUpload(null);
      if (fileInputRef.current) { fileInputRef.current.value = ""; }
    } catch (err) {
      console.error("Error uploading document:", err);
      setUploadError(err.response?.data?.detail || "Could not upload document.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDownload = async (docId, filename) => { /* ... (existing, no change needed for this step) ... */
       if (downloadingId) return;
       setDownloadingId(docId);
       setDownloadError(''); setUploadError(''); setUploadSuccess(''); setDeleteError(''); setDeleteSuccess('');
       try {
           const response = await axios.get(`/api/v1/document/${docId}/download`, {
               responseType: 'blob',
           });
           const url = window.URL.createObjectURL(new Blob([response.data]));
           const link = document.createElement('a');
           link.href = url;
           const contentDisposition = response.headers['content-disposition'];
           let downloadFilename = filename;
           if (contentDisposition) {
               const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i);
               if (filenameMatch && filenameMatch.length > 1) { downloadFilename = filenameMatch[1]; }
           }
           link.setAttribute('download', downloadFilename);
           document.body.appendChild(link); link.click(); link.parentNode.removeChild(link);
           window.URL.revokeObjectURL(url);
       } catch (err) {
           console.error(`Error downloading document ${docId}:`, err);
           let errMsg = `Could not download ${filename}. `;
            if (err.response && err.response.status === 404) errMsg += " File not found or access denied.";
            else if (err.response && err.response.data) {
                try { const errorJson = JSON.parse(await err.response.data.text()); errMsg += ` ${errorJson.detail || ''}`;}
                catch (parseErr) { /* Do nothing if not JSON */ }
            }
           setDownloadError(errMsg.trim());
       } finally {
           setDownloadingId(null);
       }
  };

  const formatDate = (dateString) => { /* ... (existing, no change) ... */
      if (!dateString) return 'N/A';
      try {
          return new Date(dateString).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
      } catch (e) {
          return 'Invalid Date';
      }
  };

  // --- Delete Handlers ---
  const openDeleteDialog = (doc) => {
    setDocToDelete(doc); // doc should be { id, filename }
    setDeleteError(''); // Clear previous delete error
    setDeleteSuccess(''); // Clear previous success
    setShowDeleteConfirm(true);
  };

  const closeDeleteDialog = () => {
    setShowDeleteConfirm(false);
    setDocToDelete(null);
  };

  const confirmDeleteDocument = async () => {
    if (!docToDelete) return;
    setIsDeleting(true);
    setDeleteError('');
    setDeleteSuccess('');
    try {
      // FastAPI endpoint expects the Odoo ir.attachment ID
      const response = await axios.delete(`/api/v1/document/${docToDelete.id}`);
      setDeleteSuccess(response.data.message || `Document "${docToDelete.filename}" deleted successfully.`);
      fetchDocuments(); // Refresh the list
    } catch (err) {
      console.error("Error deleting document:", err);
      setDeleteError(err.response?.data?.detail || `Failed to delete document "${docToDelete.filename}".`);
    } finally {
      setIsDeleting(false);
      closeDeleteDialog();
    }
  };
  // ----------------------

  return (
    <div className="documents-container">
      <h2>My Documents</h2>

      {/* Upload Section */}
      <div className="upload-section">
        <h3>Upload New Document</h3>
        {uploadError && <p className="error-message">{uploadError}</p>}
        {uploadSuccess && <p className="success-message">{uploadSuccess}</p>}
        <form onSubmit={handleUploadSubmit} className="upload-form">
          {/* ... (existing upload form inputs) ... */}
            <div className="form-group">
                <label htmlFor="docType">Document Type:</label>
                <select id="docType" value={documentType} onChange={(e) => setDocumentType(e.target.value)} required disabled={isUploading} >
                    <option value="" disabled>-- Select Type --</option>
                    {DOC_TYPES.map(type => <option key={type} value={type}>{type}</option>)}
                </select>
            </div>
            <div className="form-group">
                <label htmlFor="docFile">File (PDF, JPG, PNG):</label>
                <input type="file" id="docFile" ref={fileInputRef} onChange={handleFileChange} accept=".jpg,.jpeg,.png,.pdf" required disabled={isUploading} />
                {fileToUpload && <span className="file-name">Selected: {fileToUpload.name}</span>}
            </div>
            <button type="submit" disabled={isUploading || !fileToUpload || !documentType}>
                {isUploading ? 'Uploading...' : 'Upload Document'}
            </button>
        </form>
      </div>

      {/* List Section */}
      <div className="list-section">
        <h3>Uploaded Documents</h3>
        {listError && <p className="error-message">{listError}</p>}
        {downloadError && <p className="error-message">{downloadError}</p>}
        {deleteError && <p className="error-message">{deleteError}</p>} {/* Display delete errors */}
        {deleteSuccess && <p className="success-message">{deleteSuccess}</p>} {/* Display delete success */}

        {loadingList ? (
          <p>Loading documents...</p>
        ) : documents.length === 0 ? (
          <p>No documents uploaded yet.</p>
        ) : (
          <table className="documents-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Type</th>
                <th>Upload Date</th>
                <th>Actions</th> {/* Changed from Action to Actions */}
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td>{doc.filename}</td>
                  <td>{doc.document_type}</td>
                  <td>{formatDate(doc.upload_date)}</td>
                  <td>
                    <button
                      onClick={() => handleDownload(doc.id, doc.filename)}
                      disabled={downloadingId === doc.id}
                      className="download-button"
                    >
                      {downloadingId === doc.id ? 'Downloading...' : 'Download'}
                    </button>
                    {/* --- Add Delete Button --- */}
                    <button
                      onClick={() => openDeleteDialog(doc)} // Pass the whole doc object or needed parts
                      disabled={isDeleting && docToDelete?.id === doc.id}
                      className="delete-button" // You'll need to style this
                    >
                      {isDeleting && docToDelete?.id === doc.id ? 'Deleting...' : 'Delete'}
                    </button>
                    {/* ----------------------- */}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Delete Confirmation Dialog/Modal (Simple window.confirm for now, can be replaced with styled modal) */}
      {showDeleteConfirm && docToDelete && (
        <div className="confirm-dialog-overlay"> {/* Basic overlay style needed */}
          <div className="confirm-dialog">
            <h4>Confirm Deletion</h4>
            <p>Are you sure you want to delete the document: <strong>{docToDelete.filename}</strong>?</p>
            <p>This action cannot be undone.</p>
            <div className="confirm-dialog-actions">
              <button onClick={closeDeleteDialog} disabled={isDeleting} className="button-cancel">
                Cancel
              </button>
              <button onClick={confirmDeleteDocument} disabled={isDeleting} className="button-delete">
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DocumentsPage;