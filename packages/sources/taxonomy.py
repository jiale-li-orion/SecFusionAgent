from __future__ import annotations

from enum import StrEnum


class SourcePortfolioCategory(StrEnum):
    VULNERABILITY = "vulnerability"
    DEVELOPMENT = "development"
    ACADEMIC = "academic"
    VENDOR = "vendor"
    INDEPENDENT = "independent"
    NORMATIVE = "normative"
    ASSETS = "assets"
    INCIDENTS = "incidents"


SOURCE_PORTFOLIO_CATEGORY_ORDER: tuple[SourcePortfolioCategory, ...] = (
    SourcePortfolioCategory.VULNERABILITY,
    SourcePortfolioCategory.DEVELOPMENT,
    SourcePortfolioCategory.ACADEMIC,
    SourcePortfolioCategory.VENDOR,
    SourcePortfolioCategory.INDEPENDENT,
    SourcePortfolioCategory.NORMATIVE,
    SourcePortfolioCategory.ASSETS,
    SourcePortfolioCategory.INCIDENTS,
)

SOURCE_PORTFOLIO_CATEGORIES = frozenset(SOURCE_PORTFOLIO_CATEGORY_ORDER)
