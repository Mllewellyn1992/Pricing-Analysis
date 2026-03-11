"""
Supabase client initialization and connection management.
Reads SUPABASE_URL and SUPABASE_ANON_KEY from environment variables.
"""

import os
from typing import Optional
from supabase import create_client, Client

_client: Optional[Client] = None


def get_client() -> Optional[Client]:
    """
    Get or initialize the Supabase client.
    Returns None if SUPABASE_URL or SUPABASE_ANON_KEY are not configured.
    Uses lazy initialization for efficiency.

    Returns:
        Supabase Client instance, or None if not configured
    """
    global _client

    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_ANON_KEY", "").strip()

    if not url or not key:
        return None

    try:
        _client = create_client(url, key)
        return _client
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")
        return None


def is_configured() -> bool:
    """
    Check if Supabase is properly configured.

    Returns:
        True if both SUPABASE_URL and SUPABASE_ANON_KEY are set
    """
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    return bool(url and key)
