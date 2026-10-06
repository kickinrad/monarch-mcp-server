"""Pure projection of Monarch responses into Marketlab's capture envelope."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_SCHEMA = "marketlab.monarch-household-capture/v1"


class HouseholdCaptureError(ValueError):
    """Monarch responses cannot form an unambiguous household capture."""


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HouseholdCaptureError(f"missing Monarch {field}")
    return value.strip()


def _decimal_text(value: object, field: str) -> str:
    if isinstance(value, bool) or value is None:
        raise HouseholdCaptureError(f"invalid Monarch {field}")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise HouseholdCaptureError(f"invalid Monarch {field}") from error
    if not parsed.is_finite():
        raise HouseholdCaptureError(f"invalid Monarch {field}")
    return format(parsed, "f")


def _utc_text(value: object, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise HouseholdCaptureError(f"invalid Monarch {field}") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HouseholdCaptureError(f"invalid Monarch {field}")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _capture_time(value: datetime) -> str:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise HouseholdCaptureError("capture time must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _holding_edges(response: object, account_id: str) -> list[dict[str, Any]]:
    try:
        edges = response["portfolio"]["aggregateHoldings"]["edges"]
    except (KeyError, TypeError) as error:
        raise HouseholdCaptureError(
            f"invalid Monarch holdings response for {account_id}"
        ) from error
    if not isinstance(edges, list) or not all(isinstance(edge, dict) for edge in edges):
        raise HouseholdCaptureError(
            f"invalid Monarch holdings response for {account_id}"
        )
    return edges


def _project_holding(account_id: str, edge: dict[str, Any]) -> dict[str, object]:
    node = edge.get("node")
    if not isinstance(node, dict):
        raise HouseholdCaptureError("Monarch holding node is missing")
    identity = node.get("security") or node.get("holdings")
    if not isinstance(identity, dict):
        raise HouseholdCaptureError("Monarch holding instrument identity is missing")
    observed_at = (
        node.get("lastSyncedAt")
        or identity.get("currentPriceUpdatedAt")
        or identity.get("closingPriceUpdatedAt")
    )
    basis = node.get("basis")
    quantity = node.get("quantity")
    return {
        "external_account_id": account_id,
        "external_holding_id": _text(node.get("id"), "holding id"),
        "instrument_key": _text(identity.get("id"), "security id"),
        "quantity": (
            _decimal_text(quantity, "holding quantity")
            if quantity is not None
            else None
        ),
        "basis": (_decimal_text(basis, "holding basis") if basis is not None else None),
        "total_value": _decimal_text(node.get("totalValue"), "holding value"),
        "observed_at": _utc_text(observed_at, "holding update time"),
    }


def build_household_capture(
    accounts_response: object,
    holdings_by_account: dict[str, object],
    *,
    account_ids: tuple[str, ...],
    captured_at: datetime,
) -> dict[str, object]:
    """Build a deterministic, declared-account-only Marketlab capture."""
    if not isinstance(accounts_response, dict) or not isinstance(
        accounts_response.get("accounts"), list
    ):
        raise HouseholdCaptureError("invalid Monarch accounts response")
    if (
        type(account_ids) is not tuple
        or not account_ids
        or not all(isinstance(item, str) and item for item in account_ids)
        or len(account_ids) != len(set(account_ids))
    ):
        raise HouseholdCaptureError("declared Monarch accounts must be unique")
    raw_accounts = {
        item.get("id"): item
        for item in accounts_response["accounts"]
        if isinstance(item, dict) and item.get("id") in account_ids
    }
    if set(raw_accounts) != set(account_ids):
        raise HouseholdCaptureError("declared Monarch account is missing")

    accounts: list[dict[str, object]] = []
    holdings: list[dict[str, object]] = []
    for account_id in sorted(account_ids):
        account = raw_accounts[account_id]
        if account.get("deactivatedAt") is not None:
            raise HouseholdCaptureError("declared Monarch account is deactivated")
        count = account.get("holdingsCount")
        if type(count) is not int or count < 0:
            raise HouseholdCaptureError("invalid Monarch holdings count")
        response = holdings_by_account.get(account_id)
        edges = _holding_edges(response, account_id) if count else []
        if len(edges) != count:
            raise HouseholdCaptureError("Monarch holdings count differs from response")
        accounts.append(
            {
                "external_account_id": account_id,
                "balance": _decimal_text(
                    account.get("currentBalance"), "account balance"
                ),
                "updated_at": _utc_text(
                    account.get("displayLastUpdatedAt") or account.get("updatedAt"),
                    "account update time",
                ),
                "holdings_count": count,
            }
        )
        holdings.extend(_project_holding(account_id, edge) for edge in edges)
    holdings.sort(
        key=lambda item: (
            str(item["external_account_id"]),
            str(item["external_holding_id"]),
        )
    )
    return {
        "schema": _SCHEMA,
        "captured_at": _capture_time(captured_at),
        "accounts": accounts,
        "holdings": holdings,
    }
