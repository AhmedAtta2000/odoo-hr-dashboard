# In backend/odoo_client.py
import httpx
from fastapi import HTTPException, status, Response ,UploadFile  
from fastapi.responses import StreamingResponse # Add StreamingResponse
import logging
from typing import Optional, Dict, Any, AsyncGenerator, Tuple, List

logger = logging.getLogger(__name__)

# Define a timeout for requests (important!)
DEFAULT_TIMEOUT = 30.0 # seconds

async def call_odoo_api(
    base_url: str,
    endpoint: str, # e.g., "/ess/api/employee/5"
    method: str = "GET",
    api_key: Optional[str] = None, # Decrypted API Key/Token
    payload: Optional[Dict[str, Any]] = None # For POST/PUT requests
) -> Dict[str, Any]:
    """Helper function to make authenticated calls to the Odoo ESS API."""

    full_url = f"{base_url.rstrip('/')}{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            logger.info(f"Calling Odoo API: {method} {full_url}")
            response = await client.request(
                method=method,
                url=full_url,
                headers=headers,
                json=payload if payload else None # Send payload as JSON body if provided
            )
            response.raise_for_status() # Raise exception for 4xx or 5xx status codes

            logger.info(f"Odoo API response status: {response.status_code}")
            return response.json() # Return parsed JSON response

    except httpx.TimeoutException:
        logger.error(f"Odoo API call timed out: {method} {full_url}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request to Odoo timed out."
        )
    except httpx.RequestError as e:
        logger.error(f"Odoo API request error: {method} {full_url} - {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not connect to Odoo service: {e}"
        )
    except httpx.HTTPStatusError as e:
        # Handle specific Odoo errors (4xx, 5xx)
        logger.error(f"Odoo API returned error status {e.response.status_code}: {method} {full_url} - Response: {e.response.text[:200]}") # Log first 200 chars
        error_detail = "Error communicating with Odoo."
        try:
            # Try to parse Odoo's JSON error response
            odoo_error = e.response.json()
            error_detail = odoo_error.get("message", error_detail)
        except Exception:
             pass # Ignore if response is not JSON

        # Forward Odoo's status code if it's a client error (4xx)
        forward_status = e.response.status_code if 400 <= e.response.status_code < 500 else status.HTTP_502_BAD_GATEWAY

        raise HTTPException(
            status_code=forward_status,
            detail=f"Odoo API Error: {error_detail}"
        )
    except Exception as e:
        # Catch-all for other unexpected errors
        logger.exception(f"Unexpected error during Odoo API call: {method} {full_url}") # Log full traceback
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while contacting Odoo."
        )

# --- NEW function for downloading/streaming ---
async def stream_odoo_api_file(
    base_url: str,
    endpoint: str,
    api_key: Optional[str] = None,
) -> StreamingResponse: # Return type is StreamingResponse
    """Helper to stream a file response from the Odoo ESS API."""

    full_url = f"{base_url.rstrip('/')}{endpoint}"
    headers = {} # Start with empty headers for the request
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        # We need the client instance outside the 'async with' to access the response later
        client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)

        # Use streaming request
        request = client.build_request("GET", full_url, headers=headers)
        response = await client.send(request, stream=True)

        response.raise_for_status() # Check for 4xx/5xx errors

        # Check Content-Type if needed (optional)
        content_type = response.headers.get('content-type', 'application/octet-stream')
        logger.info(f"Odoo download response status: {response.status_code}, Content-Type: {content_type}")

        # Prepare headers to forward to the client, especially Content-Disposition
        forward_headers = {
            "Content-Type": content_type,
             # Copy Content-Disposition if Odoo provided it
            "Content-Disposition": response.headers.get('content-disposition', 'attachment')
        }
        # Copy Content-Length if provided (though streaming might alter it)
        if 'content-length' in response.headers:
            forward_headers['Content-Length'] = response.headers['content-length']


        # Define an async generator to stream the content
        async def iter_content() -> AsyncGenerator[bytes, None]:
             try:
                 async for chunk in response.aiter_bytes():
                     yield chunk
             finally:
                 await response.aclose() # Ensure response is closed
                 await client.aclose()   # Ensure client is closed


        # Return a StreamingResponse
        return StreamingResponse(
             iter_content(),
             status_code=response.status_code,
             headers=forward_headers,
             media_type=content_type # Also set media_type here
             )

    except httpx.TimeoutException:
         # Clean up client if timeout occurs before response streaming starts
         if 'client' in locals() and client.is_closed is False: await client.aclose()
         logger.error(f"Odoo API file download timed out: GET {full_url}")
         raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Request to Odoo for file download timed out.")
    except httpx.RequestError as e:
         if 'client' in locals() and client.is_closed is False: await client.aclose()
         logger.error(f"Odoo API file download request error: GET {full_url} - {e}")
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Could not connect to Odoo service for file download: {e}")
    except httpx.HTTPStatusError as e:
         # Ensure resources are closed even on HTTP error before streaming
         if 'response' in locals(): await response.aclose()
         if 'client' in locals() and client.is_closed is False: await client.aclose()
         logger.error(f"Odoo API returned error status {e.response.status_code} during file download: GET {full_url} - Response: {e.response.text[:200]}")
         error_detail = "Error downloading file from Odoo."
         try: odoo_error = e.response.json(); error_detail = odoo_error.get("message", error_detail)
         except Exception: pass
         forward_status = e.response.status_code if 400 <= e.response.status_code < 500 else status.HTTP_502_BAD_GATEWAY
         raise HTTPException(status_code=forward_status, detail=f"Odoo API Error: {error_detail}")
    except Exception as e:
         if 'response' in locals(): await response.aclose()
         if 'client' in locals() and client.is_closed is False: await client.aclose()
         logger.exception(f"Unexpected error during Odoo API file download: GET {full_url}")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while downloading the file from Odoo.")


# --- NEW function for sending multipart/form-data ---
async def call_odoo_api_multipart(
    base_url: str,
    endpoint: str, # e.g., "/ess/api/expenses"
    api_key: Optional[str] = None,
    # files should be a list of tuples:
    # [('file_form_name', (filename, file_content_bytes, content_type)), ...]
    files: Optional[List[Tuple[str, Tuple[str, bytes, str]]]] = None,
    # data should be a dictionary for other form fields
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]: # Expecting a JSON response from Odoo connector
    """Helper to make multipart/form-data calls to Odoo ESS API (e.g., for file uploads)."""

    full_url = f"{base_url.rstrip('/')}{endpoint}"
    headers = {} # Content-Type will be set by httpx for multipart
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # httpx can build multipart from dict for 'files' and 'data'
    # 'files' format: {'form_field_name_for_file': (filename, file_bytes, content_type)}
    # We'll transform our 'files' list into this dict format
    files_dict = {}
    if files:
        for file_form_name, file_tuple in files:
            files_dict[file_form_name] = file_tuple

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            logger.info(f"Calling Odoo API (Multipart): POST {full_url} with data: {data}, files: {[f_info[0] for f_info in files_dict.values()] if files_dict else 'None'}")

            response = await client.post(
                full_url,
                headers=headers,
                data=data,    # For regular form fields
                files=files_dict if files_dict else None # For file parts
            )
            response.raise_for_status() # Raise for 4xx/5xx

            logger.info(f"Odoo API (Multipart) response status: {response.status_code}")
            return response.json() # Expecting JSON response from Odoo connector

    except httpx.TimeoutException:
        logger.error(f"Odoo API (Multipart) call timed out: POST {full_url}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Request to Odoo timed out.")
    except httpx.RequestError as e:
        logger.error(f"Odoo API (Multipart) request error: POST {full_url} - {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Could not connect to Odoo service: {e}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Odoo API (Multipart) returned error {e.response.status_code}: POST {full_url} - Response: {e.response.text[:200]}")
        error_detail = "Error communicating with Odoo."
        try: odoo_error = e.response.json(); error_detail = odoo_error.get("message", error_detail)
        except Exception: pass
        forward_status = e.response.status_code if 400 <= e.response.status_code < 500 else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=forward_status, detail=f"Odoo API Error: {error_detail}")
    except Exception as e:
        logger.exception(f"Unexpected error during Odoo API (Multipart) call: POST {full_url}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while contacting Odoo.")