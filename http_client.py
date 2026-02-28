import logging
import time
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when the Modrinth API returns a rate limit error."""
    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after} seconds.")


class APIError(Exception):
    """Raised when an API call fails."""
    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


def create_session() -> requests.Session:
    """Create a requests session with connection pooling and retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_session: requests.Session | None = None


def get_session() -> requests.Session:
    """Get or create the global requests session."""
    global _session
    if _session is None:
        _session = create_session()
    return _session


def close_session() -> None:
    """Close the global requests session."""
    global _session
    if _session is not None:
        _session.close()
        _session = None


def handle_response(response: requests.Response) -> dict[str, Any]:
    """Handle API response and check for errors."""
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 60))
        raise RateLimitError(retry_after)
    
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        raise APIError(f"API request failed: {e}", response.status_code) from e
    
    return response.json()


def get_with_retry(url: str, params: dict[str, Any] | None = None, max_retries: int = 3) -> list[dict[str, Any]] | dict[str, Any]:
    """Make a GET request with retry logic and rate limit handling."""
    session = get_session()
    last_error: Exception | None = None
    
    for attempt in range(max_retries):
        try:
            response = session.get(url, params=params, timeout=30)
            return handle_response(response)
        except RateLimitError as e:
            logger.warning(f"Rate limited, waiting {e.retry_after}s before retry...")
            time.sleep(e.retry_after)
        except requests.RequestException as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                time.sleep(wait_time)
    
    raise APIError(f"Failed after {max_retries} retries: {last_error}") from last_error


def validate_url(url: str) -> bool:
    """Validate that a URL is properly formatted and uses allowed schemes."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme in ("http", "https")) and bool(parsed.netloc)
    except Exception:
        return False


def validate_modrinth_url(url: str) -> bool:
    """Validate that a URL is a valid Modrinth URL."""
    if not validate_url(url):
        return False
    parsed = urlparse(url)
    return "modrinth.com" in parsed.netloc
