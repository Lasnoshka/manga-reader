from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """Базовый класс для всех SQLAlchemy моделей"""

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()
