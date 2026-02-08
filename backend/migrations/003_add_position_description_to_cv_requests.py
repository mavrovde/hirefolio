from sqlalchemy import text

def upgrade(conn):
    conn.execute(text("ALTER TABLE cv_requests ADD COLUMN position_description VARCHAR(1000)"))

def downgrade(conn):
    conn.execute(text("ALTER TABLE cv_requests DROP COLUMN position_description"))
