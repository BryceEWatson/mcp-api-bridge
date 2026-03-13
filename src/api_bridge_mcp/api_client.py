"""Centralized HTTP client for JSONPlaceholder API.

This module provides a clean API layer that can be swapped out for any
other REST API. Buyers of this MCP server would replace this file with
their own API implementation.
"""

import httpx
from typing import Any, Optional


def handle_api_error(e: Exception) -> str:
    """Map API exceptions to actionable error messages.

    Args:
        e: Exception caught from API call.

    Returns:
        Human-readable error message suitable for Claude/AI assistant.

    Examples:
        >>> handle_api_error(httpx.HTTPStatusError(...404...))
        'Resource not found (404). Please check the ID and try again.'
    """
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return "Resource not found (404). Please check the ID and try again."
        elif status == 403:
            return "Permission denied (403). You don't have access to this resource."
        elif status == 429:
            return "Rate limit exceeded (429). Please wait before retrying."
        elif status == 400:
            return "Bad request (400). Check your input parameters."
        elif status >= 500:
            return f"API server error ({status}). The service is temporarily unavailable."
        else:
            return f"HTTP error {status}. Please try again."
    elif isinstance(e, httpx.TimeoutException):
        return "Request timed out. The API is taking too long to respond."
    elif isinstance(e, httpx.ConnectError):
        return "Connection failed. Check your network or the API endpoint."
    elif isinstance(e, httpx.RequestError):
        return f"Request error: {str(e)}"
    else:
        return f"Unexpected error: {str(e)}"


class APIClient:
    """Async HTTP client for JSONPlaceholder API.

    Provides a clean interface for making requests to the API with
    centralized error handling, timeouts, and base URL configuration.

    Usage:
        async with APIClient() as client:
            posts = await client.get("/posts")
    """

    def __init__(self, base_url: str = "https://jsonplaceholder.typicode.com", timeout: int = 30):
        """Initialize the API client.

        Args:
            base_url: Base URL for the API (default: JSONPlaceholder)
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url
        self.timeout = httpx.Timeout(timeout)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "APIClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the underlying httpx client."""
        if not self._client:
            raise RuntimeError("APIClient must be used as an async context manager")
        return self._client

    async def get(self, endpoint: str, params: Optional[dict] = None) -> dict | list:
        """Make a GET request.

        Args:
            endpoint: API endpoint (e.g., "/posts", "/posts/1")
            params: Optional query parameters

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        response = await self.client.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()

    async def post(self, endpoint: str, json: dict) -> dict:
        """Make a POST request.

        Args:
            endpoint: API endpoint
            json: Request body as dict

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        response = await self.client.post(endpoint, json=json)
        response.raise_for_status()
        return response.json()

    async def put(self, endpoint: str, json: dict) -> dict:
        """Make a PUT request.

        Args:
            endpoint: API endpoint
            json: Request body as dict

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        response = await self.client.put(endpoint, json=json)
        response.raise_for_status()
        return response.json()

    async def patch(self, endpoint: str, json: dict) -> dict:
        """Make a PATCH request.

        Args:
            endpoint: API endpoint
            json: Request body as dict

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        response = await self.client.patch(endpoint, json=json)
        response.raise_for_status()
        return response.json()


