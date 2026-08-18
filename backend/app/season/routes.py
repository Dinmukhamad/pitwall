"""API раздела «Сезон»."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.domain.season import SeasonOverview
from app.season.service import season_service

router = APIRouter(prefix="/api/season", tags=["season"])


@router.get("", response_model=SeasonOverview)
async def season_overview(
    refresh: bool = Query(default=False, description="обойти кэш"),
) -> SeasonOverview:
    """Календарь, личный зачёт и кубок конструкторов текущего сезона.

    При недоступности источника возвращает тот же объект с полем `error` —
    клиент показывает состояние ошибки, а не пустые таблицы.
    """
    return await season_service.get_overview(force=refresh)
