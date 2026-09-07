import asyncio

import asyncpg


async def create_test_db():
    sys_conn = await asyncpg.connect(
        user="postgres", password="postgres", database="postgres", host="localhost"
    )
    try:
        exists = await sys_conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'test_hirefolio'"
        )
        if not exists:
            print("Creating database test_hirefolio...")
            await sys_conn.execute("CREATE DATABASE test_hirefolio")
        else:
            print("Database test_hirefolio already exists.")
    finally:
        await sys_conn.close()

    # Connect to the new database to enable extensions
    print("Enabling vector extension...")
    conn = await asyncpg.connect(
        user="postgres",
        password="postgres",
        database="test_hirefolio",
        host="localhost",
    )
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("Extension vector enabled.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(create_test_db())
