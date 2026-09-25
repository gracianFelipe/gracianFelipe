"""
Gera `faixa.svg`: a frase de abertura do perfil, digitada letra a letra.

Por que não usar o readme-typing-svg como todo mundo: aquele serviço só aceita
fundo de cor sólida. Um retângulo chapado atravessando a largura toda do README
fica pesado — o que se quer é a faixa nascendo colada na frase e se dissolvendo
nas pontas, acompanhando o texto enquanto ele cresce e apaga.

Como funciona:

* A faixa é um retângulo pintado com gradiente radial em unidades de bounding
  box. Como a caixa é larga e baixa, o gradiente vira uma elipse achatada
  sozinho: dissolve bastante nas laterais e pouco em cima e embaixo, que é
  justamente o efeito pedido.
* Largura da faixa e recorte do texto são animados pelo mesmo conjunto de
  quadros, então o gradiente nunca descola da frase.
* A fonte vai embutida. SVG carregado como imagem não busca recurso externo,
  então sem embutir a Space Mono o GitHub renderizaria com a monoespaçada
  padrão de cada visitante — e a medida de cada caractere, que é o que
  sincroniza a animação, deixaria de valer.

Uso: python scripts/gerar-faixa.py
"""

import base64
import io
import re
import urllib.request
from pathlib import Path

from fontTools.subset import Subsetter
from fontTools.ttLib import TTFont

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "faixa.svg"

FRASES = [
    "Do banco de dados à interface",
    "Web, mobile e automação em produção",
    "Sistema que alguém usa todo dia",
    "Demo navegável > screenshot bonito",
]

# Identidade do portfólio: ink de fundo, verde ácido no texto.
INK = "#1c1c1c"
ACIDO = "#d0fa66"

TAMANHO = 22          # px da fonte
ALTURA = 64           # altura do quadro
FOLGA = 26            # respiro entre a última letra e o fim do gradiente
LARGURA = 900         # largura do quadro; o GitHub reduz proporcionalmente

MS_LETRA = 55         # digitando
MS_APAGAR = 28        # apagando
MS_PAUSA = 1500       # frase inteira parada na tela


def fonte_embutida(texto):
    """Baixa a Space Mono Bold e devolve (data-uri, avanço por caractere)."""
    css = urllib.request.urlopen(
        urllib.request.Request(
            "https://fonts.googleapis.com/css2?family=Space+Mono:wght@700",
            # Sem um UA de navegador completo o Google devolve TTF em vez de
            # woff2, e o arquivo embutido triplicaria de tamanho.
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            },
        )
    ).read().decode()

    # A última @font-face do CSS é a do intervalo latino básico.
    url = re.findall(r"https://[^)]*\.woff2", css)[-1]
    bruto = urllib.request.urlopen(url).read()

    fonte = TTFont(io.BytesIO(bruto))
    sub = Subsetter()
    sub.populate(text="".join(sorted(set(texto))))
    sub.subset(fonte)

    buffer = io.BytesIO()
    fonte.flavor = "woff2"
    fonte.save(buffer)

    # Monoespaçada: todo glifo tem o mesmo avanço, então um serve de régua.
    upem = fonte["head"].unitsPerEm
    avanco = fonte["hmtx"]["a"][0] / upem * TAMANHO

    uri = "data:font/woff2;base64," + base64.b64encode(buffer.getvalue()).decode()
    return uri, avanco


def quadros(frases, avanco):
    """
    Monta os @keyframes de cada frase dentro do ciclo completo.

    A largura é animada direto, e não por uma variável CSS: propriedade
    personalizada não registrada não interpola — o valor pularia de um quadro
    para o outro e o texto ficaria invisível quase o tempo todo.

    Por isso saem dois conjuntos de quadros por frase, um para o recorte que
    revela o texto e outro para a faixa. Os dois compartilham os mesmos
    instantes, então o gradiente nunca descola da frase; a faixa só acrescenta
    a folga das pontas, que é onde ele dissolve.

    O `steps(n)` fica dentro do quadro que abre cada trecho, porque é ali que
    o CSS deixa trocar a curva por segmento — é o que dá o avanço letra a
    letra em vez de um crescimento contínuo.
    """
    duracoes = [
        len(f) * MS_LETRA + MS_PAUSA + len(f) * MS_APAGAR for f in frases
    ]
    total = sum(duracoes)

    regras, corpo = [], []
    decorrido = 0

    for i, frase in enumerate(frases):
        n = len(frase)
        largura_texto = n * avanco
        esquerda = (LARGURA - largura_texto) / 2

        digitar = n * MS_LETRA
        apagar = n * MS_APAGAR

        def pct(ms):
            return round(ms / total * 100, 4)

        # (instante, largura do texto revelado, curva que rege o trecho a partir dali)
        marcos = [
            (0, 0, "step-end"),
            (decorrido, 0, f"steps({n})"),
            (decorrido + digitar, largura_texto, "step-end"),
            (decorrido + digitar + MS_PAUSA, largura_texto, f"steps({n})"),
            (decorrido + digitar + MS_PAUSA + apagar, 0, "step-end"),
            (total, 0, "step-end"),
        ]

        for sufixo, extra in (("t", 0), ("b", FOLGA * 2)):
            # Texto zerado tem de zerar a faixa junto. Somando a folga sempre,
            # as frases em repouso deixavam um toco de 52px visível atrás
            # da frase da vez — três blocos escuros soltos na imagem.
            passos = "".join(
                f"{pct(ms)}%{{width:{round(largura + extra, 2) if largura else 0}px;"
                f"animation-timing-function:{curva}}}"
                for ms, largura, curva in marcos
            )
            regras.append(f"@keyframes {sufixo}{i}{{{passos}}}")

        corpo.append((i, frase, esquerda, largura_texto))
        decorrido += duracoes[i]

    return regras, corpo, total


def main():
    uri, avanco = fonte_embutida("".join(FRASES))
    regras, corpo, total = quadros(FRASES, avanco)

    linhas = []
    for i, frase, esquerda, largura_texto in corpo:
        escapada = (
            frase.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        linhas.append(
            f'''  <g class="linha l{i}">
    <g mask="url(#mVertical)"><g mask="url(#mLateral)">
      <rect class="faixa" x="{round(esquerda - FOLGA, 2)}" y="{(ALTURA - 40) // 2}"
            height="40" rx="6"/>
    </g></g>
    <g clip-path="url(#corte{i})">
      <text x="{round(esquerda, 2)}" y="{ALTURA // 2}" dominant-baseline="central"
            font-family="Space Mono" font-weight="700" font-size="{TAMANHO}"
            fill="{ACIDO}" xml:space="preserve">{escapada}</text>
    </g>
  </g>'''
        )

    cortes = "".join(
        f'<clipPath id="corte{i}"><rect class="corte c{i}" '
        f'x="{round(esquerda, 2)}" y="0" height="{ALTURA}"/></clipPath>'
        for i, _, esquerda, _ in corpo
    )

    css_linhas = "\n".join(
        f"      .l{i} .faixa{{animation:b{i} {total}ms infinite}}"
        f".c{i}{{animation:t{i} {total}ms infinite}}"
        for i, *_ in corpo
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="{ALTURA}"
     viewBox="0 0 {LARGURA} {ALTURA}" role="img"
     aria-label="{' · '.join(FRASES)}">
  <defs>
    <style>
      @font-face{{font-family:"Space Mono";font-weight:700;src:url({uri}) format("woff2")}}
      /* Estado de repouso: sem a animação, nada ocupa espaço. */
      .faixa,.corte{{width:0}}
      /*
       * No claro a barra escura é o que torna o ácido legível; no escuro
       * ela seria mais clara que o fundo do GitHub e viraria mancha, então
       * vira um brilho da própria cor do texto.
       */
      .faixa{{fill:{INK};fill-opacity:1}}
      @media (prefers-color-scheme:dark){{.faixa{{fill:{ACIDO};fill-opacity:.13}}}}
{css_linhas}
      /* Quem pediu menos movimento vê a primeira frase parada, por inteiro. */
      @media (prefers-reduced-motion:reduce){{
        .faixa,.corte{{animation:none!important}}
        .l0 .faixa{{width:{round(corpo[0][3] + FOLGA * 2, 2)}px}}
        .c0{{width:{round(corpo[0][3], 2)}px}}
      }}
{chr(10).join('      ' + r for r in regras)}
    </style>
    <!--
      A dissolução vive numa máscara, não na cor.

      A primeira tentativa foi um gradiente radial no próprio preenchimento.
      Funcionava em frase curta e falhava nas longas: como o raio é
      proporcional à caixa, quanto maior a frase mais cedo a transparência
      começava, e o texto acabava com o começo e o fim caindo fora da barra —
      ilegíveis no tema claro. Aqui as paradas ficam em porcentagem pequena e
      fixa, então a barra é sólida ao longo de toda a frase e só dissolve nas
      pontas, que é onde ela some.

      São duas máscaras multiplicadas: a horizontal faz a dissolução das
      laterais, a vertical dá o respiro de cima e de baixo.
    -->
    <linearGradient id="lateral" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0%" stop-color="#000"/>
      <stop offset="6%" stop-color="#fff"/>
      <stop offset="94%" stop-color="#fff"/>
      <stop offset="100%" stop-color="#000"/>
    </linearGradient>
    <linearGradient id="vertical" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" stop-color="#000"/>
      <stop offset="16%" stop-color="#fff"/>
      <stop offset="84%" stop-color="#fff"/>
      <stop offset="100%" stop-color="#000"/>
    </linearGradient>
    <!--
      maskContentUnits em objectBoundingBox: sem isso o retângulo da máscara
      mediria a viewport inteira (900px) e não a faixa, e a dissolução ficaria
      parada enquanto a barra cresce.
    -->
    <mask id="mLateral" maskContentUnits="objectBoundingBox">
      <rect width="1" height="1" fill="url(#lateral)"/>
    </mask>
    <mask id="mVertical" maskContentUnits="objectBoundingBox">
      <rect width="1" height="1" fill="url(#vertical)"/>
    </mask>


    {cortes}
  </defs>
{chr(10).join(linhas)}
</svg>
'''

    SAIDA.write_text(svg, encoding="utf-8")
    print(f"ok — {SAIDA.name}, {len(svg) / 1024:.1f} KB, ciclo de {total / 1000:.1f}s")


if __name__ == "__main__":
    main()
