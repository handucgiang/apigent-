"""A fake HRM API with fake data, for demos and tests.

Run:  uvicorn hrm_api:app --port 8001   (from this folder)

Tokens:
  Bearer manager-token  -> HR manager, sees every department incl. salary cost
  Bearer staff-token    -> employee in Engineering (d2), own department only, no salary
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query

app = FastAPI(
    title="Demo HRM API",
    version="1.0.0",
    servers=[{"url": "http://localhost:8001"}],
)

DEPARTMENTS = {
    "d1": "Kế toán",
    "d2": "Kỹ thuật",
    "d3": "Kinh doanh",
    "d4": "Nhân sự",
}
HEADCOUNT = {"d1": 8, "d2": 25, "d3": 14, "d4": 5}
TURNOVER = {  # employees who left, per month
    "2026-08": {"d1": 0, "d2": 1, "d3": 2, "d4": 0},
    "2026-09": {"d1": 1, "d2": 2, "d3": 3, "d4": 0},
    "2026-10": {"d1": 0, "d2": 1, "d3": 1, "d4": 1},
}
LEAVE_DAYS = {  # paid leave days taken, per month
    "2026-08": {"d1": 6, "d2": 21, "d3": 9, "d4": 3},
    "2026-09": {"d1": 4, "d2": 18, "d3": 12, "d4": 2},
    "2026-10": {"d1": 5, "d2": 15, "d3": 7, "d4": 4},
}
SALARY_COST_MVND = {"d1": 152, "d2": 780, "d3": 336, "d4": 95}  # million VND / month

USERS = {
    "manager-token": {"name": "Lan", "role": "hr_manager", "department_id": "d4"},
    "staff-token": {"name": "Minh", "role": "staff", "department_id": "d2"},
}


def current_user(authorization: Annotated[str | None, Header()] = None) -> dict[str, str]:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = USERS.get(token)
    if not user:
        raise HTTPException(401, "invalid token")
    return user


User = Annotated[dict[str, str], Depends(current_user)]


def _scope(user: dict[str, str], department_id: str | None) -> list[str]:
    """Departments the user may read for this request."""
    if department_id and department_id not in DEPARTMENTS:
        raise HTTPException(404, "department not found")
    if user["role"] == "hr_manager":
        return [department_id] if department_id else list(DEPARTMENTS)
    if department_id in (None, user["department_id"]):
        return [user["department_id"]]
    raise HTTPException(403, "you may only view your own department")


def _month(month: str, table: dict[str, dict[str, int]]) -> dict[str, int]:
    if month not in table:
        raise HTTPException(404, f"no data for {month}; available: {', '.join(table)}")
    return table[month]


DeptParam = Annotated[
    str | None,
    Query(description="Department ID such as 'd1'. Omit for the whole company."),
]
MonthParam = Annotated[str, Query(description="Month in YYYY-MM format", pattern=r"^\d{4}-\d{2}$")]


@app.get(
    "/departments/search",
    operation_id="searchDepartments",
    summary="Find departments by (part of) their Vietnamese name; returns id and name.",
)
async def search_departments(
    user: User, keyword: Annotated[str, Query(description="e.g. 'kế toán'")] = ""
) -> list[dict[str, str]]:
    kw = keyword.lower().strip()
    return [{"id": k, "name": v} for k, v in DEPARTMENTS.items() if kw in v.lower()]


@app.get(
    "/reports/headcount",
    operation_id="getHeadcount",
    summary="Current number of active employees, per department and total.",
)
async def headcount(user: User, department_id: DeptParam = None) -> dict[str, object]:
    depts = _scope(user, department_id)
    rows = [{"department": DEPARTMENTS[d], "headcount": HEADCOUNT[d]} for d in depts]
    return {"rows": rows, "total": sum(r["headcount"] for r in rows)}  # type: ignore[misc]


@app.get(
    "/reports/turnover",
    operation_id="getTurnover",
    summary="Number of employees who left in a month, per department and total.",
)
async def turnover(
    user: User, month: MonthParam, department_id: DeptParam = None
) -> dict[str, object]:
    data = _month(month, TURNOVER)
    depts = _scope(user, department_id)
    rows = [{"department": DEPARTMENTS[d], "left": data[d]} for d in depts]
    return {"month": month, "rows": rows, "total": sum(r["left"] for r in rows)}  # type: ignore[misc]


@app.get(
    "/reports/leave-summary",
    operation_id="getLeaveSummary",
    summary="Paid leave days taken in a month, per department and total.",
)
async def leave_summary(
    user: User, month: MonthParam, department_id: DeptParam = None
) -> dict[str, object]:
    data = _month(month, LEAVE_DAYS)
    depts = _scope(user, department_id)
    rows = [{"department": DEPARTMENTS[d], "leave_days": data[d]} for d in depts]
    return {"month": month, "rows": rows, "total": sum(r["leave_days"] for r in rows)}  # type: ignore[misc]


@app.get(
    "/reports/salary-cost",
    operation_id="getSalaryCost",
    summary="Monthly salary cost in million VND, per department. HR managers only.",
)
async def salary_cost(user: User, department_id: DeptParam = None) -> dict[str, object]:
    if user["role"] != "hr_manager":
        raise HTTPException(403, "HR managers only")
    depts = _scope(user, department_id)
    rows = [{"department": DEPARTMENTS[d], "million_vnd": SALARY_COST_MVND[d]} for d in depts]
    return {"rows": rows, "total_million_vnd": sum(r["million_vnd"] for r in rows)}  # type: ignore[misc]
