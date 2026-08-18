import io
import tarfile
from pathlib import Path

import pytest

from pra.analisador.pacote import (
    PacoteInvalido,
    escrever_contexto,
    extrair,
    ler_contexto,
)
from pra.modelos import Contexto, Evento, FaixaLinhas


def montar_tar(tmp_path: Path, membros: dict[str, str], nome="codigo.tar.gz") -> Path:
    caminho = tmp_path / nome
    with tarfile.open(caminho, "w:gz") as tf:
        for nome_membro, conteudo in membros.items():
            dados = conteudo.encode()
            info = tarfile.TarInfo(name=nome_membro)
            info.size = len(dados)
            tf.addfile(info, io.BytesIO(dados))
    return caminho


def montar_tar_com_link(tmp_path: Path, nome_link: str, alvo: str) -> Path:
    caminho = tmp_path / "codigo.tar.gz"
    with tarfile.open(caminho, "w:gz") as tf:
        raiz = tarfile.TarInfo(name="raiz")
        raiz.type = tarfile.DIRTYPE
        tf.addfile(raiz)
        link = tarfile.TarInfo(name=nome_link)
        link.type = tarfile.SYMTYPE
        link.linkname = alvo
        tf.addfile(link)
    return caminho


def test_extrai_e_devolve_a_raiz_unica_do_tarball(tmp_path):
    tar = montar_tar(tmp_path, {"gabhrielv-hoppr-a1b2c3/README.md": "oi"})
    destino = tmp_path / "saida"
    destino.mkdir()

    raiz = extrair(tar, destino)

    assert raiz.name == "gabhrielv-hoppr-a1b2c3"
    assert (raiz / "README.md").read_text() == "oi"


def test_recusa_membro_que_escapa_do_destino(tmp_path):
    tar = montar_tar(tmp_path, {"../fora.txt": "invasor"})
    destino = tmp_path / "saida"
    destino.mkdir()

    with pytest.raises(tarfile.FilterError):
        extrair(tar, destino)

    assert not (tmp_path / "fora.txt").exists()


def test_caminho_absoluto_e_neutralizado_dentro_do_destino(tmp_path):
    # O filtro `data` não recusa caminho absoluto: remove a barra inicial e
    # grava dentro do destino. O que importa é que nada escapa.
    tar = montar_tar(tmp_path, {"/etc/invadido": "invasor"})
    destino = tmp_path / "saida"
    destino.mkdir()

    extrair(tar, destino)

    assert (destino / "etc" / "invadido").read_text() == "invasor"
    assert not Path("/etc/invadido").exists()


def test_recusa_symlink_para_fora(tmp_path):
    tar = montar_tar_com_link(tmp_path, "raiz/vazamento", "/etc/passwd")
    destino = tmp_path / "saida"
    destino.mkdir()

    with pytest.raises(tarfile.FilterError):
        extrair(tar, destino)


def test_recusa_tarball_sem_raiz_unica(tmp_path):
    tar = montar_tar(tmp_path, {"a/x.py": "1", "b/y.py": "2"})
    destino = tmp_path / "saida"
    destino.mkdir()

    with pytest.raises(PacoteInvalido):
        extrair(tar, destino)


def test_recusa_tarball_que_expande_demais(tmp_path, monkeypatch):
    # Bomba de descompressão: 50 KB comprimidos viram 50 MB em disco.
    from pra.analisador import pacote

    monkeypatch.setattr(pacote, "LIMITE_EXTRACAO_BYTES", 1024)
    tar = montar_tar(tmp_path, {"raiz/grande.bin": "x" * 5000})
    destino = tmp_path / "saida"
    destino.mkdir()

    with pytest.raises(PacoteInvalido, match="grande demais"):
        extrair(tar, destino)

    assert list(destino.iterdir()) == []


def test_contexto_sobrevive_a_ida_e_volta_em_json(tmp_path):
    original = Contexto(
        owner="gabhrielv",
        repo="hoppr",
        head_sha="a1b2c3",
        evento=Evento.PULL_REQUEST,
        linhas_tocadas={"backend/app/main.py": (FaixaLinhas(10, 20), FaixaLinhas(40, 41))},
        numero_pr=7,
        base_sha="0f0f0f",
    )
    caminho = tmp_path / "contexto.json"

    escrever_contexto(original, caminho)

    assert ler_contexto(caminho) == original


def test_contexto_com_campo_faltando_estoura(tmp_path):
    caminho = tmp_path / "contexto.json"
    caminho.write_text('{"owner": "gabhrielv"}')

    with pytest.raises(PacoteInvalido):
        ler_contexto(caminho)


def test_contexto_com_estrutura_errada_estoura(tmp_path):
    caminho = tmp_path / "contexto.json"
    caminho.write_text(
        '{"owner":"o","repo":"r","head_sha":"s","evento":"push","linhas_tocadas":"nao e mapa"}'
    )

    with pytest.raises(PacoteInvalido):
        ler_contexto(caminho)
