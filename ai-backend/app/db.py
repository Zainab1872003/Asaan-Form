

# # AI-BACKEND/app/db.py
# from motor.motor_asyncio import AsyncIOMotorClient
# import gridfs
# from app.config import settings

# class Database:
#     client = None
#     db = None
#     fs = None

# db = Database()

# async def connect_to_mongo():
#     """Connect to MongoDB and initialize GridFS"""
#     try:
#         db.client = AsyncIOMotorClient(settings.MONGODB_URL)
#         db.db = db.client[settings.DATABASE_NAME]
        
#         db.fs = gridfs.GridFSBucket(db.db, bucket_name="fs")
        
#         print("✅ Connected to MongoDB + GridFS successfully")
#         print(f"   Database: {settings.DATABASE_NAME} | Bucket: fs")
        
#     except Exception as e:
#         print(f"❌ Failed to connect to MongoDB: {e}")
#         raise

# async def close_mongo_connection():
#     if db.client:
#         db.client.close()
#         print("✅ MongoDB connection closed")

# def get_gridfs():
#     """Get GridFS - safe version"""
#     if db.fs is None:
#         raise RuntimeError("GridFS not initialized. Make sure connect_to_mongo() was called during startup.")
#     return db.fs


"""
app/db.py - Fixed for Motor AsyncIO + GridFS
"""

from motor.motor_asyncio import AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from app.config import settings

class Database:
    client = None
    db = None
    fs = None  # Async GridFS

db = Database()

async def connect_to_mongo():
    """Connect to MongoDB and initialize Async GridFS"""
    try:
        db.client = AsyncIOMotorClient(settings.MONGODB_URL)
        db.db = db.client[settings.DATABASE_NAME]
        
        # Use Async GridFSBucket (important!)
        db.fs = AsyncIOMotorGridFSBucket(db.db, bucket_name="fs")
        
        print("✅ Connected to MongoDB + Async GridFS successfully")
        print(f"   Database: {settings.DATABASE_NAME} | Bucket: fs")
        
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        raise

async def close_mongo_connection():
    """Close MongoDB connection"""
    if db.client:
        db.client.close()
        print("✅ MongoDB connection closed")

def get_gridfs():
    """Get Async GridFS"""
    if db.fs is None:
        raise RuntimeError("GridFS not initialized. Make sure connect_to_mongo() was called during startup.")
    return db.fs