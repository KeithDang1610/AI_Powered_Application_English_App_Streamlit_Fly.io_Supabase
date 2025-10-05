import os
# from supabase import create_client, Client
# from dotenv import load_dotenv
import psycopg2
# from psycopg2.extras import RealDictCursor

# load_dotenv()

# URL = os.getenv("URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# supabase: Client = create_client(URL, SUPABASE_KEY)
# --- Supabase Postgres config ---
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_PORT = os.environ.get("DB_PORT", 6543)

def get_pg_conn():
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT,
        sslmode="require",
    )
    return conn