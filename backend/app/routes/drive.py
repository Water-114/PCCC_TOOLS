from flask import Blueprint, jsonify, request
import json
import os
import urllib.parse
import urllib.request

bp = Blueprint("drive", __name__, url_prefix="/api/drive")

DRIVE_API_URL = "https://www.googleapis.com/drive/v3/files"
DEFAULT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "1AR-EefEcZfEU_yPHHFsTDVEVy5DLQBZV")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()


def build_drive_list_url(folder_id: str) -> str:
    params = {
        "q": f"'{folder_id}' in parents and trashed=false",
        "fields": "files(id,name,mimeType,webViewLink,iconLink),nextPageToken",
        "pageSize": "1000",
        "orderBy": "name"
    }
    if GOOGLE_API_KEY:
        params["key"] = GOOGLE_API_KEY
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"{DRIVE_API_URL}?{query}"


@bp.get("/files")
def list_files():
    folder_id = request.args.get("folderId", DEFAULT_FOLDER_ID).strip()
    if not folder_id:
        return jsonify({"error": "Missing folderId."}), 400

    url = build_drive_list_url(folder_id)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            payload = resp.read().decode("utf-8")
            data = json.loads(payload)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
            error_data = json.loads(body)
            message = error_data.get("error", {}).get("message", exc.reason)
        except Exception:
            message = str(exc)
        return jsonify({"error": f"Drive API error: {message}"}), exc.code
    except Exception as exc:
        return jsonify({"error": f"Drive request failed: {exc}"}), 500

    files = data.get("files", [])
    docs = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "mimeType": item.get("mimeType"),
            "viewLink": item.get("webViewLink"),
            "iconLink": item.get("iconLink"),
        }
        for item in files
    ]

    return jsonify({"folderId": folder_id, "files": docs})
