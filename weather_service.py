import os
import requests
from datetime import datetime, timedelta
from database import get_db_connection
from psycopg2.extras import RealDictCursor


def fahrenheit_to_celcius(temp):
    if temp is not None:
        celcius = (temp - 32) / 1.8
        return round(celcius, 2)
    return None


def mph_to_kmph(v_mph):
    if v_mph is not None:
        v_kmph = v_mph * 1.609
        return round(v_kmph, 2)
    return None


def salvar_no_banco(dados):
    """Salva os dados no Neon, garantindo que campos numéricos não sejam nulos."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Pegamos a média das previsões ou o temp do dia atual para min/max
        hoje = dados["previsao"][0] if dados["previsao"] else {"temperatura_min": None, "temperatura_max": None}

        # Tratamento para evitar erro de 'null' no banco para todos os campos numéricos
        umidade = dados.get("umidade") if dados.get("umidade") is not None else 0.0
        vento = dados.get("vento") if dados.get("vento") is not None else 0.0
        precipitacao = dados.get("precipitacao") if dados.get("precipitacao") is not None else 0.0
        temp_min = hoje.get("temperatura_min") if hoje.get("temperatura_min") is not None else 0.0
        temp_max = hoje.get("temperatura_max") if hoje.get("temperatura_max") is not None else 0.0

        cur.execute("""
            INSERT INTO historico_clima (cidade, data, umidade, vento, precipitacao, temp_min, temp_max)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            dados["cidade"],
            dados["data"],
            umidade,
            vento,
            precipitacao,
            temp_min,
            temp_max
        ))
        conn.commit()
        print(f"Dados de {dados["cidade"]} salvos com sucesso!")
    except Exception as e:
        print(f"Erro ao salvar no Neon: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()


def buscar_no_banco(cidade, data):
    """Busca registro existente no Neon"""
    conn = None
    try:
        conn = get_db_connection()
        # RealDictCursor faz com que o resultado venha como um dicionário
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # ILIKE é o LIKE case-insensitive do PostgreSQL
        cur.execute("""
            SELECT * FROM historico_clima 
            WHERE cidade ILIKE %s AND data = %s
            LIMIT 1
        """, (f"%{cidade}%", data))

        row = cur.fetchone()
        return row
    except Exception as e:
        print(f"Erro ao buscar no Neon: {e}")
        return None
    finally:
        if conn:
            cur.close()
            conn.close()


def transformar_dados_clima(dados_clima):
    clima_atual = dados_clima.get("currentConditions", {})
    dias = dados_clima.get("days", [])[:7]
    data_atual = datetime.now().strftime("%Y-%m-%d") # Alterado para YYYY-MM-DD para consistência com o banco

    dados_processados = {
        "data": data_atual,
        "hora": clima_atual.get("datetime"),
        "cidade": dados_clima.get("resolvedAddress"),
        "temperatura": fahrenheit_to_celcius(clima_atual.get("temp")),
        "umidade": clima_atual.get("humidity") if clima_atual.get("humidity") is not None else 0.0,
        "vento": mph_to_kmph(clima_atual.get("windspeed")) if clima_atual.get("windspeed") is not None else 0.0,
        "precipitacao": clima_atual.get("precip") if clima_atual.get("precip") is not None else 0.0,
        "icon": clima_atual.get("icon"),
        "previsao": []
    }

    for dia in dias:
        dia_processado = {
            "data": datetime.strptime(dia["datetime"], "%Y-%m-%d").strftime("%d/%m/%Y"),
            "temperatura_max": fahrenheit_to_celcius(dia.get("tempmax")) if dia.get("tempmax") is not None else 0.0,
            "temperatura_min": fahrenheit_to_celcius(dia.get("tempmin")) if dia.get("tempmin") is not None else 0.0,
            "icon": dia.get("icon")
        }
        dados_processados["previsao"].append(dia_processado)

    return dados_processados


def buscar_clima_por_cidade(cidade):
    data_hoje_db = datetime.now().strftime("%Y-%m-%d") # Formato para busca no banco
    data_hoje_frontend = datetime.now().strftime("%d/%m/%Y") # Formato para exibir no frontend

    # 1. Tentar buscar no banco Neon
    registro = buscar_no_banco(cidade, data_hoje_db)

    if registro:
        # Quando os dados vêm do banco, precisamos formatá-los para o frontend
        # e adicionar campos que não estão no banco (como 'hora', 'icon', 'previsao')
        temp_min = registro.get("temp_min")
        temp_max = registro.get("temp_max")
        temperatura_media = (temp_max + temp_min) / 2 if temp_min is not None and temp_max is not None else None

        return {
            "error": False,
            "data": {
                "data": data_hoje_frontend, # Usar a data formatada para o frontend
                "hora": "N/A", # Não temos hora no histórico, pode ser um valor padrão
                "cidade": registro.get("cidade"),
                "temperatura": temperatura_media,
                "umidade": registro.get("umidade"),
                "vento": registro.get("vento"),
                "precipitacao": registro.get("precipitacao"),
                "icon": "cloud", # Ícone padrão, pois não salvamos no histórico
                "previsao": [], # Previsão vazia, pois o histórico é para um único dia
                "origem": "banco_neon" # Adiciona a origem dos dados
            },
            "status": 200,
            "fonte": "banco_neon"
        }

    # 2. Se não houver no banco, consulta API
    base_url = os.getenv("BASE_URL_VISUAL_CROSSING")
    api_key = os.getenv("VISUAL_CROSSING_API_KEY")

    data_inicial = datetime.now().strftime("%Y-%m-%d")
    data_final = (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d")
    url = f"{base_url}{cidade}/{data_inicial}/{data_final}?key={api_key}&unitGroup=us&include=days,current"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        dados_api = transformar_dados_clima(response.json())
        dados_api["origem"] = "api_externa" # Adiciona a origem dos dados

        # 3. Salvar no Neon após a consulta bem-sucedida da API
        salvar_no_banco(dados_api)

        return {
            "error": False,
            "data": dados_api,
            "status": 200,
            "fonte": "api_externa"
        }
    except Exception as ex:
        return {"error": True, "message": str(ex), "status": 500}
