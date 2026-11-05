from pathlib import Path

ENTRYPOINT = Path(__file__).parents[1] / 'internum' / 'infra' / 'entrypoint.sh'


def test_entrypoint_runs_seed_as_module():
    """O seed precisa rodar como módulo dentro da imagem.

    A imagem instala as dependências com ``poetry install --no-root``, então
    ``internum`` não fica em ``site-packages``. Executar o arquivo por caminho
    coloca apenas ``internum/scripts`` no ``sys.path`` e quebra o boot com
    ``ModuleNotFoundError``. Como módulo, o ``cwd`` (``/app``) entra no path.
    """
    script = ENTRYPOINT.read_text()

    assert 'python -m internum.scripts.seed_oficial' in script
    assert 'python internum/scripts/seed_oficial.py' not in script
