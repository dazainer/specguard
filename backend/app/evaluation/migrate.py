"""Apply evaluation DB migrations explicitly; never run schema creation in API startup."""
from app.config import get_settings
from app.evaluation.store import Store

if __name__ == '__main__':
    Store(get_settings().evaluation_db).migrate()
    print('Evaluation database migrated.')
