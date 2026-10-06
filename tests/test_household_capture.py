import json
from datetime import UTC, datetime

from monarch_mcp_server.tools import household_capture as capture_tool
from monarch_mcp_server.household_capture import build_household_capture

CAPTURED_AT = datetime(2026, 7, 29, 20, 1, tzinfo=UTC)


def test_capture_projects_only_declared_accounts_and_stable_holding_identity() -> None:
    accounts = {
        "accounts": [
            {
                "id": "acct-ignored",
                "currentBalance": 99,
                "displayLastUpdatedAt": "2026-07-29T20:00:00Z",
                "holdingsCount": 0,
                "deactivatedAt": None,
            },
            {
                "id": "acct-taxable",
                "currentBalance": 550.0,
                "displayLastUpdatedAt": "2026-07-29T20:00:00Z",
                "holdingsCount": 1,
                "deactivatedAt": None,
            },
        ]
    }
    holdings = {
        "acct-taxable": {
            "portfolio": {
                "aggregateHoldings": {
                    "edges": [
                        {
                            "node": {
                                "id": "aggregate-aapl",
                                "quantity": 2.0,
                                "basis": 300.0,
                                "totalValue": 400.0,
                                "lastSyncedAt": "2026-07-29T19:59:00Z",
                                "holdings": None,
                                "security": {
                                    "id": "security-aapl",
                                    "currentPriceUpdatedAt": ("2026-07-29T19:59:00Z"),
                                },
                            }
                        }
                    ]
                }
            }
        }
    }

    result = build_household_capture(
        accounts,
        holdings,
        account_ids=("acct-taxable",),
        captured_at=CAPTURED_AT,
    )

    assert result == {
        "schema": "marketlab.monarch-household-capture/v1",
        "captured_at": "2026-07-29T20:01:00Z",
        "accounts": [
            {
                "external_account_id": "acct-taxable",
                "balance": "550.0",
                "updated_at": "2026-07-29T20:00:00Z",
                "holdings_count": 1,
            }
        ],
        "holdings": [
            {
                "external_account_id": "acct-taxable",
                "external_holding_id": "aggregate-aapl",
                "instrument_key": "security-aapl",
                "quantity": "2.0",
                "basis": "300.0",
                "total_value": "400.0",
                "observed_at": "2026-07-29T19:59:00Z",
            }
        ],
    }


async def test_mcp_tool_reads_holdings_only_for_declared_accounts(monkeypatch) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.holding_requests = []

        async def get_accounts(self):
            return {
                "accounts": [
                    {
                        "id": "acct-declared",
                        "currentBalance": 10,
                        "displayLastUpdatedAt": "2026-07-29T20:00:00Z",
                        "holdingsCount": 0,
                        "deactivatedAt": None,
                    },
                    {
                        "id": "acct-private",
                        "currentBalance": 20,
                        "displayLastUpdatedAt": "2026-07-29T20:00:00Z",
                        "holdingsCount": 1,
                        "deactivatedAt": None,
                    },
                ]
            }

        async def get_account_holdings(self, account_id):
            self.holding_requests.append(account_id)
            raise AssertionError("undeclared holdings must not be queried")

    client = FakeClient()

    async def fake_client():
        return client

    monkeypatch.setattr(capture_tool, "get_monarch_client", fake_client)

    capture = json.loads(await capture_tool.get_household_capture(["acct-declared"]))

    assert [item["external_account_id"] for item in capture["accounts"]] == [
        "acct-declared"
    ]
    assert capture["holdings"] == []
    assert client.holding_requests == []
