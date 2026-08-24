"""
Ferramenta de administrador da SpotGrid.

Localiza uma foto e baixa o arquivo ORIGINAL (sem marca d'água) para enviar
ao comprador que entrou em contato pelo WhatsApp.

Uso:
    python buscar_foto.py 12              # pelo ID (o número do link do WhatsApp)
    python buscar_foto.py api-12          # aceita o formato do link também
    python buscar_foto.py --placa AWNN64  # pela placa
    python buscar_foto.py --busca golf    # por texto no título/carro/marca/modelo

O link que o comprador manda é assim:
    https://jgabrielferri-dot.github.io/carshot/#post/api-12
                                                        ^^ este é o ID

Os arquivos baixados vão para a pasta ./downloads/
"""

import argparse
import os
import re
import sys
import urllib.request

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    print("Erro: DATABASE_URL não encontrada no .env")
    sys.exit(1)

try:
    import psycopg2
except ImportError:
    print("Erro: falta a dependência psycopg2.\nRode: pip install psycopg2-binary python-dotenv")
    sys.exit(1)

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")

CAMPOS = """
    p.id, p.title, p.car, p.brand, p.model, p.color, p.plate,
    p.location, p.event, p.event_date, p.event_time,
    p.price, p.is_for_sale, p.is_public, p.resolution,
    p.original_path, p.created_at,
    u.name, u.email, u.phone
"""

BASE_SQL = f"SELECT {CAMPOS} FROM photos p LEFT JOIN users u ON u.id = p.photographer_id"


def _slug(texto: str) -> str:
    limpo = re.sub(r"[^A-Za-z0-9]+", "-", (texto or "")).strip("-").lower()
    return limpo or "foto"


def mostrar(foto: tuple) -> None:
    (pid, title, car, brand, model, color, plate, location, event, event_date,
     event_time, price, is_for_sale, is_public, resolution, original_path,
     created_at, ph_name, ph_email, ph_phone) = foto

    print(f"\n{'=' * 58}")
    print(f"  FOTO #{pid}  —  {title or car or 'sem título'}")
    print(f"{'=' * 58}")
    print(f"  Veículo     : {' · '.join(x for x in [brand, model, color] if x) or '—'}")
    print(f"  Placa       : {plate or '—'}")
    print(f"  Local       : {location or '—'}")
    print(f"  Evento      : {event or '—'}")
    print(f"  Data / hora : {(event_date or '—')} {event_time or ''}".rstrip())
    print(f"  Resolução   : {resolution or '—'}")
    print(f"  Preço       : {('R$ ' + str(price)) if price else '—'}"
          f"   ({'à venda' if is_for_sale else 'não vendável'},"
          f" {'público' if is_public else 'privado'})")
    print(f"  Publicada em: {created_at}")
    print(f"  ─ Fotógrafo ─")
    print(f"    Nome      : {ph_name or '—'}")
    print(f"    E-mail    : {ph_email or '—'}")
    print(f"    WhatsApp  : {ph_phone or '—'}")
    print(f"  Link no site: https://jgabrielferri-dot.github.io/carshot/#post/api-{pid}")
    print(f"  Original    : {original_path or '(indisponível)'}")


def baixar(foto: tuple) -> None:
    pid, title, car, brand, model = foto[0], foto[1], foto[2], foto[3], foto[4]
    original_path = foto[15]

    if not original_path:
        print("\n  !! Esta foto não tem arquivo original registrado.")
        return

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    nome = f"spotgrid-{pid}-{_slug(title or car or f'{brand} {model}')}.jpg"
    destino = os.path.join(DOWNLOAD_DIR, nome)

    print(f"\n  Baixando original...", end=" ", flush=True)
    try:
        req = urllib.request.Request(
            original_path, headers={"User-Agent": "SpotGrid-Admin/1.0"}
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            dados = r.read()
        with open(destino, "wb") as f:
            f.write(dados)
        print(f"OK ({len(dados) // 1024} KB)")
        print(f"  Salvo em: {destino}")
    except Exception as e:
        print(f"ERRO: {e}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Localiza e baixa o original de uma foto da SpotGrid.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("id", nargs="?", help="ID da foto (aceita 12 ou api-12)")
    ap.add_argument("--placa", help="Busca pela placa do veículo")
    ap.add_argument("--busca", help="Busca por texto no título, carro, marca ou modelo")
    ap.add_argument("--sem-download", action="store_true",
                    help="Apenas mostra os dados, sem baixar o arquivo")
    args = ap.parse_args()

    if not any([args.id, args.placa, args.busca]):
        ap.print_help()
        sys.exit(0)

    db = psycopg2.connect(DATABASE_URL)
    cur = db.cursor()

    if args.id:
        m = re.search(r"(\d+)", str(args.id))
        if not m:
            print(f"ID inválido: {args.id}")
            sys.exit(1)
        cur.execute(f"{BASE_SQL} WHERE p.id = %s", (int(m.group(1)),))
    elif args.placa:
        cur.execute(
            f"{BASE_SQL} WHERE UPPER(REPLACE(p.plate,'-','')) LIKE %s ORDER BY p.id",
            (f"%{args.placa.upper().replace('-', '')}%",),
        )
    else:
        termo = f"%{args.busca}%"
        cur.execute(
            f"{BASE_SQL} WHERE p.title ILIKE %s OR p.car ILIKE %s "
            f"OR p.brand ILIKE %s OR p.model ILIKE %s ORDER BY p.id",
            (termo, termo, termo, termo),
        )

    fotos = cur.fetchall()
    cur.close()
    db.close()

    if not fotos:
        print("Nenhuma foto encontrada.")
        sys.exit(1)

    print(f"\n{len(fotos)} foto(s) encontrada(s).")
    for foto in fotos:
        mostrar(foto)
        if not args.sem_download:
            baixar(foto)
    print()


if __name__ == "__main__":
    main()
