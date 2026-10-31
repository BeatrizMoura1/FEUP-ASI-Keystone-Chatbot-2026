import psycopg
from psycopg.rows import dict_row

from app.config import settings


def get_connection() -> psycopg.Connection:
    """Open a PostgreSQL connection that returns rows as dicts.

    Use it as `with get_connection() as connection:`; the transaction is committed and the connection closed
    when the block ends (rolled back if it raises).

    Returns
    -------
    psycopg.Connection
        Connection to DATABASE_URL.
    """
    return psycopg.connect(settings.database_url, row_factory=dict_row)
