"""
Tira o gráfico de pizza de linguagens da cidade 3D.

O gerador (yoshi389111/github-profile-3d-contrib) não tem modo "só a cidade":
a imagem completa sempre traz a pizza. E a pizza só enxerga repositório
público. Com quase todo o código em repositório privado, ela afirmaria que eu
escrevo Go e Python e mais nada, o mesmo problema do card de "linguagens mais
usadas" que já saiu deste perfil.

Remove o grupo de primeiro nível que tem textos mas não é nem o radar (que tem
"Commit") nem a linha de totais (que tem "contributions"). A versão do gerador
está fixada no workflow, então a estrutura não muda por baixo.

Uso: python scripts/tirar-pizza.py profile-3d-contrib/cidade-3d.svg
"""
import sys
import xml.etree.ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)

caminho = sys.argv[1]
arvore = ET.parse(caminho)
raiz = arvore.getroot()

removidos = 0
for grupo in list(raiz):
    if not grupo.tag.endswith("}g"):
        continue
    textos = {t.text for t in grupo.iter(f"{{{SVG}}}text") if t.text}
    if textos and "Commit" not in textos and "contributions" not in textos:
        raiz.remove(grupo)
        removidos += 1

if removidos != 1:
    # Se o gerador mudou de estrutura, é melhor falhar alto do que publicar
    # uma imagem com o pedaço errado arrancado.
    sys.exit(f"esperava remover 1 grupo, removi {removidos}")

arvore.write(caminho, encoding="utf-8", xml_declaration=False)
print("pizza de linguagens removida")
