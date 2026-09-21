import os
import re
import requests
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Aviso: Faltan las variables SUPABASE_URL o SUPABASE_KEY.")
    exit(0)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Error conectando a Supabase: {e}")
    exit(0)

# Códigos clave de los servicios comerciales que operan en Extremadura
CODIGOS_EXTREMADURA = [
    "190", "192", "194", "291", "293", "295", "297", "299",
    "17012", "17018", "17021", "17028", "17029",
    "17801", "17806", "18330", "18331", "18770", "18773", "18775", "18779"
]

# Cuadrante geográfico de Extremadura y sus conexiones de acceso
LAT_MIN, LAT_MAX = 37.8, 40.5
LON_MIN, LON_MAX = -7.6, -4.6

# Endpoints oficiales verificados de Renfe
ENDPOINTS_TRIP = [
    "https://gtfsrt.renfe.com/trip_updates_LD.json",
    "https://gtfsrt.renfe.com/trip_updates.json"
]

ENDPOINTS_POS = [
    "https://gtfsrt.renfe.com/vehicle_positions_LD.json",
    "https://gtfsrt.renfe.com/vehicle_positions.json"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ObservatorioExtremadura/1.0"
}

def coincide_tren(trip_id_str: str) -> bool:
    trip_str = str(trip_id_str)
    for cod in CODIGOS_EXTREMADURA:
        # Coincidencia directa o con ceros a la izquierda (ej: '00190' o '190')
        if cod in trip_str:
            return True
        if cod.zfill(5) in trip_str:
            return True
    return False

def en_extremadura(lat, lon) -> bool:
    if lat is None or lon is None:
        return False
    return (LAT_MIN <= lat <= LAT_MAX) and (LON_MIN <= lon <= LON_MAX)

def main():
    print("--- INICIANDO BARRIDO TELEMETRÍA RENFE ---")
    
    # 1. Descarga de posiciones geográficas (GPS)
    posiciones = {}
    for url in ENDPOINTS_POS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code == 200:
                entidades = r.json().get("entity", [])
                for ent in entidades:
                    veh = ent.get("vehicle", {})
                    t_id = str(veh.get("trip", {}).get("trip_id", "")).strip()
                    pos = veh.get("position", {})
                    if t_id and pos.get("latitude") and pos.get("longitude"):
                        posiciones[t_id] = {
                            "lat": float(pos["latitude"]),
                            "lon": float(pos["longitude"])
                        }
        except Exception as e:
            print(f"Aviso al descargar {url}: {e}")

    print(f"Total posiciones GPS activas capturadas: {len(posiciones)}")

    # 2. Descarga de actualizaciones de viaje y retrasos
    todos_los_viajes = []
    for url in ENDPOINTS_TRIP:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code == 200:
                entidades = r.json().get("entity", [])
                todos_los_viajes.extend(entidades)
                print(f"Recibidos {len(entidades)} viajes desde {url.split('/')[-1]}")
            else:
                print(f"Endpoint {url.split('/')[-1]} devolvió HTTP {r.status_code}")
        except Exception as e:
            print(f"Aviso al consultar {url}: {e}")

    print(f"Total de servicios analizados en tiempo real: {len(todos_los_viajes)}")

    registros_para_guardar = []
    ids_procesados = set()

    for item in todos_los_viajes:
        tu = item.get("trip_update", {})
        trip = tu.get("trip", {})
        trip_id = str(trip.get("trip_id", "")).strip()
        if not trip_id or trip_id in ids_procesados:
            continue

        gps = posiciones.get(trip_id, {})
        lat = gps.get("lat")
        lon = gps.get("lon")

        # Criterio: Coincide con número de tren extremeño O está físicamente en Extremadura
        es_extremeño = coincide_tren(trip_id) or en_extremadura(lat, lon)

        if es_extremeño:
            ids_procesados.add(trip_id)
            delay_sec = tu.get("delay", 0)
            retraso_min = round(delay_sec / 60) if delay_sec else 0

            # Localizar punto de control
            estacion = "En trayecto"
            stu = tu.get("stop_time_update", [])
            if stu:
                estacion = stu[0].get("stop_id", "En trayecto")

            registros_para_guardar.append({
                "tren_id": trip_id,
                "estacion_actual": str(estacion),
                "retraso_minutos": retraso_min,
                "estado": "CIRCULANDO",
                "latitud": lat,
                "longitud": lon
            })

    if registros_para_guardar:
        try:
            supabase.table("registros_trenes").insert(registros_para_guardar).execute()
            print(f"¡ÉXITO! {len(registros_para_guardar)} circulaciones guardadas en Supabase:")
            for reg in registros_para_guardar:
                print(f" -> {reg['tren_id']} | Retraso: {reg['retraso_minutos']}m | Coordenadas: ({reg['latitud']}, {reg['longitud']})")
        except Exception as e:
            print(f"Error guardando en Supabase: {e}")
    else:
        print("Sin trenes extremeños detectados bajo los filtros en esta pasada.")
        # Muestra de depuración: ver cómo identifica Renfe los servicios ahora mismo
        if todos_los_viajes:
            muestra = [str(it.get("trip_update", {}).get("trip", {}).get("trip_id")) for it in todos_los_viajes[:10]]
            print(f"Muestra de IDs que Renfe está usando ahora mismo: {muestra}")

if __name__ == "__main__":
    main()
