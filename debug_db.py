import asyncio
import aiosqlite
import os

DB_PATH = "campus_talent.db"

async def test_db():
    print("--- Running DB Diagnostics ---")
    async with aiosqlite.connect(DB_PATH) as db:
        # Check schema
        cursor = await db.execute("PRAGMA table_info(profile_views)")
        columns = await cursor.fetchall()
        print(f"Table 'profile_views' columns: {columns}")
        
        # Try a test insert
        try:
            viewer_id = 12345
            target_id = 67890
            await db.execute("INSERT INTO profile_views (viewer_id, target_user_id) VALUES (?, ?)", (viewer_id, target_id))
            await db.commit()
            print("Successfully inserted a test view.")
        except Exception as e:
            print(f"Insert failed: {e}")
            
        # Check count
        async with db.execute("SELECT COUNT(*) FROM profile_views WHERE target_user_id = 67890") as cursor:
            row = await cursor.fetchone()
            print(f"View count for 67890: {row[0]}")
            
        # Clean up
        await db.execute("DELETE FROM profile_views WHERE viewer_id = 12345")
        await db.commit()
        print("Cleaned up test data.")

if __name__ == "__main__":
    asyncio.run(test_db())
