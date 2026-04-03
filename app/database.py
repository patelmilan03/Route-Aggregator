from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# SQLite is great for local development. The 'aiosqlite' driver makes it async.
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./routes.db"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

async def get_db():
    """Dependency to inject the database session into our FastAPI routes."""
    async with SessionLocal() as session:
        yield session