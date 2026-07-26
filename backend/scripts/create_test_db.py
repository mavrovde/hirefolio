import asyncio

import asyncpg


async def create_test_db():
    sys_conn = await asyncpg.connect(
        user="postgres", password="postgres", database="postgres", host="localhost"
    )
    try:
        exists = await sys_conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'mavrov_test'"
        )
        if not exists:
            print("Creating database mavrov_test...")
            await sys_conn.execute("CREATE DATABASE mavrov_test")
        else:
            print("Database mavrov_test already exists.")
    finally:
        await sys_conn.close()

    # Connect to the new database to enable extensions
    print("Enabling vector extension...")
    conn = await asyncpg.connect(
        user="postgres", password="postgres", database="mavrov_test", host="localhost"
    )
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("Extension vector enabled.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(create_test_db())
