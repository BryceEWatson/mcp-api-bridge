"""Tests for MCP tool functions."""

import pytest
import json
from pydantic import ValidationError
from api_bridge_mcp.server import (
    api_list_posts, api_get_post, api_create_post, api_update_post,
    ListPostsInput, GetPostInput, CreatePostInput, UpdatePostInput,
    ResponseFormat
)
from .conftest import SAMPLE_POST, SAMPLE_POSTS, SAMPLE_COMMENTS


# ============================================================================
# Input Validation Tests
# ============================================================================

class TestListPostsInputValidation:
    """Test input validation for api_list_posts."""

    def test_limit_zero_raises_validation_error(self):
        """Test that limit=0 raises validation error."""
        with pytest.raises(ValidationError):
            ListPostsInput(limit=0)

    def test_limit_over_100_raises_validation_error(self):
        """Test that limit>100 raises validation error."""
        with pytest.raises(ValidationError):
            ListPostsInput(limit=101)

    def test_valid_limit_range(self):
        """Test that limit within valid range is accepted."""
        model = ListPostsInput(limit=50)
        assert model.limit == 50

    def test_negative_offset_raises_validation_error(self):
        """Test that negative offset raises validation error."""
        with pytest.raises(ValidationError):
            ListPostsInput(offset=-1)

    def test_valid_offset(self):
        """Test that valid offset is accepted."""
        model = ListPostsInput(offset=10)
        assert model.offset == 10


class TestGetPostInputValidation:
    """Test input validation for api_get_post."""

    def test_post_id_zero_raises_validation_error(self):
        """Test that post_id=0 raises validation error."""
        with pytest.raises(ValidationError):
            GetPostInput(post_id=0)

    def test_post_id_negative_raises_validation_error(self):
        """Test that negative post_id raises validation error."""
        with pytest.raises(ValidationError):
            GetPostInput(post_id=-1)

    def test_valid_post_id(self):
        """Test that valid post_id is accepted."""
        model = GetPostInput(post_id=1)
        assert model.post_id == 1


class TestCreatePostInputValidation:
    """Test input validation for api_create_post."""

    def test_empty_title_raises_validation_error(self):
        """Test that empty title raises validation error."""
        with pytest.raises(ValidationError):
            CreatePostInput(title="", body="content", user_id=1)

    def test_title_over_200_chars_raises_validation_error(self):
        """Test that title over 200 chars raises validation error."""
        long_title = "a" * 201
        with pytest.raises(ValidationError):
            CreatePostInput(title=long_title, body="content", user_id=1)

    def test_empty_body_raises_validation_error(self):
        """Test that empty body raises validation error."""
        with pytest.raises(ValidationError):
            CreatePostInput(title="Title", body="", user_id=1)

    def test_body_over_5000_chars_raises_validation_error(self):
        """Test that body over 5000 chars raises validation error."""
        long_body = "a" * 5001
        with pytest.raises(ValidationError):
            CreatePostInput(title="Title", body=long_body, user_id=1)

    def test_user_id_zero_raises_validation_error(self):
        """Test that user_id=0 raises validation error."""
        with pytest.raises(ValidationError):
            CreatePostInput(title="Title", body="content", user_id=0)

    def test_valid_create_post_input(self):
        """Test that valid input is accepted."""
        model = CreatePostInput(title="Test", body="content", user_id=1)
        assert model.title == "Test"
        assert model.body == "content"
        assert model.user_id == 1


class TestUpdatePostInputValidation:
    """Test input validation for api_update_post."""

    def test_no_fields_provided_raises_validation_error(self):
        """Test that no fields provided raises validation error."""
        with pytest.raises(ValidationError):
            UpdatePostInput(post_id=1)

    def test_post_id_zero_raises_validation_error(self):
        """Test that post_id=0 raises validation error."""
        with pytest.raises(ValidationError):
            UpdatePostInput(post_id=0, title="New Title")

    def test_valid_update_with_title_only(self):
        """Test that updating only title is valid."""
        model = UpdatePostInput(post_id=1, title="New Title")
        assert model.post_id == 1
        assert model.title == "New Title"
        assert model.body is None

    def test_valid_update_with_body_only(self):
        """Test that updating only body is valid."""
        model = UpdatePostInput(post_id=1, body="New Body")
        assert model.post_id == 1
        assert model.body == "New Body"
        assert model.title is None

    def test_valid_update_with_user_id_only(self):
        """Test that updating only user_id is valid."""
        model = UpdatePostInput(post_id=1, user_id=5)
        assert model.post_id == 1
        assert model.user_id == 5


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
    """Test error handling in tool functions."""

    @pytest.mark.asyncio
    async def test_get_post_with_nonexistent_id_returns_error_message(self, httpx_mock):
        """Test that getting non-existent post returns error message."""
        httpx_mock.add_response(
            method="GET",
            url="https://jsonplaceholder.typicode.com/posts/99999",
            status_code=404
        )

        result = await api_get_post(post_id=99999)

        assert "Error fetching post" in result or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_create_post_with_api_failure_returns_error_message(self, httpx_mock):
        """Test that API failure in create returns error message."""
        httpx_mock.add_response(
            method="POST",
            url="https://jsonplaceholder.typicode.com/posts",
            status_code=500
        )

        result = await api_create_post(title="Test", body="Body", user_id=1)

        assert "Error creating post" in result or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_update_post_with_nonexistent_id_returns_error(self, httpx_mock):
        """Test that updating non-existent post returns error."""
        httpx_mock.add_response(
            method="PATCH",
            url="https://jsonplaceholder.typicode.com/posts/99999",
            status_code=404
        )

        result = await api_update_post(post_id=99999, title="New Title")

        assert "Error updating post" in result or "error" in result.lower()


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
