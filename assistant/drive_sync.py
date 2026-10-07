"""
Google Drive sync helper — uploads local files to Drive via the Drive HTTP API.

The OAuth access token is obtained from the connected Google Drive MCP connector
by reading it from the environment variable GOOGLE_DRIVE_ACCESS_TOKEN, which the
ChatAI server injects when a Drive session is active.  If no token is available,
all operations silently return None so the pipeline is not broken.
"""
import base64, os, pathlib, mimetypes, json, time
try:
    import requests as _req
except ImportError:
    _req = None

_DRIVE_API = "https://www.googleapis.com/drive/v3"
_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
_ROOT_FOLDER_ID = "1XjYBmP4yG0RyWcm7b2tFAKO8-ke6ASMT"  # My Drive/AI

_MIME_MAP = {
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.gsz':  'application/zip',
    '.dxf':  'application/dxf',
    '.pdf':  'application/pdf',
}


def _token():
    return os.environ.get('GOOGLE_DRIVE_ACCESS_TOKEN') or os.environ.get('GD_TOKEN')


def _headers():
    tok = _token()
    if not tok:
        return None
    return {'Authorization': f'Bearer {tok}', 'Accept': 'application/json'}


def _get_or_create_folder(name: str, parent_id: str) -> str | None:
    """Return folder ID, creating it if needed."""
    h = _headers()
    if not h or not _req:
        return None
    q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
    resp = _req.get(f"{_DRIVE_API}/files", params={'q': q, 'fields': 'files(id,name)'}, headers=h, timeout=15)
    if resp.ok:
        files = resp.json().get('files', [])
        if files:
            return files[0]['id']
    # create
    body = {'name': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
    r2 = _req.post(f"{_DRIVE_API}/files", json=body, headers=h, timeout=15)
    if r2.ok:
        return r2.json().get('id')
    return None


def upload_file(local_path: str, project_name: str = '') -> dict | None:
    """
    Upload a local file to Drive at  My Drive/AI/<project_name>/<filename>.
    Returns {'id': ..., 'webViewLink': ...} or None on failure / no token.
    """
    h = _headers()
    if not h or not _req:
        return None
    path = pathlib.Path(local_path)
    if not path.exists():
        return None

    # resolve destination folder
    parent_id = _ROOT_FOLDER_ID
    if project_name:
        proj_folder = _get_or_create_folder(project_name, parent_id)
        if proj_folder:
            parent_id = proj_folder

    suffix = path.suffix.lower()
    mime = _MIME_MAP.get(suffix) or mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
    meta = {'name': path.name, 'parents': [parent_id]}

    # multipart upload
    boundary = '---boundary_chatai_drive---'
    meta_part = (
        f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'
        + json.dumps(meta) + '\r\n'
    )
    with open(local_path, 'rb') as f:
        file_bytes = f.read()
    file_part = (
        f'--{boundary}\r\nContent-Type: {mime}\r\n\r\n'
    ).encode() + file_bytes + f'\r\n--{boundary}--'.encode()
    body = meta_part.encode() + file_part
    upload_headers = {**h, 'Content-Type': f'multipart/related; boundary={boundary}'}
    resp = _req.post(
        f"{_UPLOAD_API}/files",
        params={'uploadType': 'multipart', 'fields': 'id,webViewLink,name'},
        data=body, headers=upload_headers, timeout=60,
    )
    if resp.ok:
        return resp.json()
    return None


def upload_files(paths: list[str], project_name: str = '') -> list[dict]:
    """Upload multiple files; returns list of results (None entries skipped)."""
    results = []
    for p in paths:
        r = upload_file(p, project_name)
        if r:
            results.append(r)
    return results
