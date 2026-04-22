# Manga Reader

Pet-project: async-бэкенд + веб-интерфейс читалки манги.

## Стек

- **Python 3.11+**, **FastAPI**, async SQLAlchemy 2.0
- **PostgreSQL 16** (asyncpg), **Redis 7** (cache-aside + sorted set для популярного)
- **Alembic** для миграций
- **JWT** (python-jose) + bcrypt для аутентификации
- **Jinja2 + Alpine.js** для SSR-интерфейса поверх того же JSON API
- Docker Compose для локального окружения

## Что умеет

- Каталог манги с пагинацией, фильтром по жанрам, поиском, сортировкой
- Страница тайтла: главы, лайки, закладки (5 папок), комментарии с древовидными ответами
- Читалка глав с автосохранением прогресса и выезжающим списком глав
- JWT-регистрация/логин, профиль с закладками и историей чтения
- **Админка** (`/admin/manga`): CRUD манги прямо в вебе
- Кэширование списков/деталей в Redis с TTL и graceful degradation если Redis не поднят
- Popular-манга через Redis sorted set (инкремент просмотров на каждый GET `/manga/{id}`)
- **ARQ-воркер** для фоновых задач (пересчёт рейтингов), отдельный процесс

## Быстрый старт

```bash
cp .env.example .env            # отредактируй POSTGRES_PASSWORD, JWT_SECRET
docker compose up -d postgres redis
pip install -r requirements.txt
alembic upgrade head
python scripts/seed_db.py       # демо-данные + учётки admin/reader
uvicorn app.main:app --reload
# отдельным процессом — воркер фоновых задач (опционально):
arq app.tasks.worker.WorkerSettings
```

Открыть `http://localhost:8000` — интерфейс, `http://localhost:8000/docs` — Swagger.

Тестовые учётки после seed:
- `admin` / `admin12345` — роль `admin`, видит пункт «Админка» в шапке
- `reader` / `reader12345` — обычный пользователь

## Полностью в docker-compose

```bash
docker compose up --build
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed_db.py
```

## Структура

```
app/
├── api/v1/           # JSON API: auth, manga, chapters, comments, bookmarks, likes, progress
├── web/              # SSR-роуты (главная, каталог, тайтл, ридер, админка)
├── cache/            # Redis client + ключи
├── core/             # exceptions, logger, security (JWT, bcrypt)
├── db/               # модели SQLAlchemy, сессии, base
├── middleware/       # HTTP-логирование
├── migrations/       # Alembic
├── tasks/            # ARQ worker + клиент очереди
├── templates/        # Jinja2
├── static/           # css/js
└── main.py           # FastAPI app, lifespan, роутеры
tests/                # pytest (WIP)
scripts/seed_db.py    # демо-данные
```

## Разработка

```bash
pip install -r requirements-dev.txt
pycodestyle --max-line-length=120 app/
pytest
```

## Примечания

- Redis не обязателен — без него кэш-функции возвращают пустоту/no-op, API продолжает работать
- Все `create/update/delete` эндпоинты манги защищены `require_admin`
- Миграции в `app/migrations/versions/` — две: bootstrap-схема и user-features
