import os
import urllib.parse  # Tambahkan ini untuk handle karakter spesial di password
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 1. Ambil env vars
    DB_USER = os.getenv('POSTGRES_USER')
    DB_PASS = os.getenv('POSTGRES_PASSWORD')
    DB_HOST = os.getenv('POSTGRES_HOST')
    DB_PORT = os.getenv('POSTGRES_PORT')
    DB_NAME = os.getenv('POSTGRES_DB')

    # 2. ENCODE PASSWORD (PENTING!)
    # Ini mencegah error auth jika password mengandung karakter seperti '@', ':', dll.
    _encoded_pass = urllib.parse.quote_plus(DB_PASS) if DB_PASS else ""

    # 3. Definisikan SSL Mode
    # Gunakan 'require' untuk Cloud SQL Private IP agar enkripsi aktif
    ssl_args = "?sslmode=require"

    # Primary Database (Write)
    # Perhatikan penambahan {ssl_args} di akhir
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USER}:{_encoded_pass}@{DB_HOST}:{DB_PORT}/{DB_NAME}{ssl_args}"
    )

    # Replica Database (Read)
    REP_USER = os.getenv('POSTGRES_USER_REPLICA') or DB_USER
    REP_PASS = os.getenv('POSTGRES_PASSWORD_REPLICA') or DB_PASS
    REP_HOST = os.getenv('POSTGRES_HOST_REPLICA') or DB_HOST
    REP_PORT = os.getenv('POSTGRES_PORT_REPLICA') or DB_PORT
    REP_NAME = os.getenv('POSTGRES_DB_REPLICA') or DB_NAME

    # Encode password replica juga
    _encoded_rep_pass = urllib.parse.quote_plus(REP_PASS) if REP_PASS else ""

    SQLALCHEMY_BINDS = {
        'replica': f"postgresql://{REP_USER}:{_encoded_rep_pass}@{REP_HOST}:{REP_PORT}/{REP_NAME}{ssl_args}"
    }
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key_for_poc')