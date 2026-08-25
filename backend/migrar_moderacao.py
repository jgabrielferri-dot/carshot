"""
Adiciona as colunas de moderação na tabela photos.

As fotos que já estão no site entram como 'approved', para que nada
desapareça no momento em que a moderação passa a valer. Só as novas
começam como 'pending'.

Uso:  python migrar_moderacao.py
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    print("Erro: DATABASE_URL não encontrada no .env")
    sys.exit(1)

import psycopg2

db = psycopg2.connect(DATABASE_URL)
cur = db.cursor()


def coluna_existe(nome: str) -> bool:
    cur.execute(
        "select 1 from information_schema.columns "
        "where table_name='photos' and column_name=%s",
        (nome,),
    )
    return cur.fetchone() is not None


novas = 0

if not coluna_existe("moderation_status"):
    # default 'approved' preenche as linhas existentes de uma vez
    cur.execute(
        "alter table photos add column moderation_status varchar "
        "not null default 'approved'"
    )
    # daqui em diante o padrão do banco passa a ser 'pending'
    cur.execute("alter table photos alter column moderation_status set default 'pending'")
    cur.execute("create index if not exists ix_photos_moderation_status on photos (moderation_status)")
    print("  + moderation_status criada (fotos existentes marcadas como 'approved')")
    novas += 1
else:
    print("  = moderation_status já existe")

for nome, tipo in (("moderation_note", "text"), ("moderated_at", "timestamp")):
    if not coluna_existe(nome):
        cur.execute(f"alter table photos add column {nome} {tipo}")
        print(f"  + {nome} criada")
        novas += 1
    else:
        print(f"  = {nome} já existe")

db.commit()

cur.execute("select moderation_status, count(*) from photos group by moderation_status order by 1")
print("\nSituação atual das fotos:")
for status, qtd in cur.fetchall():
    print(f"  {status:10} {qtd}")

db.close()
print(f"\nConcluído — {novas} coluna(s) adicionada(s).")
