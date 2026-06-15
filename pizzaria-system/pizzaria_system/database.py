from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from pizzaria_system.settings import Settings

settings = Settings()
engine = create_engine(settings.DATABASE_URL)

# Cria uma fábrica de sessões, que é uma prática recomendada.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()