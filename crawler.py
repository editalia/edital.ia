import re
import time
import logging
import urllib3
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from state import (
    carregar_crawler_state,
    salvar_crawler_state,
    carregar_editais,
    salvar_editais,
)

# O portal IFBA usa CA institucional não reconhecida pelo Python.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

BASE_URL = "https://portal.ifba.edu.br"
SEED_URL = f"{BASE_URL}/prpgi/editais/"
OUTPUT_DIR = Path("editais_baixados")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
}

PROGRAMAS_VALIDOS = re.compile(r"\bPIBIC\b|\bPIBITI\b|\bPIBID\b", re.IGNORECASE)
_SLUG_INDICE = re.compile(r"edital-e-retificacoes$")


def _get_page(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, verify=False)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        log.warning(f"Falha ao acessar {url}: {e}")
        return None


def _url_absoluta(href: str) -> str:
    return href if href.startswith("http") else BASE_URL + href


def _get_anos(soup: BeautifulSoup) -> list[str]:
    urls = []
    for li in soup.select("li.navTreeItem"):
        a = li.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        if re.search(r"/editais/\d{4}/?$", href):
            urls.append(_url_absoluta(href))
    return urls


def _get_editais_do_ano(soup: BeautifulSoup) -> list[dict]:
    editais = []
    for a in soup.select("a.summary.url"):
        href = a.get("href", "")
        titulo = a.get_text(strip=True)
        desc_tag = a.find_next("span", class_="description")
        descricao = desc_tag.get_text(strip=True) if desc_tag else ""

        if PROGRAMAS_VALIDOS.search(descricao) or PROGRAMAS_VALIDOS.search(titulo):
            editais.append({
                "titulo": titulo,
                "descricao": descricao,
                "url": _url_absoluta(href),
            })
    return editais


def _get_link_retificacao(soup: BeautifulSoup) -> str | None:
    for a in soup.find_all("a", href=True):
        href = a["href"]
        texto = a.get_text(strip=True)
        if "edital-e-retificacoes" not in href:
            continue
        if "Saiba mais" in texto:
            continue
        if _SLUG_INDICE.search(href):
            continue
        return _url_absoluta(href)
    return None


def _baixar_pdf(url_retificacao: str, destino: Path) -> bool:
    if destino.exists():
        log.info(f"  PDF ja existe: {destino.name}")
        return True

    tentativas = [
        url_retificacao,
        url_retificacao + "/at_download/file",
        url_retificacao + "/download",
    ]
    for url_tentativa in tentativas:
        try:
            resp = requests.get(
                url_tentativa, headers=HEADERS, timeout=60, stream=True, verify=False
            )
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")
            if "pdf" in content_type.lower():
                with open(destino, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                log.info(f"  PDF baixado: {destino.name}")
                return True
        except Exception as e:
            log.debug(f"  Tentativa falhou ({url_tentativa}): {e}")

    log.error(f"  Nao foi possivel baixar o PDF de: {url_retificacao}")
    return False


def _nome_arquivo(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    return slug + ".pdf"


def executar_crawler(anos_limite: int = 1) -> dict:
    """Roda o crawler. Skip de URLs já visitadas via state/urls_visitadas.json.
    Cada edital descoberto é registrado em state/editais.json com URL original e do PDF.
    Retorna dict com {novos, total_visitados, ja_vistos}.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    log.info("=== Iniciando crawler de editais IFBA ===")

    crawler_state = carregar_crawler_state()
    editais_state = carregar_editais()
    urls_vistas = set(crawler_state.get("urls_visitadas", []))

    novos = 0
    ja_vistos = 0
    total = 0

    soup_seed = _get_page(SEED_URL)
    if not soup_seed:
        log.error("Nao foi possivel acessar a pagina inicial de editais.")
        return {"novos": 0, "total_visitados": 0, "ja_vistos": 0}

    urls_anos = _get_anos(soup_seed)[:anos_limite]
    log.info(f"Anos encontrados: {[u.split('/')[-1] for u in urls_anos]}")

    for url_ano in urls_anos:
        ano = url_ano.split("/")[-1]
        log.info(f"\n--- Processando {ano} ---")

        soup_ano = _get_page(url_ano)
        if not soup_ano:
            continue

        editais_listados = _get_editais_do_ano(soup_ano)
        log.info(f"Editais PIBIC/PIBITI/PIBID na listagem: {len(editais_listados)}")

        for edital in editais_listados:
            total += 1

            if edital["url"] in urls_vistas:
                ja_vistos += 1
                log.info(f"  [SKIP] Ja visitado: {edital['titulo']}")
                continue

            log.info(f"\n  {edital['titulo']} | {edital['descricao']}")

            soup_edital = _get_page(edital["url"])
            if not soup_edital:
                continue

            link_retificacao = _get_link_retificacao(soup_edital)
            if not link_retificacao:
                log.warning("  Nenhum link de retificacao encontrado")
                continue

            nome = _nome_arquivo(link_retificacao)
            destino = OUTPUT_DIR / nome

            if _baixar_pdf(link_retificacao, destino):
                novos += 1
                urls_vistas.add(edital["url"])

                # Registra entrada inicial em editais.json (programa/titulo amigavel
                # virão depois, no validador).
                key = nome + ".md"
                if key not in editais_state:
                    editais_state[key] = {}
                editais_state[key].update({
                    "arquivo_pdf": nome,
                    "arquivo_md": key,
                    "url_original": edital["url"],
                    "url_pdf": link_retificacao,
                    "titulo_listagem": edital["titulo"],
                    "descricao_listagem": edital["descricao"],
                    "ano_listagem": ano,
                })

            time.sleep(1)  # cortesia com o servidor

    crawler_state["urls_visitadas"] = sorted(urls_vistas)
    salvar_crawler_state(crawler_state)
    salvar_editais(editais_state)

    log.info(
        f"\n=== Crawler finalizado. {novos} novos PDFs, "
        f"{ja_vistos} já vistos, {total} totais ==="
    )
    return {"novos": novos, "total_visitados": total, "ja_vistos": ja_vistos}


if __name__ == "__main__":
    executar_crawler(anos_limite=1)
