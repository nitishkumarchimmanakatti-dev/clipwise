"""Automated YouTube Shorts uploader using YouTube Data API v3 and Google OAuth 2.0."""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import Flow, InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False


YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

BASE_DIR = Path(__file__).resolve().parent.parent
CLIENT_SECRET_CANDIDATES = [
    BASE_DIR / "client_secret.json",
    Path("client_secret.json"),
    Path("/app/client_secret.json"),
]
TOKEN_FILE_CANDIDATES = [
    BASE_DIR / "youtube_token.json",
    Path("youtube_token.json"),
    Path("/app/youtube_token.json"),
]


def _get_client_secret_path() -> Optional[Path]:
    for p in CLIENT_SECRET_CANDIDATES:
        if p.exists():
            return p
    return None


def _get_token_file_path() -> Path:
    for p in TOKEN_FILE_CANDIDATES:
        if p.exists():
            return p
    return TOKEN_FILE_CANDIDATES[0]


def is_youtube_configured() -> bool:
    """Check if YouTube credentials or tokens are present."""
    if not GOOGLE_LIBS_AVAILABLE:
        return False

    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")
    if client_id and client_secret and refresh_token:
        return True

    token_path = _get_token_file_path()
    if token_path.exists():
        return True

    return _get_client_secret_path() is not None


def get_youtube_credentials() -> Optional[Any]:
    """Retrieve and refresh Google OAuth 2.0 credentials."""
    if not GOOGLE_LIBS_AVAILABLE:
        return None

    # 1. Check environment variables (ideal for Railway cloud deployment)
    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

    if client_id and client_secret and refresh_token:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=YOUTUBE_SCOPES,
        )
        try:
            creds.refresh(Request())
            return creds
        except Exception as e:
            print(f"[YouTube Auth] Failed refreshing credentials from env vars: {e}")

    # 2. Check saved token file
    token_path = _get_token_file_path()
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), YOUTUBE_SCOPES)
            if creds:
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    # Re-save refreshed token
                    with open(token_path, "w", encoding="utf-8") as f:
                        f.write(creds.to_json())
                return creds
        except Exception as e:
            print(f"[YouTube Auth] Failed loading token from {token_path}: {e}")

    return None


def get_youtube_service():
    """Build and return an authenticated YouTube Data API v3 service."""
    creds = get_youtube_credentials()
    if not creds or not creds.valid:
        raise PermissionError(
            "YouTube is not authenticated. Please connect your YouTube account in Settings "
            "or configure client_secret.json / YOUTUBE_REFRESH_TOKEN."
        )
    return build("youtube", "v3", credentials=creds)


def check_channel_auth_status() -> Dict[str, Any]:
    """Check channel authentication and return profile info."""
    if not GOOGLE_LIBS_AVAILABLE:
        return {
            "authenticated": False,
            "error": "Google API client libraries are not installed.",
        }

    try:
        service = get_youtube_service()
        res = service.channels().list(part="snippet,statistics", mine=True).execute()
        items = res.get("items", [])
        if items:
            channel = items[0]
            snippet = channel.get("snippet", {})
            stats = channel.get("statistics", {})
            return {
                "authenticated": True,
                "channel_id": channel.get("id"),
                "channel_title": snippet.get("title", "Unknown Channel"),
                "custom_url": snippet.get("customUrl", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                "subscriber_count": stats.get("subscriberCount", "0"),
                "video_count": stats.get("videoCount", "0"),
            }
        return {
            "authenticated": False,
            "error": "No YouTube channel found for the authenticated Google account.",
        }
    except Exception as e:
        return {
            "authenticated": False,
            "has_credentials_file": _get_client_secret_path() is not None,
            "error": str(e),
        }


def get_oauth_authorization_url(redirect_uri: str) -> Dict[str, str]:
    """Generate a Google OAuth authorization URL for the user to grant permissions."""
    if not GOOGLE_LIBS_AVAILABLE:
        raise RuntimeError("Google API client libraries are not installed.")

    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
    secret_path = _get_client_secret_path()

    if client_id and client_secret:
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        }
        flow = Flow.from_client_config(client_config, scopes=YOUTUBE_SCOPES, redirect_uri=redirect_uri)
    elif secret_path:
        flow = Flow.from_client_secrets_file(str(secret_path), scopes=YOUTUBE_SCOPES, redirect_uri=redirect_uri)
    else:
        raise ValueError(
            "Missing client credentials. Please provide client_secret.json or set "
            "YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET."
        )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return {"auth_url": auth_url, "state": state}


def exchange_oauth_code(code: str, redirect_uri: str) -> Dict[str, Any]:
    """Exchange OAuth authorization code for credentials and save youtube_token.json."""
    if not GOOGLE_LIBS_AVAILABLE:
        raise RuntimeError("Google API client libraries are not installed.")

    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
    secret_path = _get_client_secret_path()

    if client_id and client_secret:
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        }
        flow = Flow.from_client_config(client_config, scopes=YOUTUBE_SCOPES, redirect_uri=redirect_uri)
    elif secret_path:
        flow = Flow.from_client_secrets_file(str(secret_path), scopes=YOUTUBE_SCOPES, redirect_uri=redirect_uri)
    else:
        raise ValueError("Missing client credentials.")

    flow.fetch_token(code=code)
    creds = flow.credentials

    token_path = _get_token_file_path()
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    return {
        "success": True,
        "token_saved_to": str(token_path),
        "refresh_token": creds.refresh_token,
    }


def save_client_secret_file(content: str) -> Path:
    """Save raw client secret JSON content to client_secret.json."""
    data = json.loads(content) if isinstance(content, str) else content
    target_path = BASE_DIR / "client_secret.json"
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return target_path


def upload_clip_to_youtube(
    video_path: Path,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    privacy_status: str = "public",
) -> Dict[str, Any]:
    """Upload a video clip to YouTube Shorts.
    
    Args:
        video_path: Path to the rendered .mp4 file.
        title: Title of the video (max 100 characters).
        description: Description text.
        tags: List of hashtag/tag strings.
        privacy_status: 'public', 'unlisted', or 'private'.
        
    Returns:
        dict with video_id, url (https://youtube.com/shorts/{id}), and metadata.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    youtube = get_youtube_service()

    # Format title: ensure it fits within 100 characters and includes #Shorts
    clean_title = title.strip()
    if "#Shorts" not in clean_title and "#shorts" not in clean_title:
        if len(clean_title) + len(" #Shorts") <= 100:
            clean_title = f"{clean_title} #Shorts"
        else:
            clean_title = f"{clean_title[:91]}... #Shorts"
    clean_title = clean_title[:100]

    # Format description with hashtags
    clean_desc = description.strip()
    if "#Shorts" not in clean_desc:
        clean_desc = f"{clean_desc}\n\n#Shorts #Viral"

    all_tags = list(tags or [])
    if "Shorts" not in all_tags:
        all_tags.append("Shorts")
    if "Viral" not in all_tags:
        all_tags.append("Viral")

    body = {
        "snippet": {
            "title": clean_title,
            "description": clean_desc,
            "tags": all_tags,
            "categoryId": "22",  # People & Blogs / Entertainment
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=-1,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()

    video_id = response.get("id")
    shorts_url = f"https://youtube.com/shorts/{video_id}"

    return {
        "video_id": video_id,
        "url": shorts_url,
        "title": clean_title,
        "privacy": privacy_status,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "status": "uploaded",
    }
