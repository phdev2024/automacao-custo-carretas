import xml.etree.ElementTree as ET

def extrair_dados_xml(arquivo):
    try:
        tree = ET.parse(arquivo)
        root = tree.getroot()
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        
        def carregar(path):
            node = root.find(path, ns)
            return node.text if node is not None else ""

        dados = {
            "Nota": carregar('.//nfe:ide/nfe:nNF'),
            "Emissao": carregar('.//nfe:ide/nfe:dhEmi')[:10],
            "Emitente": carregar('.//nfe:emit/nfe:xNome'),
            "Valor_Total": float(carregar('.//nfe:total/nfe:ICMSTot/nfe:vNF') or 0),
        }
        return dados
    except Exception as e:
        return None

def calcular_custos(dados, p_base, p_logcare):
    dados["Custo_Base"] = dados["Valor_Total"] * p_base
    dados["Custo_Logcare"] = dados["Valor_Total"] * p_logcare
    dados["Custo_Total_Nota"] = dados["Custo_Base"] + dados["Custo_Logcare"]
    return dados