"""End-to-end MCP protocol tests.

These tests connect to the server using the same MCP protocol that Claude Desktop
uses. No HTTP mocking — every tool call hits the live JSONPlaceholder API.

Two transport modes are tested:
  1. In-memory: Fast, uses the SDK's built-in memory transport. Tests the full
     MCP message flow (initialize → list_tools → call_tool) without spawning
     a subprocess.
  2. Stdio: Spawns the server as a child process and communicates over
     stdin/stdout JSON-RPC, exactly like Claude Desktop does.
"""

import json
import sys

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.memory import create_connected_server_and_client_session

from api_bridge_mcp.server import mcp as server_instance


# ============================================================================
# In-Memory Transport Tests (full MCP protocol, no subprocess)
# ============================================================================


class TestMCPInitialization:
    """Verify the server advertises itself correctly over MCP."""

    @pytest.mark.asyncio
    async def test_server_initializes_and_reports_capabilities(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            caps = session.get_server_capabilities()
            assert caps is not None
            assert caps.tools is not None, "Server must advertise tool capabilities"

    @pytest.mark.asyncio
    async def test_server_lists_exactly_four_tools(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.list_tools()
            tool_names = sorted([t.name for t in result.tools])
            assert tool_names == [
                "api_create_post",
                "api_get_post",
                "api_list_posts",
                "api_update_post",
            ]


class TestToolSchemas:
    """Verify that Annotated[type, Field(...)] constraints appear in the
    JSON schemas that get advertised to Claude."""

    @pytest.mark.asyncio
    async def test_list_posts_schema_has_constraints(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.list_tools()
            tool = next(t for t in result.tools if t.name == "api_list_posts")
            props = tool.inputSchema["properties"]

            # limit: ge=1, le=100
            assert props["limit"]["minimum"] == 1, "limit must have minimum=1"
            assert props["limit"]["maximum"] == 100, "limit must have maximum=100"

            # offset: ge=0
            assert props["offset"]["minimum"] == 0, "offset must have minimum=0"

            # user_id: ge=1
            # user_id may be in a oneOf/anyOf for Optional, so check the nested schema
            user_id_schema = props["user_id"]
            # Optional[int] with Field(ge=1) can produce different schema shapes
            # depending on Pydantic version. Check that ge=1 is present somewhere.
            user_id_str = json.dumps(user_id_schema)
            assert '"minimum": 1' in user_id_str or '"minimum":1' in user_id_str, (
                f"user_id must have minimum=1, got: {user_id_schema}"
            )

    @pytest.mark.asyncio
    async def test_create_post_schema_has_string_constraints(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.list_tools()
            tool = next(t for t in result.tools if t.name == "api_create_post")
            props = tool.inputSchema["properties"]

            # title: min_length=1, max_length=200
            assert props["title"]["minLength"] == 1
            assert props["title"]["maxLength"] == 200

            # body: min_length=1, max_length=5000
            assert props["body"]["minLength"] == 1
            assert props["body"]["maxLength"] == 5000

    @pytest.mark.asyncio
    async def test_get_post_schema_has_post_id_constraint(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.list_tools()
            tool = next(t for t in result.tools if t.name == "api_get_post")
            props = tool.inputSchema["properties"]

            assert props["post_id"]["minimum"] == 1, "post_id must have minimum=1"

    @pytest.mark.asyncio
    async def test_schemas_include_descriptions(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.list_tools()
            for tool in result.tools:
                assert tool.description, f"{tool.name} must have a tool description"
                for prop_name, prop_schema in tool.inputSchema["properties"].items():
                    # Description might be in the top-level or inside anyOf/oneOf
                    prop_str = json.dumps(prop_schema)
                    assert "description" in prop_str, (
                        f"{tool.name}.{prop_name} must have a description in its schema"
                    )


class TestToolAnnotations:
    """Verify MCP tool annotations (readOnlyHint, destructiveHint, etc.)."""

    @pytest.mark.asyncio
    async def test_list_posts_annotations(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.list_tools()
            tool = next(t for t in result.tools if t.name == "api_list_posts")
            assert tool.annotations is not None, "api_list_posts must have annotations"
            assert tool.annotations.readOnlyHint is True
            assert tool.annotations.destructiveHint is False
            assert tool.annotations.idempotentHint is True
            assert tool.annotations.openWorldHint is True

    @pytest.mark.asyncio
    async def test_get_post_annotations(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.list_tools()
            tool = next(t for t in result.tools if t.name == "api_get_post")
            assert tool.annotations is not None
            assert tool.annotations.readOnlyHint is True
            assert tool.annotations.destructiveHint is False

    @pytest.mark.asyncio
    async def test_create_post_is_not_readonly(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.list_tools()
            tool = next(t for t in result.tools if t.name == "api_create_post")
            assert tool.annotations is not None
            assert tool.annotations.readOnlyHint is False

    @pytest.mark.asyncio
    async def test_update_post_is_not_readonly(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.list_tools()
            tool = next(t for t in result.tools if t.name == "api_update_post")
            assert tool.annotations is not None
            assert tool.annotations.readOnlyHint is False


class TestLiveToolCalls:
    """Call each tool over MCP against the live JSONPlaceholder API.
    No mocks — real HTTP requests."""

    @pytest.mark.asyncio
    async def test_list_posts_returns_markdown(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_list_posts",
                {"user_id": 1, "limit": 3, "response_format": "markdown"},
            )
            assert not result.isError, f"Expected success, got: {result.content}"
            text = result.content[0].text
            assert "# Posts" in text
            assert "Showing 3 of" in text

    @pytest.mark.asyncio
    async def test_list_posts_returns_json(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_list_posts",
                {"user_id": 1, "limit": 2, "response_format": "json"},
            )
            assert not result.isError
            data = json.loads(result.content[0].text)
            assert "posts" in data
            assert len(data["posts"]) == 2
            assert "pagination" in data

    @pytest.mark.asyncio
    async def test_list_posts_pagination(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_list_posts",
                {"user_id": 1, "limit": 2, "offset": 0, "response_format": "json"},
            )
            assert not result.isError
            data = json.loads(result.content[0].text)
            assert data["pagination"]["has_more"] is True

    @pytest.mark.asyncio
    async def test_get_post_markdown(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_get_post",
                {"post_id": 1, "response_format": "markdown"},
            )
            assert not result.isError
            text = result.content[0].text
            # Post 1 on JSONPlaceholder always has this title
            assert "sunt aut facere repellat" in text
            assert "User 1" in text

    @pytest.mark.asyncio
    async def test_get_post_with_comments(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_get_post",
                {"post_id": 1, "include_comments": True, "response_format": "markdown"},
            )
            assert not result.isError
            text = result.content[0].text
            assert "## Comments" in text
            # Post 1 has 5 comments on JSONPlaceholder
            assert "Eliseo@gardner.biz" in text

    @pytest.mark.asyncio
    async def test_get_post_json(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_get_post",
                {"post_id": 1, "response_format": "json"},
            )
            assert not result.isError
            data = json.loads(result.content[0].text)
            assert data["post"]["id"] == 1
            assert data["post"]["userId"] == 1

    @pytest.mark.asyncio
    async def test_create_post(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_create_post",
                {
                    "title": "E2E Test Post",
                    "body": "Created via MCP protocol test.",
                    "user_id": 1,
                },
            )
            assert not result.isError
            data = json.loads(result.content[0].text)
            assert data["success"] is True
            assert data["post"]["title"] == "E2E Test Post"
            assert data["post"]["id"] == 101  # JSONPlaceholder always returns 101

    @pytest.mark.asyncio
    async def test_update_post_uses_patch(self):
        """Verify the update tool sends PATCH (not PUT)."""
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_update_post",
                {"post_id": 1, "title": "Patched Title"},
            )
            assert not result.isError
            data = json.loads(result.content[0].text)
            assert data["success"] is True
            assert data["post"]["title"] == "Patched Title"
            # The original body should be preserved (PATCH, not PUT)
            assert data["post"]["body"], "Body should not be empty after PATCH"


class TestInputValidation:
    """Verify that invalid inputs are rejected through the MCP protocol layer.
    These test that Pydantic constraints in Annotated[type, Field(...)]
    actually fire when called via MCP, not just as direct Python calls."""

    @pytest.mark.asyncio
    async def test_list_posts_rejects_limit_zero(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_list_posts",
                {"limit": 0},
            )
            assert result.isError, "limit=0 should be rejected (minimum is 1)"

    @pytest.mark.asyncio
    async def test_list_posts_rejects_limit_over_100(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_list_posts",
                {"limit": 500},
            )
            assert result.isError, "limit=500 should be rejected (maximum is 100)"

    @pytest.mark.asyncio
    async def test_list_posts_rejects_negative_offset(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_list_posts",
                {"offset": -1},
            )
            assert result.isError, "offset=-1 should be rejected (minimum is 0)"

    @pytest.mark.asyncio
    async def test_get_post_rejects_post_id_zero(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_get_post",
                {"post_id": 0},
            )
            assert result.isError, "post_id=0 should be rejected (minimum is 1)"

    @pytest.mark.asyncio
    async def test_create_post_rejects_empty_title(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_create_post",
                {"title": "", "body": "Valid body", "user_id": 1},
            )
            assert result.isError, "Empty title should be rejected (minLength is 1)"

    @pytest.mark.asyncio
    async def test_create_post_rejects_missing_required_fields(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_create_post",
                {"title": "Only a title"},  # missing body and user_id
            )
            assert result.isError, "Missing required fields should be rejected"

    @pytest.mark.asyncio
    async def test_update_post_rejects_no_fields(self):
        """When no update fields are provided, the tool should return an error.
        This tests the cross-field validation (at least one of title/body/user_id required)."""
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_update_post",
                {"post_id": 1},  # no title, body, or user_id
            )
            assert result.isError, "Update with no fields should be rejected"
            text = result.content[0].text
            assert "at least one" in text.lower() or "title, body" in text.lower(), (
                f"Error should mention required fields, got: {text}"
            )


class TestErrorHandling:
    """Verify errors from the live API are handled gracefully."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_post(self):
        async with create_connected_server_and_client_session(server_instance) as session:
            result = await session.call_tool(
                "api_get_post",
                {"post_id": 99999},
            )
            # Should return an error message, not crash
            text = result.content[0].text
            assert "error" in text.lower() or "404" in text or "not found" in text.lower()


# ============================================================================
# Stdio Transport Tests (spawns server as subprocess, like Claude Desktop)
# ============================================================================


class TestStdioTransport:
    """Spawn the server as a subprocess over stdio — the exact same transport
    Claude Desktop uses. This is the most realistic integration test possible
    without actually using Claude Desktop."""

    @pytest.mark.asyncio
    async def test_full_session_over_stdio(self):
        """Complete session: initialize → discover tools → call a tool → get results."""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "api_bridge_mcp.server"],
        )

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # 1. Initialize (protocol handshake)
                init_result = await session.initialize()
                assert init_result.protocolVersion, "Must negotiate protocol version"
                assert init_result.capabilities.tools, "Must advertise tool capabilities"

                # 2. Discover tools (what Claude Desktop does on startup)
                tools_result = await session.list_tools()
                tool_names = [t.name for t in tools_result.tools]
                assert "api_list_posts" in tool_names
                assert "api_get_post" in tool_names
                assert "api_create_post" in tool_names
                assert "api_update_post" in tool_names

                # 3. Call a tool (what Claude does when it decides to use a tool)
                result = await session.call_tool(
                    "api_list_posts",
                    {"limit": 2, "response_format": "json"},
                )
                assert not result.isError
                data = json.loads(result.content[0].text)
                assert len(data["posts"]) == 2

                # 4. Call another tool in the same session
                result = await session.call_tool(
                    "api_get_post",
                    {"post_id": 1},
                )
                assert not result.isError
                assert "sunt aut facere" in result.content[0].text

    @pytest.mark.asyncio
    async def test_stdio_validation_rejects_bad_input(self):
        """Validation errors are returned (not raised) over stdio transport."""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "api_bridge_mcp.server"],
        )

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                result = await session.call_tool(
                    "api_list_posts",
                    {"limit": 0},  # Below minimum of 1
                )
                assert result.isError, "limit=0 should be rejected over stdio too"
