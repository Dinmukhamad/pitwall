# Публикация Pit Wall через GitHub + Render

Порядок: сначала кладём код на GitHub, потом Render разворачивает его по
`render.yaml` (веб-сервис + Postgres + Redis). Архив, который вы скачали, уже
содержит готовый git-репозиторий с первым коммитом — остаётся добавить remote и
запушить.

---

## Шаг 1. Залить код на GitHub

1. Создайте пустой репозиторий на GitHub (без README/gitignore), например `pitwall`.
   Скопируйте его URL, вида `https://github.com/ВАШ_ЛОГИН/pitwall.git`.

2. В распакованной папке проекта выполните (репозиторий и коммит уже созданы):

```bash
cd pitwall
git remote add origin https://github.com/ВАШ_ЛОГИН/pitwall.git
git branch -M main
git push -u origin main
```

Если git-репозитория внутри нет (распаковали без `.git`) — инициализируйте:

```bash
cd pitwall
git init && git add . && git commit -m "Pit Wall — initial"
git branch -M main
git remote add origin https://github.com/ВАШ_ЛОГИН/pitwall.git
git push -u origin main
```

> Аутентификация: при `git push` GitHub попросит логин и **personal access
> token** (не пароль). Токен: GitHub → Settings → Developer settings →
> Personal access tokens. Либо поставьте `gh` CLI и `gh auth login`.

---

## Шаг 2. Развернуть на Render (Blueprint — рекомендуется)

1. Зайдите на https://render.com, залогиньтесь через GitHub.
2. **New → Blueprint**, выберите свой репозиторий `pitwall`.
3. Render найдёт `render.yaml` и покажет три ресурса: **pitwall** (web),
   **pitwall-db** (Postgres), **pitwall-redis** (Redis). Нажмите **Apply**.
4. Дождитесь сборки (первый деплой ~2–4 мин). Приложение откроется по адресу
   вида `https://pitwall-XXXX.onrender.com`.
5. Проверьте здоровье: `https://.../api/health` → должно вернуть
   `{"status":"ok","db_enabled":true,"cache_backend":"redis", ...}`.

Готово — фронтенд и API работают на одном домене.

### Переключение на живые данные OpenF1
По умолчанию стоит `PITWALL_DATA_SOURCE=fixture` (демо-гонка, работает всегда).
Чтобы включить живой OpenF1: дашборд Render → сервис **pitwall** →
**Environment** → поменяйте `PITWALL_DATA_SOURCE` на `openf1` → **Save**
(сервис передеплоится). Живые данные видны во время/после реальных сессий F1.

---

## Альтернатива: без Blueprint (вручную)

Если не хотите Blueprint, создайте ресурсы по отдельности:

1. **New → PostgreSQL** (план free) → скопируйте *Internal Database URL*.
2. **New → Redis** (план free) → скопируйте *Internal Redis URL*.
3. **New → Web Service** → ваш GitHub-репозиторий, настройки:
   - **Root Directory:** `backend`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt && python scripts/generate_fixture.py`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path:** `/api/health`
   - **Environment** (Add Environment Variable):
     - `DATABASE_URL` = *Internal Database URL* из п.1
     - `REDIS_URL` = *Internal Redis URL* из п.2
     - `PITWALL_DATA_SOURCE` = `fixture` (или `openf1`)
     - `PYTHON_VERSION` = `3.12.6`

Приложение само приведёт схему `postgres://` к `postgresql+asyncpg://` и
создаст таблицы при старте.

---

## Замечания
- **Free-план** веб-сервиса «засыпает» при простое — первый запрос после паузы
  идёт ~30–60 с, это норма для бесплатного тарифа.
- Если Postgres/Redis недоступны — приложение **не падает**: работает на
  in-memory кэше без персистентности (см. архитектуру). Но для публикации
  корректно, когда `/api/health` показывает `db_enabled:true`.
- Обновление: любой `git push` в `main` автоматически передеплоит Render.
