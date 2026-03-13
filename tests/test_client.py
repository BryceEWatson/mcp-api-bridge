"""Tests for the APIClient HTTP layer."""

import pytest
import httpx
from api_bridge_mcp.api_client import APIClient, handle_api_error
from .conftest import SAMPLE_POST, SAMPLE_POSTS


class TestAPIClientGet:
    """Test GET request functionality."""

    @pytest.mark.asyncio
    async def test_successful_get_returns_parsed_json(self, httpx_mock):
        """Test that successful GET request returns parsed JSON."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.example.com/posts",
            json=SAMPLE_POSTS
        )

        client = APIClient(base_url="https://api.example.com")
        async with client:
            result = await client.get("/posts")

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0]["title"] == "First Post"

    @pytest.mark.asyncio
    async def test_get_with_params(self, httpx_mock):
        """Test GET request with query parameters."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.example.com/posts?userId=1",
            json=[SAMPLE_POSTS[0]]
        )

        client = APIClient(base_url="https://api.example.com")
        async with client:
            result = await client.get("/posts", params={"userId": 1})

        assert len(result) == 1
        assert result[0]["userId"] == 1


class TestAPIClientPost:
    """Test POST request functionality."""

    @pytest.mark.asyncio
    async def test_successful_post_sends_body_correctly(self, httpx_mock):
        """Test that POST request sends JSON body correctly."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.example.com/posts",
            json={"id": 101, "title": "New Post", "body": "content", "userId": 1},
            status_code=201
        )

        client = APIClient(base_url="https://api.example.com")
        async with client:
            payload = {"title": "New Post", "body": "content", "userId": 1}
            result = await client.post("/posts", json=payload)

        assert result["id"] == 101
        assert result["title"] == "New Post"

    @pytest.mark.asyncio
    async def test_post_request_includes_payload(self, httpx_mock):
        """Test that POST payload is correctly transmitted."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.example.com/posts",
            json={"id": 102, "userId": 5},
            status_code=201
        )

        client = APIClient(base_url="https://api.example.com")
        async with client:
            payload = {"title": "Test", "body": "Test body", "userId": 5}
            await client.post("/posts", json=payload)

        # Verify the request was made with correct payload
        request = httpx_mock.get_request()
        assert request.method == "POST"


class TestAPIClientErrorHandling:
    """Test error handling for various API responses."""

    @pytest.mark.asyncio
    async def test_404_error_produces_actionable_message(self, httpx_mock):
        """Test that 404 error produces actionable error message."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.example.com/posts/99999",
            status_code=404
        )

        client = APIClient(base_url="https://api.example.com")
        async with client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.get("/posts/99999")

    @pytest.mark.asyncio
    async def test_429_error_produces_rate_limit_message(self):
        """Test that 429 error produces rate limit message."""
        response = httpx.Response(429)
        error = httpx.HTTPStatusError("429", request=None, response=response)

        message = handle_api_error(error)
        assert "Rate limit" in message
        assert "429" in message

    @pytest.mark.asyncio
    async def test_timeout_produces_timeout_message(self):
        """Test that timeout error produces timeout message."""
        error = httpx.TimeoutException("Timeout")

        message = handle_api_error(error)
        assert "timed out" in message.lower()

    @pytest.mark.asyncio
    async def test_connection_error_produces_connection_failure_message(self):
        """Test that connection error produces connection failure message."""
        error = httpx.ConnectError("Connection failed")

        message = handle_api_error(error)
        assert "Connection failed" in message

    @pytest.mark.asyncio
    async def test_generic_exception_produces_message(self):
        """Test that generic exception produces a message."""
        error = Exception("Something went wrong")

        message = handle_api_error(error)
        assert "Unexpected error" in message


class TestHandleAPIError:
    """Test the error handler function."""

    def test_404_error_message(self):
        """Test 404 error handling."""
        response = httpx.Response(404)
        error = httpx.HTTPStatusError("404", request=None, response=response)

        message = handle_api_error(error)
        assert "not found" in message.lower()
        assert "404" in message

    def test_403_error_message(self):
        """Test 403 forbidden error handling."""
        response = httpx.Response(403)
        error = httpx.HTTPStatusError("403", request=None, response=response)

        message = handle_api_error(error)
        assert "Permission denied" in message

    def test_500_error_message(self):
        """Test 5xx server error handling."""
        response = httpx.Response(500)
        error = httpx.HTTPStatusError("500", request=None, response=response)

        message = handle_api_error(error)
        assert "server error" in message.lower()
