"""API раздела «Сезон»."""
from __future__ import annotations

from fastapi import APIRouter, Path, Query

from app.domain.season import RaceResult, SeasonOverview
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


@router.get("/round/{round_no}", response_model=RaceResult)
async def race_result(
    round_no: int = Path(..., ge=1, le=30, description="номер этапа сезона"),
    refresh: bool = Query(default=False),
) -> RaceResult:
    """Протокол одного этапа: кто где финишировал, очки, быстрейший круг.

    Загружается по клику на этап в календаре, а не вместе с обзором сезона —
    иначе один запрос тянул бы результаты всех гонок разом.
    """
    return await season_service.get_race_result(round_no, force=refresh)
