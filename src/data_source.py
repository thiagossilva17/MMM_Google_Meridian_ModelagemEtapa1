"""Fonte oficial fixada; qualquer alteração de bytes interrompe a leitura."""
from pathlib import Path
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '02111531f8661373aa7b6ba31c316c67d72d1dd2'
URL = f'https://raw.githubusercontent.com/google/meridian/{COMMIT}/meridian/data/simulated_data/csv/geo_all_channels.csv'
SHA256 = 'd9ee016f7cd21f5c90b50da10a794af91a372b69f881d3caa266edd41fdafbf6'
BLOB = '855e25fe5f76cc895d458f456f7a1d45ba5d87b8'
SIZE = 966498


def verify_bytes(content):
    """Valida SHA-256, tamanho e identidade do blob oficial, sem normalizar CSV."""
    digest = hashlib.sha256(content).hexdigest()
    blob = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
    if digest != SHA256 or len(content) != SIZE or blob != BLOB:
        raise ValueError('BLOCKED: conteúdo diferente do CSV oficial fixado.')
    return digest


def obtain(path=None):
    """Usa a cópia imutável versionada; download apenas se ela estiver ausente."""
    path = Path(path) if path else ROOT / 'data/raw/geo_all_channels.csv'
    if path.exists():
        verify_bytes(path.read_bytes())
    else:
        with urllib.request.urlopen(URL, timeout=60) as response:
            content = response.read()
        verify_bytes(content)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return path


def verify_provenance():
    meta = json.loads((ROOT / 'data/metadata/provenance.json').read_text())
    if (meta['sha256'], meta['bytes'], meta['git_blob_sha'], meta['source_url']) != (SHA256, SIZE, BLOB, URL):
        raise ValueError('BLOCKED: metadados divergentes do contrato fixado.')
    return verify_bytes(obtain().read_bytes())
