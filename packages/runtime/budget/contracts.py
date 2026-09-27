from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class BudgetResource(StrEnum):
    WALL_SECONDS = "wall_seconds"
    MODEL_TOKENS = "model_tokens"
    AGENT_TURNS = "agent_turns"
    TOOL_CALLS = "tool_calls"
    RPC_CALLS = "rpc_calls"
    RETRIES = "retries"
    EXTERNAL_COST = "external_cost"
    BYTES_READ = "bytes_read"
    CONCURRENCY = "concurrency"
    RECURSION_DEPTH = "recursion_depth"


class BudgetLimits(BaseModel):
    quantities: dict[str, Decimal] = Field(default_factory=dict)

    @field_validator("quantities")
    @classmethod
    def validate_quantities(cls, value: dict[str, Decimal]) -> dict[str, Decimal]:
        for resource, quantity in value.items():
            if not resource.strip():
                raise ValueError("budget resource cannot be empty")
            if quantity < 0:
                raise ValueError("budget limit cannot be negative")
        return value


class BudgetReservationStatus(StrEnum):
    RESERVED = "reserved"
    COMMITTED = "committed"
    RELEASED = "released"


class BudgetReservation(BaseModel):
    reservation_id: str
    account_id: str
    resource_type: str
    amount_reserved: Decimal
    amount_committed: Decimal = Decimal("0")
    status: BudgetReservationStatus
