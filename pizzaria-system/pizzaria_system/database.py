from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pizzaria_system.settings import Settings

settings = Settings()
engine = create_engine(settings.DATABASE_URL)


def get_session():
    yield Session(engine)
