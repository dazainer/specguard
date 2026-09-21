from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from app.config import get_settings

path = context.config.attributes.get('database_path', get_settings().evaluation_db)
engine = create_engine('sqlite:///' + str(path.resolve()), poolclass=NullPool)
with engine.connect() as connection:
    context.configure(connection=connection, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
