import aiosqlite
import os
import asyncio
from datetime import datetime
import json

DB_PATH = "campus_talent.db"

class Database:
    _connection: aiosqlite.Connection = None

    @classmethod
    async def get_db(cls) -> aiosqlite.Connection:
        if cls._connection is None:
            cls._connection = await aiosqlite.connect(DB_PATH)
            # Enable WAL mode for high concurrency
            await cls._connection.execute("PRAGMA journal_mode=WAL;")
            await cls._connection.execute("PRAGMA synchronous=NORMAL;")
        return cls._connection

    @classmethod
    async def close(cls):
        if cls._connection:
            await cls._connection.close()
            cls._connection = None

async def init_db():
    db = await Database.get_db()
    
    # Users table
    await db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            fake_name TEXT,
            fake_id TEXT UNIQUE,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Posts table - ensuring schema
    await db.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            content_type TEXT,
            is_anonymous BOOLEAN,
            photo_file_id TEXT,
            voice_file_id TEXT,
            caption TEXT,
            status TEXT DEFAULT 'pending',
            message_id INTEGER,
            comments_enabled BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Reactions table
    await db.execute('''
        CREATE TABLE IF NOT EXISTS post_reactions (
            reaction_id INTEGER PRIMARY KEY,
            post_id INTEGER,
            user_id INTEGER,
            reaction TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(post_id, user_id),
            FOREIGN KEY(post_id) REFERENCES posts(post_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')

    # ID Requests table
    await db.execute('''
        CREATE TABLE IF NOT EXISTS id_requests (
            request_id INTEGER PRIMARY KEY,
            requester_id INTEGER,
            target_user_id INTEGER,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(requester_id, target_user_id)
        )
    ''')

    # Comments table
    await db.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            comment_id INTEGER PRIMARY KEY,
            post_id INTEGER,
            user_id INTEGER,
            content TEXT,
            parent_id INTEGER DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(post_id) REFERENCES posts(post_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')

    # Reports table
    await db.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY,
            post_id INTEGER,
            reporter_id INTEGER,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Banned Words table
    await db.execute('''
        CREATE TABLE IF NOT EXISTS banned_words (
            word_id INTEGER PRIMARY KEY,
            word TEXT UNIQUE
        )
    ''')

    # User Badges table
    await db.execute('''
        CREATE TABLE IF NOT EXISTS user_badges (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            badge_key TEXT,
            awarded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, badge_key)
        )
    ''')

    # Profile Views table
    await db.execute('''
        CREATE TABLE IF NOT EXISTS profile_views (
            view_id INTEGER PRIMARY KEY,
            viewer_id INTEGER,
            target_user_id INTEGER,
            view_date DATE DEFAULT CURRENT_DATE,
            viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(viewer_id, target_user_id, view_date)
        )
    ''')
    
    # Message-Comment Mapping
    await db.execute('''
        CREATE TABLE IF NOT EXISTS message_comment_mapping (
            message_id INTEGER,
            chat_id INTEGER,
            comment_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (message_id, chat_id)
        )
    ''')
    
    # Event Queue
    await db.execute('''
        CREATE TABLE IF NOT EXISTS event_queue (
            event_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            meta TEXT DEFAULT '{}',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            signature TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0
        )
    ''')

    await db.commit()
    print("Database Optimized & Initialized.")

# --- User Management ---
async def add_user(user_id, username, full_name):
    from utils.name_generator import generate_fake_name, generate_fake_id
    db = await Database.get_db()
    
    async with db.execute('SELECT fake_id FROM users WHERE user_id = ?', (user_id,)) as cursor:
        existing = await cursor.fetchone()
        
    if not (existing and existing[0]):
        fake_name = generate_fake_name()
        fake_id = generate_fake_id()
        await db.execute('''
            INSERT OR IGNORE INTO users (user_id, username, full_name, fake_name, fake_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, full_name, fake_name, fake_id))
        await db.execute('UPDATE users SET fake_name=?, fake_id=? WHERE user_id=? AND fake_id IS NULL', (fake_name, fake_id, user_id))
    else:
        await db.execute('UPDATE users SET username=?, full_name=? WHERE user_id=?', (username, full_name, user_id))
        
    await db.commit()

async def get_user_profile(user_id):
    db = await Database.get_db()
    db.row_factory = aiosqlite.Row
    async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
        return await cursor.fetchone()

async def get_user_by_fake_id(fake_id):
    db = await Database.get_db()
    db.row_factory = aiosqlite.Row
    async with db.execute('SELECT * FROM users WHERE fake_id = ?', (fake_id,)) as cursor:
        return await cursor.fetchone()

# --- Post Management ---
async def create_post(user_id, category, content_type, is_anonymous, photo_id, caption, voice_id=None, comments_enabled=True):
    db = await Database.get_db()
    cursor = await db.execute('''
        INSERT INTO posts (user_id, category, content_type, is_anonymous, photo_file_id, caption, voice_file_id, status, comments_enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    ''', (user_id, category, content_type, is_anonymous, photo_id, caption, voice_id, comments_enabled))
    await db.commit()
    return cursor.lastrowid

async def get_post(post_id):
    db = await Database.get_db()
    db.row_factory = aiosqlite.Row
    async with db.execute('''
        SELECT p.*, u.username, u.full_name 
        FROM posts p 
        LEFT JOIN users u ON p.user_id = u.user_id 
        WHERE p.post_id = ?
    ''', (post_id,)) as cursor:
        return await cursor.fetchone()

async def update_post_status(post_id, status, message_id=None):
    db = await Database.get_db()
    if message_id:
        await db.execute('UPDATE posts SET status = ?, message_id = ? WHERE post_id = ?', (status, message_id, post_id))
    else:
        await db.execute('UPDATE posts SET status = ? WHERE post_id = ?', (status, post_id))
    await db.commit()

async def atomic_update_post_status(post_id: int, new_status: str, expected_status: str = 'pending') -> bool:
    """
    Atomic update that prevents race conditions. 
    Returns True if successfully updated, False if status was already changed.
    """
    db = await Database.get_db()
    cursor = await db.execute(
        'UPDATE posts SET status = ? WHERE post_id = ? AND status = ?', 
        (new_status, post_id, expected_status)
    )
    await db.commit()
    return cursor.rowcount > 0

async def check_rate_limit(user_id):
    db = await Database.get_db()
    async with db.execute('''
        SELECT 1 FROM posts 
        WHERE user_id = ? 
        AND created_at > datetime('now', '-5 minutes')
    ''', (user_id,)) as cursor:
        row = await cursor.fetchone()
        return bool(row)

# --- ID Requests ---
async def create_id_request(requester_id, target_user_id):
    db = await Database.get_db()
    try:
        cursor = await db.execute('''
            INSERT INTO id_requests (requester_id, target_user_id, status)
            VALUES (?, ?, 'pending')
        ''', (requester_id, target_user_id))
        await db.commit()
        return cursor.lastrowid
    except:
        return None

async def get_id_request(request_id):
    db = await Database.get_db()
    db.row_factory = aiosqlite.Row
    async with db.execute('SELECT * FROM id_requests WHERE request_id = ?', (request_id,)) as cursor:
        return await cursor.fetchone()

async def update_id_request_status(request_id, status):
    db = await Database.get_db()
    await db.execute('UPDATE id_requests SET status = ? WHERE request_id = ?', (status, request_id))
    await db.commit()

async def check_existing_request(requester_id, target_user_id):
    db = await Database.get_db()
    db.row_factory = aiosqlite.Row
    async with db.execute('''
        SELECT * FROM id_requests 
        WHERE requester_id = ? AND target_user_id = ?
    ''', (requester_id, target_user_id)) as cursor:
        return await cursor.fetchone()

# --- Reactions ---
async def toggle_reaction(post_id: int, user_id: int, reaction: str):
    db = await Database.get_db()
    cursor = await db.execute('SELECT reaction FROM post_reactions WHERE post_id=? AND user_id=?', (post_id, user_id))
    row = await cursor.fetchone()
    
    if row:
        if row[0] == reaction:
            await db.execute('DELETE FROM post_reactions WHERE post_id=? AND user_id=?', (post_id, user_id))
            result = "removed"
        else:
            await db.execute('UPDATE post_reactions SET reaction=? WHERE post_id=? AND user_id=?', (reaction, post_id, user_id))
            result = "switched"
    else:
        await db.execute('INSERT INTO post_reactions (post_id, user_id, reaction) VALUES (?, ?, ?)', (post_id, user_id, reaction))
        result = "added"
        
    await db.commit()
    return result

async def get_reaction_counts(post_id: int):
    db = await Database.get_db()
    async with db.execute('SELECT reaction, COUNT(*) as count FROM post_reactions WHERE post_id=? GROUP BY reaction', (post_id,)) as cursor:
        rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}

async def get_user_total_reactions(user_id: int):
    db = await Database.get_db()
    async with db.execute('''
        SELECT pr.reaction, COUNT(*) 
        FROM post_reactions pr
        JOIN posts p ON pr.post_id = p.post_id
        WHERE p.user_id = ?
        GROUP BY pr.reaction
    ''', (user_id,)) as cursor:
        rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}

# --- Comments ---
async def add_comment(post_id: int, user_id: int, content: str, parent_id: int = None):
    db = await Database.get_db()
    await db.execute('''
        INSERT INTO comments (post_id, user_id, content, parent_id)
        VALUES (?, ?, ?, ?)
    ''', (post_id, user_id, content, parent_id))
    await db.commit()

async def get_comments(post_id: int, page: int = 1, limit: int = 5):
    db = await Database.get_db()
    db.row_factory = aiosqlite.Row
    offset = (page - 1) * limit
    
    async with db.execute('SELECT COUNT(*) FROM comments WHERE post_id = ?', (post_id,)) as cursor:
        res = await cursor.fetchone()
        total = res[0] if res else 0

    async with db.execute('''
        SELECT c.*, u.fake_name, u.fake_id, u.username, u.full_name
        FROM comments c
        LEFT JOIN users u ON c.user_id = u.user_id
        WHERE c.post_id = ?
        ORDER BY c.created_at ASC
        LIMIT ? OFFSET ?
    ''', (post_id, limit, offset)) as cursor:
        comments = await cursor.fetchall()
    
    return comments, total

async def get_comment_by_id(comment_id: int):
    db = await Database.get_db()
    db.row_factory = aiosqlite.Row
    async with db.execute('''
        SELECT c.*, u.fake_name, u.fake_id
        FROM comments c
        LEFT JOIN users u ON c.user_id = u.user_id
        WHERE c.comment_id = ?
    ''', (comment_id,)) as cursor:
        return await cursor.fetchone()

# --- Message Mapping ---
async def map_message_to_comment(message_id: int, chat_id: int, comment_id: int):
    db = await Database.get_db()
    await db.execute('''
        INSERT OR REPLACE INTO message_comment_mapping (message_id, chat_id, comment_id)
        VALUES (?, ?, ?)
    ''', (message_id, chat_id, comment_id))
    await db.commit()

async def get_comment_id_from_message(message_id: int, chat_id: int):
    db = await Database.get_db()
    async with db.execute('''
        SELECT comment_id FROM message_comment_mapping 
        WHERE message_id = ? AND chat_id = ?
    ''', (message_id, chat_id)) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else None

async def get_comment_count(post_id: int):
    db = await Database.get_db()
    async with db.execute('SELECT COUNT(*) FROM comments WHERE post_id = ?', (post_id,)) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else 0

async def cleanup_mapping_table(days=1):
    """Cleanup old message mappings."""
    db = await Database.get_db()
    await db.execute("DELETE FROM message_comment_mapping WHERE created_at < datetime('now', ?)", (f'-{days} days',))
    await db.commit()

# --- Moderation ---
async def submit_report(post_id: int, reporter_id: int, reason: str):
    db = await Database.get_db()
    await db.execute('''
        INSERT INTO reports (post_id, reporter_id, reason)
        VALUES (?, ?, ?)
    ''', (post_id, reporter_id, reason))
    await db.commit()

async def get_pending_reports():
    db = await Database.get_db()
    db.row_factory = aiosqlite.Row
    async with db.execute('''
        SELECT r.*, p.caption, p.category 
        FROM reports r
        JOIN posts p ON r.post_id = p.post_id
        WHERE r.status = 'pending'
        ORDER BY r.created_at DESC
    ''') as cursor:
        return await cursor.fetchall()

async def resolve_report(report_id: int, status: str):
    db = await Database.get_db()
    await db.execute('UPDATE reports SET status = ? WHERE report_id = ?', (status, report_id))
    await db.commit()

async def add_banned_word(word: str):
    db = await Database.get_db()
    try:
        await db.execute('INSERT INTO banned_words (word) VALUES (?)', (word.lower().strip(),))
        await db.commit()
        return True
    except aiosqlite.IntegrityError:
        return False

async def remove_banned_word(word: str):
    db = await Database.get_db()
    await db.execute('DELETE FROM banned_words WHERE word = ?', (word.lower().strip(),))
    await db.commit()

async def get_banned_words():
    db = await Database.get_db()
    async with db.execute('SELECT word FROM banned_words') as cursor:
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

# --- Gamification ---
BADGES = {
    "first_post": "🌱 First Step",
    "frequent_poster": "✍️ Frequent Contributor", # 5 posts
    "top_creator": "🌟 Top Creator", # 20 posts
    "liked_creator": "🔥 Hot Content", # 10 total reactions
    "star": "⭐ Campus Star", # 50 total reactions
}

async def check_and_award_badges(user_id: int, trigger_event: str = "post"):
    """
    Optimized badge check: only scans if milestone thresholds are hit.
    """
    db = await Database.get_db()
    
    # 1. Post Milestones (1, 5, 20)
    cursor = await db.execute("SELECT COUNT(*) FROM posts WHERE user_id = ? AND status='approved'", (user_id,))
    res = await cursor.fetchone()
    posts = res[0]
    
    new_badges = []
    if posts >= 1: new_badges.append("first_post")
    if posts >= 5: new_badges.append("frequent_poster")
    if posts >= 20: new_badges.append("top_creator")
    
    # 2. Reaction Milestones (10, 50)
    if trigger_event == "reaction":
        all_reactions = await get_user_total_reactions(user_id)
        total = sum(all_reactions.values())
        if total >= 10: new_badges.append("liked_creator")
        if total >= 50: new_badges.append("star")
        
    for badge in new_badges:
        try:
            await db.execute("INSERT OR IGNORE INTO user_badges (user_id, badge_key) VALUES (?, ?)", (user_id, badge))
        except: pass
    await db.commit()

async def get_user_badges(user_id: int):
    db = await Database.get_db()
    async with db.execute("SELECT badge_key FROM user_badges WHERE user_id = ?", (user_id,)) as cursor:
        rows = await cursor.fetchall()
        return [BADGES.get(row[0], row[0]) for row in rows]

# --- Analytics ---
async def get_leaderboard(limit=5):
    db = await Database.get_db()
    db.row_factory = aiosqlite.Row
    async with db.execute('''
        SELECT u.fake_name, u.fake_id, COUNT(*) as total_reactions
        FROM users u
        JOIN posts p ON u.user_id = p.user_id
        JOIN post_reactions pr ON p.post_id = pr.post_id
        GROUP BY u.user_id
        ORDER BY total_reactions DESC
        LIMIT ?
    ''', (limit,)) as cursor:
        return await cursor.fetchall()

async def get_bot_stats():
    db = await Database.get_db()
    stats = {}
    async with db.execute('SELECT COUNT(*) FROM users') as c: stats['total_users'] = (await c.fetchone())[0]
    async with db.execute('SELECT COUNT(*) FROM posts') as c: stats['total_posts'] = (await c.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM posts WHERE date(created_at) = date('now')") as c: stats['posts_today'] = (await c.fetchone())[0]
    return stats

async def get_all_users():
    db = await Database.get_db()
    async with db.execute('SELECT user_id FROM users') as cursor:
        return [row[0] for row in await cursor.fetchall()]

async def record_profile_view(viewer_id: int, target_user_id: int):
    db = await Database.get_db()
    try:
        await db.execute('INSERT INTO profile_views (viewer_id, target_user_id) VALUES (?, ?)', (viewer_id, target_user_id))
        await db.commit()
        return True
    except: return False

async def get_profile_view_count(user_id: int):
    db = await Database.get_db()
    async with db.execute('SELECT COUNT(*) FROM profile_views WHERE target_user_id = ?', (user_id,)) as cursor:
        res = await cursor.fetchone()
        return res[0] if res else 0

async def get_total_posts(user_id: int):
    db = await Database.get_db()
    async with db.execute('SELECT COUNT(*) FROM posts WHERE user_id = ?', (user_id,)) as cursor:
        res = await cursor.fetchone()
        return res[0] if res else 0

