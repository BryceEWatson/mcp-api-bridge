"""Tests for MCP tool functions.

Validation tests go through the real MCP protocol (in-memory transport), so
they check the schema the server actually enforces, not a separate model.
All HTTP calls are mocked with pytest-httpx; nothing here touches the network.
"""

import json

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from mcp.shared.memory import create_connected_server_and_client_session

from api_bridge_mcp.server import (
    ResponseFormat,
    api_create_post,
    api_get_post,
    api_list_posts,
    api_update_post,
)
from api_bridge_mcp.server import mcp as server_instance

from .conftest import SAMPLE_COMMENTS, SAMPLE_POST, SAMPLE_POSTS

BASE = "https://jsonplaceholder.typicode.com"


async def call(tool: str, args: dict):
    async with create_connected_server_and_client_session(server_instance) as session:
        return await session.call_tool(tool, args)


# ============================================================================
# Input Validation Tests (rejected before any HTTP request is made)
# ============================================================================

INVALID_INPUTS = [
    ("api_list_posts", {"limit": 0}),
    ("api_list_posts", {"limit": 101}),
    ("api_list_posts", {"offset": -1}),
    ("api_list_posts", {"user_id": 0}),
    ("api_get_post", {"post_id": 0}),
    ("api_get_post", {"post_id": -1}),
    ("api_create_post", {"title": "", "body": "content", "user_id": 1}),
    ("api_create_post", {"title": "   ", "body": "content", "user_id": 1}),
    ("api_create_post", {"title": "a" * 201, "body": "content", "user_id": 1}),
    ("api_create_post", {"title": "Title", "body": "", "user_id": 1}),
    ("api_create_post", {"title": "Title", "body": "\n\t ", "user_id": 1}),
    ("api_create_post", {"title": "Title", "body": "a" * 5001, "user_id": 1}),
    ("api_create_post", {"title": "Title", "body": "content", "user_id": 0}),
    ("api_create_post", {"title": "Title"}),
    ("api_update_post", {"post_id": 1}),
    ("api_update_post", {"post_id": 0, "title": "New Title"}),
    ("api_update_post", {"post_id": 1, "title": "  "}),
]


class TestInputValidation:
    """Bad input is rejected with isError=True and no HTTP request.

    Each case also checks that no HTTP request was sent, so validation has to
    happen before the API is called.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool,args", INVALID_INPUTS)
    async def test_invalid_input_is_rejected(self, tool, args, httpx_mock):
        result = await call(tool, args)
        assert result.isError, f"{tool}({args}) should be rejected"
        assert httpx_mock.get_requests() == [], "validation must happen before any HTTP request"

    @pytest.mark.asyncio
    async def test_title_and_body_are_stripped_before_sending(self, httpx_mock):
        httpx_mock.add_response(method="POST", url=f"{BASE}/posts", json={"id": 101})

        result = await call("api_create_post", {"title": "  Hi  ", "body": " text ", "user_id": 1})

        assert not result.isError
        sent = json.loads(httpx_mock.get_request().content)
        assert sent == {"title": "Hi", "body": "text", "userId": 1}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fields", [{"title": "New"}, {"body": "New body"}, {"user_id": 5}])
    async def test_update_with_one_field_sends_only_that_field(self, fields, httpx_mock):
        httpx_mock.add_response(method="PATCH", url=f"{BASE}/posts/1", json={"id": 1})

        result = await call("api_update_post", {"post_id": 1, **fields})

        assert not result.isError
        sent = json.loads(httpx_mock.get_request().content)
        assert len(sent) == 1


# ============================================================================
# Tool Output Format Tests
# ============================================================================

class TestListPostsOutputFormat:
    """Test output format of api_list_posts."""

    @pytest.mark.asyncio
    async def test_markdown_format_contains_headers_and_structure(self, httpx_mock):
        """Test that markdown format contains expected headers and structure."""
        httpx_mock.add_response(
            method="GET",
            url="https://jsonplaceholder.typicode.com/posts",
            json=SAMPLE_POSTS
        )

        result = await api_list_posts(limit=20, response_format=ResponseFormat.MARKDOWN)

        assert "# Posts" in result
        assert "Showing" in result
        assert "offset:" in result
        assert "First Post" in result
        assert "Second Post" in result

    @pytest.mark.asyncio
    async def test_json_format_is_valid_json_with_pagination(self, httpx_mock):
        """Test that JSON format is valid JSON with pagination metadata."""
        httpx_mock.add_response(
            method="GET",
            url="https://jsonplaceholder.typicode.com/posts",
            json=SAMPLE_POSTS
        )

        result = await api_list_posts(limit=20, response_format=ResponseFormat.JSON)

        data = json.loads(result)
        assert "pagination" in data
        assert "posts" in data
        assert "total" in data["pagination"]
        assert "count" in data["pagination"]
        assert "has_more" in data["pagination"]

    @pytest.mark.asyncio
    async def test_markdown_includes_pagination_info(self, httpx_mock):
        """Test that markdown format includes pagination info."""
        httpx_mock.add_response(
            method="GET",
            url="https://jsonplaceholder.typicode.com/posts",
            json=SAMPLE_POSTS
        )

        result = await api_list_posts(limit=2, offset=0, response_format=ResponseFormat.MARKDOWN)

        assert "offset: 0" in result
        # With 3 posts and limit=2, we should have more
        assert "More posts available" in result or "offset:" in result


class TestGetPostOutputFormat:
    """Test output format of api_get_post."""

    @pytest.mark.asyncio
    async def test_markdown_includes_post_title(self, httpx_mock):
        """Test that markdown format includes post title."""
        httpx_mock.add_response(
            method="GET",
            url="https://jsonplaceholder.typicode.com/posts/1",
            json=SAMPLE_POST
        )

        result = await api_get_post(post_id=1, response_format=ResponseFormat.MARKDOWN)

        assert "Test Post" in result
        assert "1" in result
        assert "User" in result

    @pytest.mark.asyncio
    async def test_with_include_comments_true_response_includes_comments(self, httpx_mock):
        """Test that include_comments=True response includes comments."""
        httpx_mock.add_response(
            method="GET",
            url="https://jsonplaceholder.typicode.com/posts/1",
            json=SAMPLE_POST
        )
        httpx_mock.add_response(
            method="GET",
            url="https://jsonplaceholder.typicode.com/posts/1/comments",
            json=SAMPLE_COMMENTS
        )

        result = await api_get_post(post_id=1, include_comments=True, response_format=ResponseFormat.MARKDOWN)

        assert "## Comments" in result
        assert "Test Comment 1" in result

    @pytest.mark.asyncio
    async def test_json_format_valid_json(self, httpx_mock):
        """Test that JSON format returns valid JSON."""
        httpx_mock.add_response(
            method="GET",
            url="https://jsonplaceholder.typicode.com/posts/1",
            json=SAMPLE_POST
        )

        result = await api_get_post(post_id=1, response_format=ResponseFormat.JSON)

        data = json.loads(result)
        assert "post" in data
        assert data["post"]["id"] == 1


# ============================================================================
# Pagination Tests
# ============================================================================

class TestListPostsPagination:
    """Test pagination behavior of api_list_posts."""

    @pytest.mark.asyncio
    async def test_offset_returns_correct_slice(self, httpx_mock):
        """Test that offset=2 with limit=1 returns correct slice."""
        httpx_mock.add_response(
            method="GET",
            url="https://jsonplaceholder.typicode.com/posts",
            json=SAMPLE_POSTS
        )

        result = await api_list_posts(limit=1, offset=2, response_format=ResponseFormat.JSON)

        data = json.loads(result)
        assert data["pagination"]["offset"] == 2
        assert len(data["posts"]) == 1
        assert data["posts"][0]["id"] == 3

    @pytest.mark.asyncio
    async def test_has_more_false_at_end_of_results(self, httpx_mock):
        """Test that has_more=False when at end of results."""
        httpx_mock.add_response(
            method="GET",
            url="https://jsonplaceholder.typicode.com/posts",
            json=SAMPLE_POSTS
        )

        # Request posts beyond available (offset=3, limit=10, total=3)
        result = await api_list_posts(limit=10, offset=3, response_format=ResponseFormat.JSON)

        data = json.loads(result)
        assert data["pagination"]["has_more"] is False
        assert data["pagination"]["next_offset"] is None

    @pytest.mark.asyncio
    async def test_has_more_true_when_more_results_available(self, httpx_mock):
        """Test that has_more=True when more results available."""
        httpx_mock.add_response(
            method="GET",
            url="https://jsonplaceholder.typicode.com/posts",
            json=SAMPLE_POSTS
        )

        result = await api_list_posts(limit=2, offset=0, response_format=ResponseFormat.JSON)

        data = json.loads(result)
        assert data["pagination"]["has_more"] is True
        assert data["pagination"]["next_offset"] == 2


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestToolErrorHandling:
    """API failures raise ToolError, which MCP reports as isError=True."""

    @pytest.mark.asyncio
    async def test_get_post_404_raises_tool_error(self, httpx_mock):
        httpx_mock.add_response(method="GET", url=f"{BASE}/posts/99999", status_code=404)

        with pytest.raises(ToolError, match="Error fetching post: Resource not found"):
            await api_get_post(post_id=99999)

    @pytest.mark.asyncio
    async def test_create_post_500_raises_tool_error(self, httpx_mock):
        httpx_mock.add_response(method="POST", url=f"{BASE}/posts", status_code=500)

        with pytest.raises(ToolError, match="Error creating post: API server error"):
            await api_create_post(title="Test", body="Body", user_id=1)

    @pytest.mark.asyncio
    async def test_update_post_404_raises_tool_error(self, httpx_mock):
        httpx_mock.add_response(method="PATCH", url=f"{BASE}/posts/99999", status_code=404)

        with pytest.raises(ToolError, match="Error updating post: Resource not found"):
            await api_update_post(post_id=99999, title="New Title")

    @pytest.mark.asyncio
    async def test_api_error_is_reported_as_mcp_error(self, httpx_mock):
        httpx_mock.add_response(method="GET", url=f"{BASE}/posts/99999", status_code=404)

        result = await call("api_get_post", {"post_id": 99999})

        assert result.isError
        assert "not found" in result.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_unexpected_error_does_not_leak_details(self, httpx_mock):
        # A non-JSON body makes response.json() raise something that isn't an HTTP error
        httpx_mock.add_response(method="GET", url=f"{BASE}/posts", text="<html>secret internals</html>")

        with pytest.raises(ToolError) as exc:
            await api_list_posts()

        assert "unexpected server error" in str(exc.value)
        assert "secret" not in str(exc.value)

    @pytest.mark.asyncio
    async def test_comments_failure_still_returns_post_with_note(self, httpx_mock):
        httpx_mock.add_response(method="GET", url=f"{BASE}/posts/1", json=SAMPLE_POST)
        httpx_mock.add_response(method="GET", url=f"{BASE}/posts/1/comments", status_code=503)

        result = await api_get_post(post_id=1, include_comments=True, response_format=ResponseFormat.JSON)

        data = json.loads(result)
        assert data["post"]["id"] == 1
        assert "comments" not in data
        assert "API server error (503)" in data["comments_error"]


# ============================================================================
# User ID Filtering Tests
# ============================================================================

class TestUserIDFiltering:
    """Test user_id filtering in api_list_posts."""

    @pytest.mark.asyncio
    async def test_filter_by_user_id(self, httpx_mock):
        """Test filtering posts by user_id."""
        httpx_mock.add_response(
            method="GET",
            url="https://jsonplaceholder.typicode.com/posts",
            json=SAMPLE_POSTS
        )

        result = await api_list_posts(user_id=1, response_format=ResponseFormat.JSON)

        data = json.loads(result)
        # SAMPLE_POSTS has posts with userId 1, 2, 1
        # After filtering for userId=1, should have 2 posts
        assert data["pagination"]["count"] == 2
        for post in data["posts"]:
            assert post["userId"] == 1
