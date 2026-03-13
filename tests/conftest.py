"""Shared test fixtures and mock data for api_bridge_mcp tests."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
import httpx
from api_bridge_mcp.api_client import APIClient


# ============================================================================
# Sample Data Constants
# ============================================================================

SAMPLE_POST = {
    "userId": 1,
    "id": 1,
    "title": "Test Post",
    "body": "This is a test post body with some content."
}

SAMPLE_POSTS = [
    {
        "userId": 1,
        "id": 1,
        "title": "First Post",
        "body": "This is the first post body with some content."
    },
    {
        "userId": 2,
        "id": 2,
        "title": "Second Post",
        "body": "This is the second post body with different content."
    },
    {
        "userId": 1,
        "id": 3,
        "title": "Third Post",
        "body": "This is the third post body with more content."
    }
]

SAMPLE_COMMENTS = [
    {
        "postId": 1,
        "id": 1,
        "name": "Test Comment 1",
        "email": "user1@example.com",
        "body": "This is the first comment on the post."
    },
    {
        "postId": 1,
        "id": 2,
        "name": "Test Comment 2",
        "email": "user2@example.com",
        "body": "This is the second comment on the post."
    }
]


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_post():
    """Return a sample post dict."""
    return SAMPLE_POST.copy()


@pytest.fixture
def sample_posts():
    """Return a list of sample posts."""
    return [post.copy() for post in SAMPLE_POSTS]


@pytest.fixture
def sample_comments():
    """Return a list of sample comments."""
    return [comment.copy() for comment in SAMPLE_COMMENTS]


@pytest_asyncio.fixture
async def mock_api_client(httpx_mock):
    """Provide a configured mock APIClient.

    Uses pytest-httpx to mock HTTP responses.
    Default mocks: GET /posts returns SAMPLE_POSTS
    """
    # Default mock for listing all posts
    httpx_mock.add_response(
        method="GET",
        url="https://jsonplaceholder.typicode.com/posts",
        json=SAMPLE_POSTS
    )

    # Mock for single post
    httpx_mock.add_response(
        method="GET",
        url="https://jsonplaceholder.typicode.com/posts/1",
        json=SAMPLE_POST
    )

    # Mock for non-existent post (404)
    httpx_mock.add_response(
        method="GET",
        url="https://jsonplaceholder.typicode.com/posts/99999",
        status_code=404
    )

    # Mock for comments on post 1
    httpx_mock.add_response(
        method="GET",
        url="https://jsonplaceholder.typicode.com/posts/1/comments",
        json=SAMPLE_COMMENTS
    )

    # Mock for POST create
    httpx_mock.add_response(
        method="POST",
        url="https://jsonplaceholder.typicode.com/posts",
        json={
            "userId": 1,
            "title": "New Post",
            "body": "New post body",
            "id": 101
        },
        status_code=201
    )

    # Mock for PUT update
    httpx_mock.add_response(
        method="PUT",
        url="https://jsonplaceholder.typicode.com/posts/1",
        json={
            "userId": 1,
            "id": 1,
            "title": "Updated Post",
            "body": "Updated post body"
        }
    )

    # Create and return client
    client = APIClient(base_url="https://jsonplaceholder.typicode.com")
    return client
