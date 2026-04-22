import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import app.db.session_runtime as db_session
from app.core.security import hash_password
from app.db.models.chapter import Chapter
from app.db.models.genre import Genre
from app.db.models.manga import Manga
from app.db.models.page import Page
from app.db.models.user import User


SEED_USERS = [
    {
        "username": "admin",
        "email": "admin@example.com",
        "password": "admin12345",
        "role": "admin",
    },
    {
        "username": "reader",
        "email": "reader@example.com",
        "password": "reader12345",
        "role": "user",
    },
]


SEED_DATA = [
    {
        "title": "Berserk",
        "description": (
            "Тёмное фэнтези о Гатсе — наёмнике, чья жизнь превратилась в бесконечную "
            "войну с демонами и собственным прошлым. Эпос о мести, дружбе и судьбе."
        ),
        "author": "Kentaro Miura",
        "cover_image": "https://placehold.co/600x900/1f1711/e6d7c3?text=Berserk",
        "rating": 9.8,
        "genres": ["Dark Fantasy", "Action", "Drama", "Seinen"],
        "chapters": [
            {"number": 1.0, "title": "The Black Swordsman", "volume": 1, "pages": 8},
            {"number": 2.0, "title": "Brand of Sacrifice", "volume": 1, "pages": 7},
            {"number": 3.0, "title": "Guardians of Desire", "volume": 1, "pages": 9},
            {"number": 4.0, "title": "The Golden Age", "volume": 2, "pages": 10},
        ],
    },
    {
        "title": "Vinland Saga",
        "description": (
            "Юный викинг Торфинн жаждет мести за отца. Сага о крови, чести и долгом пути "
            "к пониманию настоящей силы — отказа от насилия."
        ),
        "author": "Makoto Yukimura",
        "cover_image": "https://placehold.co/600x900/2a3320/d8dfd3?text=Vinland+Saga",
        "rating": 9.5,
        "genres": ["Historical", "Adventure", "Drama", "Seinen"],
        "chapters": [
            {"number": 1.0, "title": "Normanni", "volume": 1, "pages": 8},
            {"number": 2.0, "title": "Sword", "volume": 1, "pages": 7},
            {"number": 3.0, "title": "Troll", "volume": 1, "pages": 9},
        ],
    },
    {
        "title": "Chainsaw Man",
        "description": (
            "Дэндзи мечтает о простой жизни, но получает работу охотника на демонов "
            "и силу бензопилы. Хаотичный экшен о выживании, любви и желаниях."
        ),
        "author": "Tatsuki Fujimoto",
        "cover_image": "https://placehold.co/600x900/3d1e17/f1d4c7?text=Chainsaw+Man",
        "rating": 9.1,
        "genres": ["Action", "Horror", "Supernatural", "Shonen"],
        "chapters": [
            {"number": 1.0, "title": "Dog & Chainsaw", "volume": 1, "pages": 9},
            {"number": 2.0, "title": "Arrival in Tokyo", "volume": 1, "pages": 8},
            {"number": 3.0, "title": "Power", "volume": 1, "pages": 8},
            {"number": 4.0, "title": "Rescue", "volume": 2, "pages": 7},
        ],
    },
    {
        "title": "One Piece",
        "description": (
            "Монки Д. Луффи отправляется в путешествие, чтобы стать королём пиратов "
            "и найти легендарное сокровище — Уан Пис."
        ),
        "author": "Eiichiro Oda",
        "cover_image": "https://placehold.co/600x900/0e3a5c/ffe9b6?text=One+Piece",
        "rating": 9.4,
        "genres": ["Action", "Adventure", "Comedy", "Shonen"],
        "chapters": [
            {"number": 1.0, "title": "Romance Dawn", "volume": 1, "pages": 12},
            {"number": 2.0, "title": "They Call Him 'Strawhat Luffy'", "volume": 1, "pages": 10},
            {"number": 3.0, "title": "Pirate Hunter Zoro", "volume": 1, "pages": 11},
        ],
    },
    {
        "title": "Jujutsu Kaisen",
        "description": (
            "Ютá Окоцу проглатывает палец Сукуны — могущественного проклятия — "
            "и попадает в школу магов, где учится сражаться с тьмой."
        ),
        "author": "Gege Akutami",
        "cover_image": "https://placehold.co/600x900/2a2238/d6c8ee?text=Jujutsu+Kaisen",
        "rating": 9.0,
        "genres": ["Action", "Supernatural", "School", "Shonen"],
        "chapters": [
            {"number": 1.0, "title": "Ryomen Sukuna", "volume": 1, "pages": 9},
            {"number": 2.0, "title": "For Myself", "volume": 1, "pages": 8},
            {"number": 3.0, "title": "Girl of Steel", "volume": 1, "pages": 8},
        ],
    },
    {
        "title": "Attack on Titan",
        "description": (
            "Человечество прячется за гигантскими стенами от титанов — пока однажды "
            "самый огромный из них не пробивает первую стену."
        ),
        "author": "Hajime Isayama",
        "cover_image": "https://placehold.co/600x900/3a2a1e/eed7b8?text=Attack+on+Titan",
        "rating": 9.3,
        "genres": ["Action", "Drama", "Mystery", "Shonen"],
        "chapters": [
            {"number": 1.0, "title": "To You, in 2000 Years", "volume": 1, "pages": 11},
            {"number": 2.0, "title": "That Day", "volume": 1, "pages": 9},
            {"number": 3.0, "title": "Night of the Disbanding", "volume": 1, "pages": 10},
        ],
    },
    {
        "title": "Solo Leveling",
        "description": (
            "Сон Джину — самый слабый охотник Кореи — получает уникальную систему, "
            "позволяющую бесконечно повышать уровень."
        ),
        "author": "Chugong",
        "cover_image": "https://placehold.co/600x900/1a1a2e/d6c8ee?text=Solo+Leveling",
        "rating": 9.2,
        "genres": ["Action", "Fantasy", "Adventure", "Manhwa"],
        "chapters": [
            {"number": 1.0, "title": "The Weakest E-rank", "volume": 1, "pages": 10},
            {"number": 2.0, "title": "Double Dungeon", "volume": 1, "pages": 9},
            {"number": 3.0, "title": "Re-Awakening", "volume": 1, "pages": 8},
            {"number": 4.0, "title": "First Quest", "volume": 2, "pages": 9},
        ],
    },
    {
        "title": "Spy x Family",
        "description": (
            "Шпион, наёмная убийца и телепатка-ребёнок создают фальшивую семью "
            "ради сложной операции — и постепенно становятся настоящей."
        ),
        "author": "Tatsuya Endo",
        "cover_image": "https://placehold.co/600x900/3b2a48/f4d7ee?text=Spy+x+Family",
        "rating": 8.9,
        "genres": ["Comedy", "Action", "Slice of Life", "Shonen"],
        "chapters": [
            {"number": 1.0, "title": "Operation Strix", "volume": 1, "pages": 10},
            {"number": 2.0, "title": "Secure a Wife", "volume": 1, "pages": 8},
            {"number": 3.0, "title": "Prepare for Interview", "volume": 1, "pages": 9},
        ],
    },
    {
        "title": "Frieren: Beyond Journey's End",
        "description": (
            "Эльфийка-маг Фрирен пережила своих товарищей по приключению на сотни лет "
            "и теперь учится понимать, что для людей значила их короткая дружба."
        ),
        "author": "Kanehito Yamada",
        "cover_image": "https://placehold.co/600x900/2a3a3a/c8e8e0?text=Frieren",
        "rating": 9.4,
        "genres": ["Fantasy", "Adventure", "Drama", "Slice of Life"],
        "chapters": [
            {"number": 1.0, "title": "The Journey's End", "volume": 1, "pages": 9},
            {"number": 2.0, "title": "The Priest's Lie", "volume": 1, "pages": 8},
            {"number": 3.0, "title": "Killer of Magic", "volume": 1, "pages": 7},
        ],
    },
    {
        "title": "Kaguya-sama: Love is War",
        "description": (
            "Два умнейших старшеклассника влюблены друг в друга, но каждый ждёт, "
            "когда другой первым признается. Война умов и хрупких сердец."
        ),
        "author": "Aka Akasaka",
        "cover_image": "https://placehold.co/600x900/4a2c40/f7d8ec?text=Kaguya-sama",
        "rating": 8.8,
        "genres": ["Romance", "Comedy", "School", "Seinen"],
        "chapters": [
            {"number": 1.0, "title": "I Will Make You Confess", "volume": 1, "pages": 8},
            {"number": 2.0, "title": "Kaguya Wants to Be Stopped", "volume": 1, "pages": 7},
            {"number": 3.0, "title": "Kaguya Wants to Get a Reply", "volume": 1, "pages": 8},
        ],
    },
    {
        "title": "Tower of God",
        "description": (
            "Мальчик по имени Двадцать пятый Бам входит в Башню, чтобы найти "
            "единственного дорогого ему человека — Рашель."
        ),
        "author": "SIU",
        "cover_image": "https://placehold.co/600x900/1c2c4a/c8d8ee?text=Tower+of+God",
        "rating": 9.0,
        "genres": ["Action", "Adventure", "Fantasy", "Manhwa"],
        "chapters": [
            {"number": 1.0, "title": "Headon's Floor", "volume": 1, "pages": 11},
            {"number": 2.0, "title": "Ball", "volume": 1, "pages": 9},
            {"number": 3.0, "title": "The Crown's Test", "volume": 1, "pages": 10},
        ],
    },
    {
        "title": "Oyasumi Punpun",
        "description": (
            "История взросления мальчика-птицы Пунпуна — депрессивная, болезненная "
            "и пронзительно правдивая хроника одной обычной жизни."
        ),
        "author": "Inio Asano",
        "cover_image": "https://placehold.co/600x900/2c2c2c/e8e8e8?text=Punpun",
        "rating": 9.1,
        "genres": ["Drama", "Slice of Life", "Psychological", "Seinen"],
        "chapters": [
            {"number": 1.0, "title": "Childhood", "volume": 1, "pages": 8},
            {"number": 2.0, "title": "First Love", "volume": 1, "pages": 7},
            {"number": 3.0, "title": "Growing Up", "volume": 1, "pages": 8},
        ],
    },
]


def slugify(value: str) -> str:
    return (
        value.lower()
        .replace(" ", "-")
        .replace("&", "and")
        .replace("/", "-")
        .replace(":", "")
        .replace("'", "")
        .replace(",", "")
        .replace(".", "")
    )


async def get_or_create_genres(session, names: list[str]) -> list[Genre]:
    if not names:
        return []

    result = await session.scalars(select(Genre).where(Genre.name.in_(names)))
    existing = list(result.all())
    by_name = {genre.name: genre for genre in existing}

    resolved: list[Genre] = []
    for name in names:
        genre = by_name.get(name)
        if genre is None:
            genre = Genre(name=name)
            session.add(genre)
            by_name[name] = genre
        resolved.append(genre)
    return resolved


async def seed_users(session) -> None:
    for payload in SEED_USERS:
        existing = await session.scalar(select(User).where(User.username == payload["username"]))
        if existing is not None:
            continue
        session.add(
            User(
                username=payload["username"],
                email=payload["email"],
                password_hash=hash_password(payload["password"]),
                role=payload["role"],
            )
        )
    await session.flush()


async def seed_manga(session) -> None:
    for manga_payload in SEED_DATA:
        existing = await session.scalar(
            select(Manga)
            .options(selectinload(Manga.chapters), selectinload(Manga.genres))
            .where(Manga.title == manga_payload["title"])
        )
        if existing is not None:
            await session.delete(existing)
            await session.flush()

        genres = await get_or_create_genres(session, manga_payload["genres"])
        manga = Manga(
            title=manga_payload["title"],
            description=manga_payload["description"],
            author=manga_payload["author"],
            cover_image=manga_payload["cover_image"],
            rating=manga_payload["rating"],
        )
        manga.genres = genres
        session.add(manga)
        await session.flush()

        for chapter_payload in manga_payload["chapters"]:
            chapter = Chapter(
                manga_id=manga.id,
                number=chapter_payload["number"],
                title=chapter_payload["title"],
                volume=chapter_payload["volume"],
                pages_count=chapter_payload["pages"],
            )
            session.add(chapter)
            await session.flush()

            slug = slugify(manga.title)
            for page_number in range(1, chapter_payload["pages"] + 1):
                session.add(
                    Page(
                        chapter_id=chapter.id,
                        page_number=page_number,
                        image_path=f"/demo/page-image/{slug}/{int(chapter.number)}/{page_number}.svg",
                        width=960,
                        height=1400,
                    )
                )


async def seed() -> None:
    await db_session.init_db()
    session_factory = db_session.AsyncSessionLocal
    if session_factory is None:
        raise RuntimeError("Database session factory was not initialized")

    async with session_factory() as session:
        await seed_users(session)
        await seed_manga(session)
        await session.commit()

    await db_session.close_db()
    print(f"Seed completed: {len(SEED_USERS)} users, {len(SEED_DATA)} manga")


if __name__ == "__main__":
    asyncio.run(seed())
