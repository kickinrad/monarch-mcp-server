"""Budget response parsing with fields omitted by some Monarch accounts."""

from monarch_mcp_server.tools.budgets import format_budget_data


def test_format_budget_data_preserves_category_when_optional_fields_are_absent():
    raw = {
        "budgetData": {
            "monthlyAmountsByCategory": [{
                "category": {"id": "cat-1"},
                "monthlyAmounts": [{
                    "month": "2026-06-01", "plannedCashFlowAmount": -100,
                    "actualAmount": -25, "remainingAmount": -75,
                }],
            }],
        },
        "categoryGroups": [{
            "name": "Food", "categories": [{"id": "cat-1", "name": "Groceries"}],
        }],
    }
    assert format_budget_data(raw) == {
        "categories": [{
            "category": "Groceries", "category_id": "cat-1", "variability": None,
            "month": "2026-06-01", "planned": -100, "actual": -25,
            "remaining": -75, "rollover": None,
        }],
        "flex_expense": None,
        "totals": [],
    }
