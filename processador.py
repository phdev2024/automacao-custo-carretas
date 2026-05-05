import xml.etree.ElementTree as ET
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import time

# Configurações de Geolocalização
geolocator = Nominatim(user_agent="gestor_logistico_ortobom")
# Endereço da sua Base fornecido
ENDERECO_BASE = "R. Paraíso, Qd.07 - Lt.11 - Jardim Paraiso, Aparecida de Goiânia - GO, 74984-400"
COORD_BASE = (-16.7915, -49.2368) # Coordenadas aproximadas da sua base

def extrair_dados_xml(arquivo):
    try:
        tree = ET.parse(arquivo)
        root = tree.getroot()
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        
        def carregar(path):
            node = root.find(path, ns)
            return node.text if node is not None else ""

        # Extraímos o endereço completo para visualização na planilha
        rua = carregar('.//nfe:dest/nfe:enderDest/nfe:xLgr')
        nro = carregar('.//nfe:dest/nfe:enderDest/nfe:nro')
        cidade = carregar('.//nfe:dest/nfe:enderDest/nfe:xMun')
        uf = carregar('.//nfe:dest/nfe:enderDest/nfe:UF')
        
        # Extraímos o CEP especificamente para a busca no Mapa
        cep = carregar('.//nfe:dest/nfe:enderDest/nfe:CEP')

        dados = {
            "Nota": carregar('.//nfe:ide/nfe:nNF'),
            "Emissao": carregar('.//nfe:ide/nfe:dhEmi')[:10],
            "Emitente": carregar('.//nfe:emit/nfe:xNome'),
            "Valor_Total": float(carregar('.//nfe:total/nfe:ICMSTot/nfe:vNF') or 0),
            "Endereco_Destino": f"{rua}, {nro}, {cidade} - {uf}",
            "CEP_Destino": cep, # Guardamos o CEP aqui
            "Cidade": cidade,  # Adicione esta linha
            "UF": uf           # Adicione esta linha
        }
        return dados
    except Exception as e:
        return None

def calcular_distancia(dados_xml):
    try:
        # Pegamos os dados do dicionário
        cidade = dados_xml.get("Cidade", "")
        uf = dados_xml.get("UF", "")
        cep = str(dados_xml.get("CEP_Destino", "")).replace("-", "").strip()
        
        # PLANO A: Cidade, Estado, Brasil (Altíssima taxa de acerto no Geopy)
        busca_principal = f"{cidade}, {uf}, Brazil"
        location = geolocator.geocode(busca_principal, timeout=15)
        
        # PLANO B: Se a cidade falhar, tentamos pelo CEP puro
        if not location:
            location = geolocator.geocode({"postalcode": cep, "country": "Brazil"}, timeout=15)
            
        if location:
            coord_cliente = (location.latitude, location.longitude)
            
            # Cálculo e aplicação do Fator de 20%
            distancia_reta = geodesic(COORD_BASE, coord_cliente).km
            distancia_final = distancia_reta * 1.20
            
            return round(distancia_final, 2), location.latitude, location.longitude
            
        return 0, 0, 0
    except Exception as e:
        return 0, 0, 0

def calcular_custos(dados, p_base, p_logcare):
    # Agora passamos o pacote de 'dados' completo para o GPS se virar
    km, lat, lon = calcular_distancia(dados)
    
    dados["KM_Estimado"] = km
    dados["Latitude"] = lat
    dados["Longitude"] = lon
    
    dados["Custo_Base"] = dados["Valor_Total"] * p_base
    dados["Custo_Logcare"] = dados["Valor_Total"] * p_logcare
    dados["Custo_Total_Nota"] = dados["Custo_Base"] + dados["Custo_Logcare"]
    return dados