"""Tests for the household budget tool's full response projection."""

import json

from monarch_mcp_server.tools.budgets import get_budgets


class TestGetBudgets:
    async def test_returns_categories_flex_expense_and_totals(self, mock_monarch_client):
        mock_monarch_client.get_budgets.return_value = {
            "categoryGroups": [
                {"categories": [{"id": "cat-1", "name": "Groceries", "budgetVariability": "FIXED"}]}
            ],
            "budgetData": {
                "monthlyAmountsByCategory": [
                    {"category": {"id": "cat-1"}, "monthlyAmounts": [{
                        "month": "2026-03-01", "plannedCashFlowAmount": 500,
                        "actualAmount": 320, "remainingAmount": 180,
                        "previousMonthRolloverAmount": 20,
                    }]}
                ],
                "monthlyAmountsForFlexExpense": {
                    "budgetVariability": "FLEXIBLE",
                    "monthlyAmounts": [{"month": "2026-03-01", "plannedCashFlowAmount": 200,
                                        "actualAmount": 150, "remainingAmount": 50,
                                        "previousMonthRolloverAmount": 10}],
                },
                "totalsByMonth": [{"month": "2026-03-01", "totalIncome": {
                    "plannedAmount": 3000, "actualAmount": 2900, "remainingAmount": 100
                }}],
            },
        }
        result = json.loads(await get_budgets())
        assert result["categories"] == [{
            "category": "Groceries", "category_id": "cat-1", "variability": "FIXED",
            "month": "2026-03-01", "planned": 500, "actual": 320,
            "remaining": 180, "rollover": 20,
        }]
        assert result["flex_expense"] == {
            "variability": "FLEXIBLE",
            "months": [{"month": "2026-03-01", "planned": 200, "actual": 150,
                        "remaining": 50, "rollover": 10}],
        }
        assert result["totals"] == [{
            "month": "2026-03-01",
            "totalIncome": {"planned": 3000, "actual": 2900, "remaining": 100},
        }]

    async def test_passes_only_explicit_dates(self, mock_monarch_client):
        mock_monarch_client.get_budgets.return_value = {}
        await get_budgets(start_date="2026-03-01", end_date="2026-03-31")
        mock_monarch_client.get_budgets.assert_awaited_once_with(
            start_date="2026-03-01", end_date="2026-03-31"
        )

    async def test_omitted_dates_use_client_defaults(self, mock_monarch_client):
        mock_monarch_client.get_budgets.return_value = {}
        await get_budgets()
        mock_monarch_client.get_budgets.assert_awaited_once_with()

    async def test_handles_api_error(self, mock_monarch_client):
        mock_monarch_client.get_budgets.side_effect = Exception("Budget error")
        result = json.loads(await get_budgets())
        assert result["error"] and result["tool"] == "get_budgets"
