import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()


def get_db_connection():
    """
    Estabelece uma conexão com o banco de dados Neon.
    Retorna o objeto de conexão.
    """
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("A variável DATABASE_URL não foi encontrada no arquivo .env")

    try:
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None


def init_db():
    """
    Cria a tabela historico_clima caso ela ainda não exista.
    Útil para a primeira execução do projeto.
    """
    commands = (
        """
        CREATE TABLE IF NOT EXISTS historico_clima (
            id SERIAL PRIMARY KEY,
            cidade VARCHAR(255) NOT NULL,
            data TEXT NOT NULL,
            umidade FLOAT,
            vento FLOAT,
            precipitacao FLOAT,
            temp_min FLOAT,
            temp_max FLOAT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )
    conn = None
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            for command in commands:
                cur.execute(command)
            cur.close()
            conn.commit()
            print("Banco de dados inicializado com sucesso!")
    except Exception as e:
        print(f"Erro ao inicializar o banco: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    # Se você rodar este arquivo diretamente (python database.py),
    # ele criará a tabela para você no Neon.
    init_db()
