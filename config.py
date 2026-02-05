import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Primary Database (Write)
    DB_USER = os.getenv('POSTGRES_USER')
    DB_PASS = os.getenv('POSTGRES_PASSWORD')
    DB_HOST = os.getenv('POSTGRES_HOST')
    DB_PORT = os.getenv('POSTGRES_PORT')
    DB_NAME = os.getenv('POSTGRES_DB')
    
    # FIX 1: Tambahkan ?sslmode=require di akhir connection string
    SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"

    # Replica Database (Read)
    REP_USER = os.getenv('POSTGRES_USER_REPLICA') or DB_USER
    REP_PASS = os.getenv('POSTGRES_PASSWORD_REPLICA') or DB_PASS
    REP_HOST = os.getenv('POSTGRES_HOST_REPLICA') or DB_HOST
    REP_PORT = os.getenv('POSTGRES_PORT_REPLICA') or DB_PORT
    REP_NAME = os.getenv('POSTGRES_DB_REPLICA') or DB_NAME

    # FIX 2: Tambahkan juga di Replica
    SQLALCHEMY_BINDS = {
        'replica': f"postgresql://{REP_USER}:{REP_PASS}@{REP_HOST}:{REP_PORT}/{REP_NAME}?sslmode=require"
    }
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key_for_poc')
