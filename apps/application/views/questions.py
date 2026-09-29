from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator

from apps.application.views.investigations import DecisionView, InvestigationView


class QuestionResultView(BaseModel):
    request_id: str
    session_id: str
    turn_index: int
    mode: Literal["completed", "accepted"]
    execution_profile: str
    decision: DecisionView | None = None
    investigation: InvestigationView | None = None

    @model_validator(mode="after")
    def validate_result(self) -> QuestionResultView:
        if self.mode == "completed":
            if self.decision is None or self.investigation is not None:
                raise ValueError("completed question requires decision only")
        elif self.investigation is None or self.decision is not None:
            raise ValueError("accepted question requires investigation only")
        return self
