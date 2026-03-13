"""FastMCP server that wraps JSONPlaceholder API as MCP tools.

This module demonstrates the "REST API → MCP server" pattern:
- Centralized API client (api_client.py) handles all HTTP concerns
- Pydantic models validate inputs
- Tools expose clean, typed interfaces to Claude and other AI assistants
- Error handling maps API errors to actionable messages
"""

import json

import httpx
from enum import Enum
from typing import Annotated, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from mcp.server.fastmcp import FastMCP

from .api_client import APIClient, handle_api_error


# Initialize FastMCP server
mcp = FastMCP("api_bridge_mcp")


# ============================================================================
# Shared Models
# ============================================================================

class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


# ============================================================================
# Tool 1: api_list_posts
# ============================================================================

class ListPostsInput(BaseModel):
    """Input model for api_list_posts tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )

    user_id: Optional[int] = Field(
        None,
        description="Filter posts by user ID (author). If omitted, returns posts from all users."
    )
    limit: int = Field(
        20,
        ge=1,
        le=100,
        description="Number of posts to return. Default 20, max 100."
    )
    offset: int = Field(
        0,
        ge=0,
        description="Number of posts to skip. Default 0. Used for pagination."
    )
    response_format: ResponseFormat = Field(
        ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable summaries, 'json' for full objects."
    )

    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v):
        if v is not None and v < 1:
            raise ValueError("user_id must be >= 1")
        return v


@mcp.tool(
    name="api_list_posts",
    description="List posts from JSONPlaceholder with pagination and optional filtering.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def api_list_posts(
    user_id: Annotated[Optional[int], Field(None, description="Filter posts by user ID (author). If omitted, returns posts from all users.", ge=1)] = None,
    limit: Annotated[int, Field(description="Number of posts to return. Default 20, max 100.", ge=1, le=100)] = 20,
    offset: Annotated[int, Field(description="Number of posts to skip. Default 0. Used for pagination.", ge=0)] = 0,
    response_format: Annotated[ResponseFormat, Field(description="Output format: 'markdown' for human-readable summaries, 'json' for full objects.")] = ResponseFormat.MARKDOWN
) -> str:
    """Fetch and list posts with optional filtering by author and pagination.

    Args:
        user_id: Filter posts by user ID. If omitted, all posts shown.
        limit: Number of posts per page (1-100, default 20).
        offset: Number of posts to skip (default 0).
        response_format: 'markdown' for summaries, 'json' for full objects.

    Returns:
        Formatted list of posts with pagination metadata.

    Examples:
        List first 20 posts as markdown:
        >>> await api_list_posts()

        List 50 posts from user 2 as JSON:
        >>> await api_list_posts(user_id=2, limit=50, response_format=ResponseFormat.JSON)

        Get posts 20-40 (pagination):
        >>> await api_list_posts(limit=20, offset=20)

    Error Handling:
        - Invalid user_id: Returns validation error
        - Limit out of range: Returns validation error
        - Network error: Returns actionable error message
    """
    try:
        async with APIClient() as client:
            # Fetch all posts (JSONPlaceholder doesn't support server-side pagination)
            all_posts = await client.get("/posts")

            # Apply user_id filter if provided
            if user_id is not None:
                all_posts = [p for p in all_posts if p.get("userId") == user_id]

            # Calculate pagination
            total = len(all_posts)
            posts_page = all_posts[offset : offset + limit]
            has_more = (offset + limit) < total
            next_offset = offset + limit if has_more else None

            if response_format == ResponseFormat.JSON:
                return _format_list_posts_json(posts_page, {
                    "total": total,
                    "count": len(posts_page),
                    "offset": offset,
                    "has_more": has_more,
                    "next_offset": next_offset
                })
            else:  # markdown
                return _format_list_posts_markdown(posts_page, {
                    "total": total,
                    "count": len(posts_page),
                    "offset": offset,
                    "has_more": has_more,
                    "next_offset": next_offset
                })

    except httpx.HTTPError as e:
        return f"Error fetching posts: {handle_api_error(e)}"
    except Exception as e:
        return f"Error: {handle_api_error(e)}"


def _format_list_posts_markdown(posts: list, pagination: dict) -> str:
    """Format posts as markdown for human readability."""
    lines = []
    lines.append("# Posts")
    lines.append(f"Showing {pagination['count']} of {pagination['total']} posts (offset: {pagination['offset']})")
    lines.append("")

    for i, post in enumerate(posts, start=pagination['offset'] + 1):
        title = post.get("title", "Untitled")
        body = post.get("body", "")
        # Truncate body to first 80 characters
        body_preview = body[:80] + "..." if len(body) > 80 else body
        post_id = post.get("id")
        user_id = post.get("userId")
        lines.append(f"{i}. **{title}** (ID: {post_id}, User: {user_id})")
        lines.append(f"   {body_preview}")
        lines.append("")

    if pagination['has_more']:
        lines.append(f"**More posts available.** Set `offset: {pagination['next_offset']}` to see next page.")
    else:
        lines.append("**End of results.**")

    return "\n".join(lines)


def _format_list_posts_json(posts: list, pagination: dict) -> str:
    """Format posts as JSON with pagination metadata."""
    return json.dumps({
        "pagination": pagination,
        "posts": posts
    }, indent=2)


# ============================================================================
# Tool 2: api_get_post
# ============================================================================

class GetPostInput(BaseModel):
    """Input model for api_get_post tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )

    post_id: int = Field(
        ...,
        ge=1,
        description="ID of the post to fetch. Must be >= 1."
    )
    include_comments: bool = Field(
        False,
        description="If true, also fetch comments on this post."
    )
    response_format: ResponseFormat = Field(
        ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for formatted display, 'json' for raw objects."
    )


@mcp.tool(
    name="api_get_post",
    description="Fetch a single post by ID with optional comments.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def api_get_post(
    post_id: Annotated[int, Field(description="ID of the post to fetch. Must be >= 1.", ge=1)],
    include_comments: Annotated[bool, Field(description="If true, also fetch comments on this post.")] = False,
    response_format: Annotated[ResponseFormat, Field(description="Output format: 'markdown' for formatted display, 'json' for raw objects.")] = ResponseFormat.MARKDOWN
) -> str:
    """Fetch a single post by ID and optionally its comments.

    Demonstrates the pattern of fetching a resource and joining related data.

    Args:
        post_id: ID of the post (>= 1).
        include_comments: If true, also fetch and include comments.
        response_format: 'markdown' for formatted display, 'json' for objects.

    Returns:
        Post details and optionally comments.

    Examples:
        Fetch post 1 as markdown:
        >>> await api_get_post(post_id=1)

        Fetch post 5 with comments as JSON:
        >>> await api_get_post(post_id=5, include_comments=True, response_format=ResponseFormat.JSON)

    Error Handling:
        - Post not found (404): Returns "Resource not found" message
        - Invalid post_id: Returns validation error
        - Network error: Returns actionable error message
    """
    try:
        async with APIClient() as client:
            # Fetch the post
            post = await client.get(f"/posts/{post_id}")

            # Optionally fetch comments
            comments = []
            if include_comments:
                try:
                    comments = await client.get(f"/posts/{post_id}/comments")
                except httpx.HTTPStatusError:
                    # If comments endpoint fails, continue without them
                    comments = []

            if response_format == ResponseFormat.JSON:
                return _format_get_post_json(post, comments)
            else:  # markdown
                return _format_get_post_markdown(post, comments)

    except httpx.HTTPStatusError as e:
        return f"Error fetching post: {handle_api_error(e)}"
    except httpx.HTTPError as e:
        return f"Error fetching post: {handle_api_error(e)}"
    except Exception as e:
        return f"Error: {handle_api_error(e)}"


def _format_get_post_markdown(post: dict, comments: list) -> str:
    """Format post as markdown."""
    lines = []
    lines.append(f"# {post.get('title', 'Untitled')}")
    lines.append(f"**ID:** {post.get('id')} | **Author:** User {post.get('userId')}")
    lines.append("")
    lines.append(post.get('body', ''))
    lines.append("")

    if comments:
        lines.append("## Comments")
        for i, comment in enumerate(comments, 1):
            name = comment.get('name', 'Anonymous')
            email = comment.get('email', '')
            body = comment.get('body', '')
            lines.append(f"{i}. **{name}** ({email})")
            lines.append(f"   {body}")
            lines.append("")

    return "\n".join(lines)


def _format_get_post_json(post: dict, comments: list) -> str:
    """Format post as JSON."""
    data = {
        "post": post,
    }
    if comments:
        data["comments"] = comments
    return json.dumps(data, indent=2)


# ============================================================================
# Tool 3: api_create_post
# ============================================================================

class CreatePostInput(BaseModel):
    """Input model for api_create_post tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Post title (1-200 characters)."
    )
    body: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Post body content (1-5000 characters)."
    )
    user_id: int = Field(
        ...,
        ge=1,
        description="ID of the user creating the post. Must be >= 1."
    )

    @field_validator('title', 'body')
    @classmethod
    def validate_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Cannot be empty or whitespace only")
        return v


@mcp.tool(
    name="api_create_post",
    description="Create a new post.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def api_create_post(
    title: Annotated[str, Field(description="Post title (1-200 characters).", min_length=1, max_length=200)],
    body: Annotated[str, Field(description="Post body content (1-5000 characters).", min_length=1, max_length=5000)],
    user_id: Annotated[int, Field(description="ID of the user creating the post. Must be >= 1.", ge=1)]
) -> str:
    """Create a new post on JSONPlaceholder.

    Demonstrates write operations and input validation.

    Args:
        title: Post title (1-200 characters).
        body: Post body (1-5000 characters).
        user_id: Author user ID (>= 1).

    Returns:
        The created post with its ID.

    Examples:
        Create a simple post:
        >>> await api_create_post(
        ...     title="My First Post",
        ...     body="This is the content of my post.",
        ...     user_id=1
        ... )

        Create a longer post:
        >>> await api_create_post(
        ...     title="In-Depth Guide",
        ...     body="A detailed explanation about...",
        ...     user_id=5
        ... )

    Error Handling:
        - Title too long (>200 chars): Returns validation error
        - Body too long (>5000 chars): Returns validation error
        - user_id < 1: Returns validation error
        - Network error: Returns actionable error message
    """
    try:
        async with APIClient() as client:
            payload = {
                "title": title,
                "body": body,
                "userId": user_id
            }
            result = await client.post("/posts", json=payload)

            return json.dumps({
                "success": True,
                "message": f"Post created with ID {result.get('id')}",
                "post": result
            }, indent=2)

    except httpx.HTTPError as e:
        return f"Error creating post: {handle_api_error(e)}"
    except Exception as e:
        return f"Error: {handle_api_error(e)}"


# ============================================================================
# Tool 4: api_update_post
# ============================================================================

class UpdatePostInput(BaseModel):
    """Input model for api_update_post tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )

    post_id: int = Field(
        ...,
        ge=1,
        description="ID of the post to update. Must be >= 1."
    )
    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="New title (1-200 characters). Omit to keep current."
    )
    body: Optional[str] = Field(
        None,
        min_length=1,
        max_length=5000,
        description="New body (1-5000 characters). Omit to keep current."
    )
    user_id: Optional[int] = Field(
        None,
        ge=1,
        description="New user ID. Omit to keep current."
    )

    @field_validator('title', 'body')
    @classmethod
    def validate_not_empty_if_present(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Cannot be empty or whitespace only")
        return v

    @model_validator(mode='after')
    def check_at_least_one_field(self):
        """Ensure at least one of title/body/user_id is provided."""
        if self.title is None and self.body is None and self.user_id is None:
            raise ValueError("At least one of title, body, or user_id must be provided")
        return self


@mcp.tool(
    name="api_update_post",
    description="Update a post (partial update with PATCH).",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def api_update_post(
    post_id: Annotated[int, Field(description="ID of the post to update. Must be >= 1.", ge=1)],
    title: Annotated[Optional[str], Field(description="New title (1-200 characters). Omit to keep current.", min_length=1, max_length=200)] = None,
    body: Annotated[Optional[str], Field(description="New body (1-5000 characters). Omit to keep current.", min_length=1, max_length=5000)] = None,
    user_id: Annotated[Optional[int], Field(description="New user ID. Omit to keep current.", ge=1)] = None
) -> str:
    """Update a post with partial fields.

    Demonstrates partial update pattern where only provided fields are changed.

    Args:
        post_id: ID of post to update (>= 1).
        title: New title (1-200 chars). Omit to keep current.
        body: New body (1-5000 chars). Omit to keep current.
        user_id: New author user ID (>= 1). Omit to keep current.

    Returns:
        The updated post.

    Examples:
        Update only the title:
        >>> await api_update_post(post_id=1, title="New Title")

        Update title and body:
        >>> await api_update_post(
        ...     post_id=5,
        ...     title="Updated",
        ...     body="New content here"
        ... )

        Change the author:
        >>> await api_update_post(post_id=10, user_id=3)

    Error Handling:
        - post_id < 1: Returns validation error
        - No fields provided: Returns validation error
        - Post not found (404): Returns "Resource not found" message
        - Network error: Returns actionable error message
    """
    # Validate that at least one field is provided
    if title is None and body is None and user_id is None:
        return "Error: At least one of title, body, or user_id must be provided."

    try:
        async with APIClient() as client:
            # Build payload with only provided fields
            payload = {}
            if title is not None:
                payload["title"] = title
            if body is not None:
                payload["body"] = body
            if user_id is not None:
                payload["userId"] = user_id

            result = await client.patch(f"/posts/{post_id}", json=payload)

            return json.dumps({
                "success": True,
                "message": f"Post {post_id} updated successfully",
                "post": result
            }, indent=2)

    except httpx.HTTPStatusError as e:
        return f"Error updating post: {handle_api_error(e)}"
    except httpx.HTTPError as e:
        return f"Error updating post: {handle_api_error(e)}"
    except Exception as e:
        return f"Error: {handle_api_error(e)}"


# ============================================================================
# Entry Point
# ============================================================================

def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
