"""Regression tests for SDK 2 server imports and tool registration."""


def test_app_exposes_server_instance():
    """The SDK 2 server instance imports and registers tools."""
    from monarch_mcp_server.app import mcp

    assert mcp is not None
    assert hasattr(mcp, "tool")
    assert hasattr(mcp, "run")


def test_context_is_importable():
    """Context resolves from the SDK 2 server module."""
    from monarch_mcp_server import auth

    assert auth.Context is not None


async def test_tools_are_registered():
    """Tool registration survives the import indirection."""
    from monarch_mcp_server.app import mcp

    tools = await mcp.list_tools()
    assert len(tools) > 0
