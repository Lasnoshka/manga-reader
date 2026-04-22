# check_db.py (в корне проекта)
import asyncio
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.append(str(Path(__file__).parent))

from app.config import settings

async def check_db_connection():
    """Проверяет подключение к PostgreSQL"""
    print(f"🔍 Проверяю подключение к PostgreSQL...")
    print(f"   Host: {settings.POSTGRES_HOST}")
    print(f"   Port: {settings.POSTGRES_PORT}")
    print(f"   User: {settings.POSTGRES_USER}")
    print(f"   DB: {settings.POSTGRES_DB}")
    print(f"   URL: postgresql://{settings.POSTGRES_USER}:***@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    
    try:
        import asyncpg
        
        # Пробуем подключиться
        conn = await asyncpg.connect(
            host=settings.POSTGRES_HOST,
            port=int(settings.POSTGRES_PORT),
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
            timeout=5
        )
        
        # Проверяем версию PostgreSQL
        version = await conn.fetchval("SELECT version()")
        print(f"\n✅ Подключение успешно!")
        print(f"   PostgreSQL версия: {version.split(',')[0]}")
        
        # Проверяем существование таблиц
        tables = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        )
        
        if tables:
            print(f"\n📊 Существующие таблицы:")
            for table in tables:
                print(f"   - {table['table_name']}")
        else:
            print(f"\n📊 Таблиц пока нет (будут созданы при старте FastAPI)")
        
        await conn.close()
        return True
        
    except asyncpg.exceptions.InvalidPasswordError:
        print(f"\n❌ Ошибка: Неверный пароль для пользователя '{settings.POSTGRES_USER}'")
        print(f"   Проверь пароль в файле .env")
        return False
    except asyncpg.exceptions.InvalidCatalogNameError:
        print(f"\n❌ Ошибка: База данных '{settings.POSTGRES_DB}' не существует")
        print(f"\n📝 Создай её в PgAdmin4 или выполни SQL запрос:")
        print(f"   CREATE DATABASE {settings.POSTGRES_DB};")
        return False
    except Exception as e:
        print(f"\n❌ Ошибка подключения: {e}")
        print(f"\n💡 Проверьте:")
        print(f"   1. Запущен ли PostgreSQL (порт {settings.POSTGRES_PORT})")
        print(f"   2. Правильные ли логин/пароль в файле .env")
        print(f"   3. Создана ли база данных '{settings.POSTGRES_DB}'")
        return False

if __name__ == "__main__":
    asyncio.run(check_db_connection())