import os
from datetime import datetime, timedelta
from peewee import SqliteDatabase, Model, BigIntegerField, CharField, TextField, BooleanField, DateTimeField, ForeignKeyField

db_path = os.getenv("DB_PATH", "gitgram.db")
db = SqliteDatabase(db_path)

class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel):
    telegram_id = BigIntegerField(unique=True, index=True)
    created_at = DateTimeField(default=datetime.utcnow)

class GitHubAccount(BaseModel):
    user_id = BigIntegerField(index=True)
    alias = CharField(max_length=50)
    token = CharField(max_length=255)
    username = CharField(max_length=100)
    is_active = BooleanField(default=True)

class AIConfig(BaseModel):
    user_id = BigIntegerField(index=True)
    provider = CharField(max_length=20) # 'groq', 'gemini', 'openai'
    api_key = CharField(max_length=255)

class ChatHistory(BaseModel):
    user_id = BigIntegerField(index=True)
    role = CharField(max_length=20) # 'user', 'assistant', 'system'
    content = TextField()
    created_at = DateTimeField(default=datetime.utcnow, index=True)

def init_db():
    db.connect()
    db.create_tables([User, GitHubAccount, AIConfig, ChatHistory], safe=True)
    db.close()

def cleanup_old_chat_history():
    """Elimina mensajes del historial con más de 24 horas de antigüedad para mantener la base ligera."""
    threshold = datetime.utcnow() - timedelta(hours=24)
    db.connect()
    try:
        query = ChatHistory.delete().where(ChatHistory.created_at < threshold)
        deleted_count = query.execute()
        return deleted_count
    finally:
        db.close()
