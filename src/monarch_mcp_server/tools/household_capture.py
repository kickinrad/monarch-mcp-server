"""Read a declared subset of accounts as a Marketlab household capture."""

import json
from datetime import UTC, datetime

from monarch_mcp_server.app import mcp
from monarch_mcp_server.client import get_monarch_client
from monarch_mcp_server.household_capture import build_household_capture


@mcp.tool()
async def get_household_capture(account_ids: list[str]) -> str:
    """Capture declared accounts without refreshing or mutating them."""
    if not account_ids or len(account_ids) != len(set(account_ids)):
        raise ValueError("account_ids must be a nonempty unique list")

    client = await get_monarch_client()
    accounts = await client.get_accounts()
    selected = {
        account.get("id"): account
        for account in accounts.get("accounts", [])
        if account.get("id") in account_ids
    }
    holdings = {}
    for account_id in account_ids:
        account = selected.get(account_id)
        if account is not None and account.get("holdingsCount", 0) > 0:
            holdings[account_id] = await client.get_account_holdings(account_id)

    capture = build_household_capture(
        accounts,
        holdings,
        account_ids=tuple(account_ids),
        captured_at=datetime.now(UTC),
    )
    return json.dumps(capture, separators=(",", ":"), sort_keys=True)
