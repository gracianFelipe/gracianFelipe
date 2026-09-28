"""
Space Mono embutida em SVG, reduzida aos caracteres que o desenho usa.

SVG carregado como imagem (que é como o GitHub mostra o README) não busca
recurso externo. Sem a fonte embutida, cada visitante veria a monoespaçada
padrão do próprio sistema, e a medida de cada caractere, que é o que alinha
colunas e sincroniza as animações, deixaria de valer.
"""
import base64
import io
import re
import urllib.request

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

# Sem um UA de navegador completo o Google devolve TTF em vez de woff2, e o
# arquivo embutido triplicaria de tamanho.
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def space_mono(texto, peso, tamanho):
    """Devolve (data-uri woff2, avanço por caractere em px no `tamanho` dado)."""
    css = urllib.request.urlopen(
        urllib.request.Request(
            f"https://fonts.googleapis.com/css2?family=Space+Mono:wght@{peso}",
            headers={"User-Agent": _UA},
        ),
        timeout=30,
    ).read().decode()

    # A última @font-face do CSS é a do intervalo latino básico.
    url = re.findall(r"https://[^)]*\.woff2", css)[-1]
    bruto = urllib.request.urlopen(url, timeout=30).read()

    # recalcTimestamp=False: sem isso o fontTools grava a hora atual no
    # cabeçalho a cada save, e a mesma fonte sai com bytes diferentes em toda
    # execução — diff falso no git e na saída da Action.
    fonte = TTFont(io.BytesIO(bruto), recalcTimestamp=False)
    # frac, numr e dnom saem das features padrão: com "/" e dígitos no texto,
    # o fechamento do GSUB guardava ~31 glifos de fração por peso que o
    # navegador nunca usa (frac não vem ligado por padrão).
    opcoes = Options()
    opcoes.layout_features = [
        f for f in opcoes.layout_features if f not in ("frac", "numr", "dnom")
    ]
    sub = Subsetter(options=opcoes)
    sub.populate(text="".join(sorted(set(texto))))
    sub.subset(fonte)

    buffer = io.BytesIO()
    fonte.flavor = "woff2"
    fonte.save(buffer)

    # Monoespaçada: todo glifo tem o mesmo avanço, então um serve de régua.
    upem = fonte["head"].unitsPerEm
    avanco = fonte["hmtx"]["a"][0] / upem * tamanho

    uri = "data:font/woff2;base64," + base64.b64encode(buffer.getvalue()).decode()
    return uri, avanco
