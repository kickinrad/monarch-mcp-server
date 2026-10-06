"""Budget tools."""

import logging
from typing import Any, Dict, List, Optional

from monarch_mcp_server.app import mcp
from monarch_mcp_server.client import get_monarch_client
from monarch_mcp_server.helpers import json_success, json_error

logger = logging.getLogger(__name__)


def format_budget_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Project Monarch's full budget response into category, flex, and total rows."""
    category_names = {}
    category_variability = {}
    for group in data.get("categoryGroups", []):
        for category in group.get("categories", []):
            category_id = category.get("id")
            category_names[category_id] = category.get("name")
            category_variability[category_id] = category.get("budgetVariability")

    budget_data = data.get("budgetData") or {}
    result: Dict[str, Any] = {"categories": [], "flex_expense": None, "totals": []}
    for entry in budget_data.get("monthlyAmountsByCategory", []):
        category_id = (entry.get("category") or {}).get("id")
        for month in entry.get("monthlyAmounts", []):
            result["categories"].append(
                {
                    "category": category_names.get(category_id, category_id),
                    "category_id": category_id,
                    "variability": category_variability.get(category_id),
                    "month": month.get("month"),
                    "planned": month.get("plannedCashFlowAmount"),
                    "actual": month.get("actualAmount"),
                    "remaining": month.get("remainingAmount"),
                    "rollover": month.get("previousMonthRolloverAmount"),
                }
            )

    flex = budget_data.get("monthlyAmountsForFlexExpense")
    if flex:
        result["flex_expense"] = {
            "variability": flex.get("budgetVariability"),
            "months": [
                {
                    "month": month.get("month"),
                    "planned": month.get("plannedCashFlowAmount"),
                    "actual": month.get("actualAmount"),
                    "remaining": month.get("remainingAmount"),
                    "rollover": month.get("previousMonthRolloverAmount"),
                }
                for month in flex.get("monthlyAmounts", [])
            ],
        }

    for total in budget_data.get("totalsByMonth", []):
        row = {"month": total.get("month")}
        for key in (
            "totalIncome",
            "totalExpenses",
            "totalFixedExpenses",
            "totalNonMonthlyExpenses",
            "totalFlexibleExpenses",
        ):
            section = total.get(key)
            if section:
                row[key] = {
                    "planned": section.get("plannedAmount"),
                    "actual": section.get("actualAmount"),
                    "remaining": section.get("remainingAmount"),
                }
        result["totals"].append(row)
    return result


@mcp.tool()
async def get_budgets(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """Get category, flex-expense, and monthly total budgets.

    Dates are YYYY-MM-DD; omitted dates use Monarch's defaults. Returns a JSON
    object with ``categories``, ``flex_expense``, and ``totals`` keys.
    """
    try:
        client = await get_monarch_client()
        filters = {}
        if start_date:
            filters["start_date"] = start_date
        if end_date:
            filters["end_date"] = end_date
        return json_success(format_budget_data(await client.get_budgets(**filters)))
    except Exception as error:
        return json_error("get_budgets", error)


@mcp.tool()
async def set_budget_amount(
    amount: float,
    category_id: Optional[str] = None,
    category_group_id: Optional[str] = None,
    start_date: Optional[str] = None,
    apply_to_future: bool = False,
) -> str:
    """
    Set or update a budget amount for a category or category group.

    Use get_budgets() first to see current budgets and category IDs.
    Use get_categories() or get_category_groups() to find category/group IDs.

    Args:
        amount: The budget amount to set. Use 0 to clear/unset the budget.
        category_id: The ID of the category to budget (cannot use with category_group_id)
        category_group_id: The ID of the category group to budget (cannot use with category_id)
        start_date: The month to set budget for in YYYY-MM-DD format (defaults to current month)
        apply_to_future: Whether to apply this amount to all future months (default: False)

    Returns:
        Result of the budget update.

    Examples:
        Set grocery budget to $600 for current month:
            set_budget_amount(amount=600, category_id="cat_groceries_123")

        Set dining budget to $200 and apply to all future months:
            set_budget_amount(amount=200, category_id="cat_dining_456", apply_to_future=True)

        Clear a budget (set to 0):
            set_budget_amount(amount=0, category_id="cat_123")
    """
    try:
        if category_id and category_group_id:
            return json_success({
                "success": False,
                "error": "Cannot specify both category_id and category_group_id. Choose one."
            })

        if not category_id and not category_group_id:
            return json_success({
                "success": False,
                "error": "Must specify either category_id or category_group_id."
            })

        client = await get_monarch_client()

        params: Dict[str, Any] = {
            "amount": amount,
            "apply_to_future": apply_to_future,
        }

        if category_id:
            params["category_id"] = category_id
        if category_group_id:
            params["category_group_id"] = category_group_id
        if start_date:
            params["start_date"] = start_date

        result = await client.set_budget_amount(**params)

        # No literal "success": True here. The upstream mutation selects no
        # errors field, so there is nothing to check and nothing that justifies
        # asserting the write landed. Report what was requested and hand back
        # the raw result rather than a claim the response cannot support.
        return json_success({
            "requested": {
                "amount": amount,
                "apply_to_future": apply_to_future,
                "category_id": category_id,
                "category_group_id": category_group_id,
                "start_date": start_date,
            },
            "result": result,
        })
    except Exception as e:
        return json_error("set_budget_amount", e)
