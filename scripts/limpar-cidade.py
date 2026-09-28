"""
Deixa na cidade 3D só a cidade, o total de contribuições e o período.

O gerador (yoshi389111/github-profile-3d-contrib) não tem modo "só a cidade":
a imagem completa sempre traz mais três peças, e as três só enxergam o que é
público. Como quase todo o código está em repositório privado, cada uma
contaria uma história falsa:

* pizza de linguagens: diria que eu escrevo Go e Python e mais nada;
* radar por tipo (commit, issue, PR...): o GitHub só detalha o público, então
  o radar mostrava ~30 commits ao lado de um total de 1.450;
* estrelas e forks: zero, pelo mesmo motivo.

O total vem do calendário, que conta as contribuições privadas (a opção
"Include private contributions on my profile" está ligada), então esse fica.

Qualquer peça não encontrada derruba o passo: é melhor falhar alto do que
publicar uma imagem com o pedaço errado arrancado se o gerador mudar. A
versão do gerador está fixada no workflow.

Uso: python scripts/limpar-cidade.py profile-3d-contrib/cidade-3d.svg
"""
import sys
import xml.etree.ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)
G, TEXT = f"{{{SVG}}}g", f"{{{SVG}}}text"
LARGURA = 1280

caminho = sys.argv[1]
arvore = ET.parse(caminho)
raiz = arvore.getroot()


def textos(elemento):
    return {t.text for t in elemento.iter(TEXT) if t.text}


grupos = [g for g in raiz if g.tag == G]
radar = [g for g in grupos if "Commit" in textos(g)]
totais = [g for g in grupos if "contributions" in textos(g)]
# A pizza é o outro grupo com texto: as legendas das linguagens.
pizza = [g for g in grupos if textos(g) and g not in radar and g not in totais]

for nome, achados in (("radar", radar), ("totais", totais), ("pizza", pizza)):
    if len(achados) != 1:
        sys.exit(f"{nome}: esperava 1 grupo, achei {len(achados)}")

raiz.remove(radar[0])
raiz.remove(pizza[0])

# Estrelas e forks: cada um é um ícone (<g>) seguido do número (<text>).
total = totais[0]
filhos = list(total)
icones = [c for c in filhos if c.tag == G]
if len(icones) != 2:
    sys.exit(f"estrelas/forks: esperava 2 ícones, achei {len(icones)}")
for icone in icones:
    numero = filhos[filhos.index(icone) + 1]
    if numero.tag != TEXT:
        sys.exit("estrelas/forks: o ícone não vem seguido do número")
    total.remove(icone)
    total.remove(numero)

# Sem as estrelas ao lado, o total fica sozinho à esquerda. Centraliza o par
# "1450 contributions", que usa o espaço entre os dois textos como eixo.
numero, rotulo = [t for t in total if t.tag == TEXT and t.text in textos(total)][:2]
if rotulo.text != "contributions":
    sys.exit("totais: ordem inesperada dos textos")
eixo = (float(numero.get("x")) + float(rotulo.get("x"))) / 2
deslocamento = LARGURA / 2 - eixo
for t in (numero, rotulo):
    t.set("x", str(round(float(t.get("x")) + deslocamento, 2)))

arvore.write(caminho, encoding="utf-8", xml_declaration=False)
print("cidade limpa: pizza, radar, estrelas e forks removidos")
