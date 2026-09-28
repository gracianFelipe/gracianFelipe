"""
Gera `saida/consulta.svg`: uma sessão de psql que consulta a minha atividade.

O terminal digita a consulta, o resultado aparece linha a linha no formato do
psql e a sessão termina com o cursor piscando no prompt. A animação roda uma
vez e para no resultado: é uma tabela para ser lida, e um laço que apagasse a
tela no meio da leitura atrapalharia.

De onde vem cada número:

* Quatro linhas saem do calendário de contribuições do GitHub, lido pela API
  a cada execução. São contribuições, não só commits: o calendário soma
  commit, PR, review e criação de repositório, e o que vem de repositório
  privado chega sem tipo. Por isso a linha é "dias_ativos", e não
  "dias_com_commit". O calendário conta os repositórios privados (inclusive os
  da org escolasuperior) porque "Include private contributions on my profile"
  está ligado; sem isso ele só enxergaria o que é público.
* Duas são fixas, em FIXOS, porque não existem em API nenhuma. Quando mudarem
  no portfólio, mudar aqui.

Total de contribuições e maior sequência ficam de fora de propósito: o card de
streak logo ao lado no README já mostra os dois.

Uso (precisa de um token com leitura pública, o GITHUB_TOKEN da Action basta):
    GITHUB_TOKEN=... python scripts/gerar-consulta.py
"""

import json
import os
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fonte import space_mono

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "saida" / "consulta.svg"
USUARIO = "gracianFelipe"

# Números sem API. Ao mudar, mudar junto a fonte citada.
FIXOS = [
    # Os três com `track: "producao"` no portfólio (src/data/projects.ts),
    # que são também os marcados em produção na tabela deste README:
    # OniSaúde, Maestro e Central de Disparos. O ILP Summit está em
    # `concluido`: o evento acabou e o site saiu do ar.
    ("projetos_em_producao", "3"),
    # Os sistemas da org escolasuperior que são meus: sol-academy, Maestro,
    # sei-mensagens, Auto-Provas, sei-decidir, jornada-sei e ovg-link. A lista
    # é minha, não da API: a org tem outros repositórios com commits meus que
    # não entram aqui.
    ("sistemas_na_esup", "7"),
]

# Identidade do portfólio.
INK = "#1c1c1c"
BORDA = "#2e2e2e"
PAPEL = "#fbfaf3"
ACIDO = "#d0fa66"
PROMPT = "#9fc43a"
APAGADO = "#7d7d74"

TAMANHO = 15          # px da fonte
LINHA = 23            # px entre linhas
MARGEM = 26           # respiro lateral dentro do cartão
BARRA = 36            # altura da barra de título
LARGURA_MIN = 520   # a barra de título precisa de um mínimo

MS_LETRA = 42         # digitando a consulta
MS_ENTER = 380        # pausa entre o ponto e vírgula e o resultado
MS_SAIDA = 70         # entre uma linha de resultado e a próxima

# Brasil sem horário de verão desde 2019: UTC-3 fixo evita depender do banco de
# fusos, que não vem instalado no Python do Windows.
BRASILIA = timezone(timedelta(hours=-3))

DIAS = ["domingo", "segunda-feira", "terça-feira", "quarta-feira",
        "quinta-feira", "sexta-feira", "sábado"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


# ——— dados ————————————————————————————————————————————————————————————

def calendario():
    """Dias do último ano, cada um com data, dia da semana e contribuições."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("defina GITHUB_TOKEN (na Action, secrets.GITHUB_TOKEN basta)")

    consulta = """
      query($login: String!) {
        user(login: $login) {
          contributionsCollection {
            contributionCalendar {
              weeks { contributionDays { date weekday contributionCount } }
            }
          }
        }
      }"""
    pedido = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": consulta, "variables": {"login": USUARIO}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            # Sem isto a janela do calendário segue o fuso de quem consulta; na
            # Action é o bot, em UTC, e à noite o calendário já incluiria o dia
            # seguinte enquanto o comentário mostra o dia de hoje.
            "Time-Zone": "America/Sao_Paulo",
        },
    )
    resposta = json.load(urllib.request.urlopen(pedido, timeout=30))

    # A API devolve 200 com "errors" no corpo quando algo dá errado. A mensagem
    # vem do GitHub e não carrega o token, então pode ir para o log.
    if resposta.get("errors"):
        sys.exit(f"GraphQL: {resposta['errors'][0].get('message')}")
    try:
        semanas = resposta["data"]["user"]["contributionsCollection"][
            "contributionCalendar"]["weeks"]
    except (KeyError, TypeError):
        sys.exit("GraphQL: resposta sem o calendário esperado")

    dias = [d for s in semanas for d in s["contributionDays"]]
    if not dias:
        sys.exit("GraphQL: calendário vazio")
    return dias


def metricas(dias):
    """As quatro linhas que saem do calendário, já formatadas para exibir."""
    ativos = [d for d in dias if d["contributionCount"] > 0]
    if not ativos:
        sys.exit("nenhuma contribuição no período: a tabela sairia só com zeros")

    por_dia = Counter()
    por_mes = Counter()
    for d in dias:
        por_dia[d["weekday"]] += d["contributionCount"]
        por_mes[d["date"][:7]] += d["contributionCount"]

    dia_top = max(por_dia, key=lambda k: (por_dia[k], -k))
    mes_top = max(por_mes, key=lambda k: (por_mes[k], k))
    ano, mes = mes_top.split("-")
    recorde = max(dias, key=lambda d: (d["contributionCount"], d["date"]))
    _, rm, rd = recorde["date"].split("-")

    return [
        ("dias_ativos", f"{len(ativos)} de {len(dias)}"),
        ("dia_mais_ativo", DIAS[dia_top]),
        ("mes_de_pico", f"{MESES[int(mes) - 1]}/{ano} ({por_mes[mes_top]})"),
        ("recorde_em_um_dia", f"{recorde['contributionCount']} em {rd}/{rm}"),
    ]


# ——— texto do terminal ———————————————————————————————————————————————————

def tabela_psql(linhas):
    """Monta o resultado no formato alinhado do psql, em pt-BR."""
    cab = ("metrica", "valor")
    larg = [max(len(cab[i]), *(len(l[i]) for l in linhas)) for i in range(2)]

    def celula(txt, w, centro=False):
        return " " + (txt.center(w) if centro else txt.ljust(w)) + " "

    saida = [
        celula(cab[0], larg[0], True) + "|" + celula(cab[1], larg[1], True).rstrip(),
        "+".join("-" * (w + 2) for w in larg),
    ]
    for nome, valor in linhas:
        saida.append(celula(nome, larg[0]) + "|" + celula(valor, larg[1]).rstrip())
    saida.append(f"({len(linhas)} linhas)")
    return saida


# Consulta digitada: (prompt, [(trecho, é palavra-chave?)])
CONSULTA = [
    ("felipe=# ", [("SELECT", True), (" metrica, valor", False)]),
    ("felipe-# ", [("  FROM", True), (" felipe.atividade", False)]),
    ("felipe-# ", [(" ORDER BY", True), (" peso ", False), ("DESC", True), (";", False)]),
]


def esc(texto):
    """Escapa para texto e para atributo entre aspas duplas (o aria-label)."""
    return (
        texto.replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )


# ——— desenho ——————————————————————————————————————————————————————————————

def main():
    agora = datetime.now(BRASILIA)
    linhas = metricas(calendario()) + FIXOS
    comentario = f"-- atualizado em {agora:%d/%m/%Y}"
    resultado = tabela_psql(linhas)

    todo_texto = (
        comentario + "".join(p + "".join(t for t, _ in c) for p, c in CONSULTA)
        + "".join(resultado) + "psql · felipe@gracianodev"
    )
    fonte_normal, avanco = space_mono(todo_texto, 400, TAMANHO)
    fonte_negrito, _ = space_mono(todo_texto, 700, TAMANHO)

    textos_visiveis = [comentario, *resultado] + [
        p + "".join(t for t, _ in c) for p, c in CONSULTA
    ]
    largura = max(
        LARGURA_MIN, round(2 * MARGEM + max(map(len, textos_visiveis)) * avanco)
    )

    # Posições verticais: comentário, 3 linhas de consulta, respiro, resultado,
    # respiro, prompt final.
    y0 = BARRA + 30
    ys = [y0 + i * LINHA for i in range(1 + len(CONSULTA))]
    y_res = ys[-1] + LINHA + 8
    ys_res = [y_res + i * LINHA for i in range(len(resultado))]
    y_fim = ys_res[-1] + LINHA + 8
    altura = y_fim + 26

    elementos = []
    t = 250  # ms: o comentário aparece de cara, a digitação começa logo depois

    elementos.append(
        f'<text x="{MARGEM}" y="{ys[0]}" fill="{APAGADO}" xml:space="preserve">'
        f"{esc(comentario)}</text>"
    )

    # Consulta: o prompt surge no início de cada linha e o código é revelado
    # por um recorte que cresce um caractere por passo.
    for i, (prompt, trechos) in enumerate(CONSULTA):
        y = ys[i + 1]
        codigo = "".join(txt for txt, _ in trechos)
        x_codigo = MARGEM + len(prompt) * avanco
        dur = len(codigo) * MS_LETRA

        elementos.append(
            f'<text class="surge" style="animation-delay:{t}ms" x="{MARGEM}" '
            f'y="{y}" fill="{PROMPT}" xml:space="preserve">{esc(prompt)}</text>'
        )
        spans = "".join(
            f'<tspan fill="{ACIDO}" font-weight="700">{esc(txt)}</tspan>' if chave
            else f'<tspan fill="{PAPEL}">{esc(txt)}</tspan>'
            for txt, chave in trechos
        )
        larg_recorte = round(len(codigo) * avanco + 2, 2)
        elementos.append(
            f'<clipPath id="q{i}"><rect class="digita" x="{round(x_codigo, 2)}" '
            f'y="{y - LINHA}" height="{LINHA + 6}" style="width:{larg_recorte}px;'
            f"animation-duration:{dur}ms;animation-delay:{t}ms;"
            f'animation-timing-function:steps({len(codigo)},end)"/></clipPath>'
        )
        elementos.append(
            f'<text clip-path="url(#q{i})" x="{round(x_codigo, 2)}" y="{y}" '
            f'xml:space="preserve">{spans}</text>'
        )
        t += dur + 120

    t += MS_ENTER

    # Resultado: cabeçalho em negrito, separador apagado, valores em ácido.
    for j, (texto, y) in enumerate(zip(resultado, ys_res)):
        estilo = f'class="surge" style="animation-delay:{t}ms"'
        if j == 1:
            # O hífen da Space Mono é curto e a linha de "-" do psql virava
            # tracejado. Aqui ela é um traço contínuo, cruzado na coluna do "|"
            # como o "+" faria.
            x_fim = round(MARGEM + len(texto) * avanco, 2)
            x_cruz = round(MARGEM + (texto.index("+") + 0.5) * avanco, 2)
            meio = y - TAMANHO * 0.32
            elementos.append(
                f'<path class="surge" style="animation-delay:{t}ms" '
                f'd="M{MARGEM} {meio:.2f}H{x_fim}M{x_cruz} {meio - LINHA / 2:.2f}'
                f'V{meio + LINHA / 2:.2f}" stroke="{APAGADO}" stroke-width="1"/>'
            )
            t += MS_SAIDA
            continue
        if j == 0:
            # Negrito só nos nomes: o "|" fica com o mesmo peso das linhas.
            nome, valor = texto.split("|", 1)
            corpo = (
                f'<tspan fill="{PAPEL}" font-weight="700">{esc(nome)}</tspan>'
                f'<tspan fill="{APAGADO}">|</tspan>'
                f'<tspan fill="{PAPEL}" font-weight="700">{esc(valor)}</tspan>'
            )
        elif j == len(resultado) - 1:
            corpo = f'<tspan fill="{APAGADO}">{esc(texto)}</tspan>'
        else:
            nome, valor = texto.split("|", 1)
            corpo = (
                f'<tspan fill="{PAPEL}" fill-opacity=".82">{esc(nome)}</tspan>'
                f'<tspan fill="{APAGADO}">|</tspan>'
                f'<tspan fill="{ACIDO}">{esc(valor)}</tspan>'
            )
        elementos.append(
            f'<text {estilo} x="{MARGEM}" y="{y}" xml:space="preserve">{corpo}</text>'
        )
        t += MS_SAIDA

    t += 200
    x_cursor = round(MARGEM + len("felipe=# ") * avanco, 2)
    elementos.append(
        f'<text class="surge" style="animation-delay:{t}ms" x="{MARGEM}" '
        f'y="{y_fim}" fill="{PROMPT}" xml:space="preserve">felipe=# </text>'
    )
    elementos.append(
        f'<rect class="cursor" style="animation-delay:{t}ms,{t}ms" '
        f'x="{x_cursor}" y="{y_fim - TAMANHO + 2}" width="{round(avanco, 2)}" '
        f'height="{TAMANHO + 2}" fill="{ACIDO}"/>'
    )

    rotulo = "; ".join(f"{n}: {v}" for n, v in linhas)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}"
     viewBox="0 0 {largura} {altura}" role="img"
     aria-label="Consulta SQL sobre a atividade de Felipe Graciano. {esc(rotulo)}.">
  <defs>
    <style>
      @font-face{{font-family:"Space Mono";font-weight:400;src:url({fonte_normal}) format("woff2")}}
      @font-face{{font-family:"Space Mono";font-weight:700;src:url({fonte_negrito}) format("woff2")}}
      text{{font-family:"Space Mono",ui-monospace,monospace;font-size:{TAMANHO}px}}
      /*
       * O estado base de cada peça é o final. As animações só descrevem de
       * onde elas vêm e seguram esse começo até o próprio atraso (fill
       * backwards). Sem animação, como em prefers-reduced-motion, sobra a
       * tabela pronta.
       */
      .surge{{animation:surge 160ms ease-out backwards}}
      .digita{{animation-name:digita;animation-fill-mode:backwards}}
      .cursor{{animation:surge 1ms backwards,pisca 1.1s step-end infinite}}
      @keyframes surge{{from{{opacity:0}}}}
      @keyframes digita{{from{{width:0}}}}
      @keyframes pisca{{50%{{opacity:0}}}}
      @media (prefers-reduced-motion:reduce){{
        .surge,.digita,.cursor{{animation:none}}
      }}
    </style>
  </defs>
  <rect x=".5" y=".5" width="{largura - 1}" height="{altura - 1}" rx="10"
        fill="{INK}" stroke="{BORDA}"/>
  <path d="M.5 {BARRA}H{largura - .5}" stroke="{BORDA}"/>
  <rect x="18" y="{BARRA / 2 - 5}" width="10" height="10" fill="{ACIDO}"/>
  <rect x="34" y="{BARRA / 2 - 5}" width="10" height="10" fill="{PAPEL}" fill-opacity=".35"/>
  <rect x="50" y="{BARRA / 2 - 5}" width="10" height="10" fill="{PAPEL}" fill-opacity=".35"/>
  <text x="{largura / 2}" y="{BARRA / 2 + 4}" text-anchor="middle" fill="{APAGADO}"
        style="font-size:12px">psql · felipe@gracianodev</text>
  {chr(10).join("  " + e for e in elementos).strip()}
</svg>
"""
    SAIDA.parent.mkdir(exist_ok=True)
    # LF fixo, pelo mesmo motivo da faixa: saída igual no Windows e na Action.
    SAIDA.write_text(svg, encoding="utf-8", newline="\n")
    print(f"ok, {SAIDA.relative_to(RAIZ)}: {len(svg) / 1024:.1f} KB, "
          f"animação de {t / 1000:.1f}s")
    for nome, valor in linhas:
        print(f"  {nome:<22}{valor}")


if __name__ == "__main__":
    main()
