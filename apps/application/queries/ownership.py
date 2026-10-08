"""Read authorization from durable TaskContract and QuestionSession owners."""

from __future__ import annotations

from sqlalchemy import SQLColumnExpression, and_, or_, select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import ScalarSelect, Select

from packages.task_runtime.storage.models import TaskContractVersionModel, TaskRunModel


def investigation_owner(case_id: str | SQLColumnExpression[str]) -> ScalarSelect[str]:
    # The InvestigationRole controller owns the Case, including its later
    # DecisionRole run. This matches the cancellation owner boundary.
    return (
        select(TaskContractVersionModel.principal)
        .join(
            TaskRunModel,
            TaskRunModel.task_contract_version_id
            == TaskContractVersionModel.task_contract_version_id,
        )
        .where(TaskRunModel.case_id == case_id)
        .order_by(
            (TaskRunModel.role_id == "InvestigationRole").desc(),
            TaskRunModel.created_at.desc(),
            TaskRunModel.run_id.desc(),
        )
        .limit(1)
        .correlate_except(TaskRunModel, TaskContractVersionModel)
        .scalar_subquery()
    )


def public_system_case(case_id: str | SQLColumnExpression[str]) -> ColumnElement[bool]:
    """A system controller alone cannot publish user-delegated or mixed Cases."""
    private_run = (
        select(TaskRunModel.run_id)
        .join(
            TaskContractVersionModel,
            TaskContractVersionModel.task_contract_version_id
            == TaskRunModel.task_contract_version_id,
        )
        .where(
            TaskRunModel.case_id == case_id,
            or_(
                TaskContractVersionModel.principal.startswith("user:"),
                TaskContractVersionModel.on_behalf_of.startswith("user:"),
            ),
        )
        .correlate_except(TaskRunModel, TaskContractVersionModel)
        .exists()
    )
    return and_(investigation_owner(case_id).startswith("system:"), ~private_run)


def visible_task_run_ids(principal: str | None) -> Select[str]:
    statement = select(TaskRunModel.run_id)
    if principal is None:
        return statement
    return statement.join(
        TaskContractVersionModel,
        TaskContractVersionModel.task_contract_version_id == TaskRunModel.task_contract_version_id,
    ).where(
        or_(
            TaskContractVersionModel.principal == principal,
            (
                TaskContractVersionModel.principal.startswith("system:")
                & or_(
                    TaskContractVersionModel.on_behalf_of.is_(None),
                    ~TaskContractVersionModel.on_behalf_of.startswith("user:"),
                    TaskContractVersionModel.on_behalf_of == principal,
                )
            ),
        )
    )
