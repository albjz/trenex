import os
import re
import requests
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Faltan las variables de entorno SUPABASE_URL o SUPABASE_KEY.")
    exit(0)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Error inicializando cliente Supabase: {e}")
    exit(0)

# Lista oficial de números comerciales de los trenes extremeños
CODIGOS_EXTREMADURA = {
    # Alvia e Intercity
    "190", "192", "194", "291", "293", "295", "297", "299",
    # Media Distancia / Regionales
    "17012", "17018", "17021", "17028", "17029",
    "17801", "17806", "18330", "18331", "18770", "18773", "18775", "18779"
}

ENDPOINTS_TRIP_UPDATES = [
    "https://gtfsrt.renfe.com/trip_updates_LD.json",
    "https://gtfsrt.renfe.com/trip_updates_MD.json"
]

ENDPOINTS_VEHICLE_POSITIONS = [
    "https://gtfsrt.renfe.com/vehicle_positions_LD.json",
    "https://gtfsrt.renfe.com/vehicle_positions_MD.json"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ObservatorioExtremadura/1.0"
}

def es_tren_extremadura(trip_id: str) -> bool:
    trip_str = str(trip_id)
    # Extrae todos los grupos de dígitos del identificador (ej: de "ALVIA_00190_D" extrae ["00190"])
    numeros = re.findall(r'\d+', trip_str)
    for n in numeros:
        sin_ceros = n.lstrip('0')
        if sin_ceros in CODIGOS_EXTREMADURA or n in CODIGOS_EXTREMADURA:
            return True
    return any(cod in trip_str for cod in CODIGOS_EXTREMADURA)

def obtener_posiciones_gps():
    posiciones = {}
    for url in ENDPOINTS_VEHICLE_POSITIONS:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code == 200:
                datos = resp.json()
                for item in datos.get("entity", []):
                    vehicle = item.get("vehicle", {})
                    trip = vehicle.get("trip", {})
                    trip_id = trip.get("trip_id", "")
                    pos = vehicle.get("position", {})
                    if trip_id and pos:
                        lat = pos.get("latitude")
                        lon = pos.get("longitude")
                        if lat and lon:
                            posiciones[str(trip_id)] = {"lat": float(lat), "lon": float(lon)}
        except Exception as e:
            print(f"Aviso al descargar {url}: {e}")
    return posiciones

def main():
    print("Descargando telemetría oficial de Renfe (LD y MD)...")
    posiciones_gps = obtener_posiciones_gps()

    todos_los_items = []
    for url in ENDPOINTS_TRIP_UPDATES:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code == 200:
                datos = resp.json()
                items = datos.get("entity", [])
                todos_los_items.extend(items)
                print(f"Recibidas {len(items)} circulaciones desde {url.split('/')[-1]}")
            else:
                print(f"Respuesta HTTP {resp.status_code} desde {url}")
        except Exception as e:
            print(f"Error consultando {url}: {e}")

    print(f"Total circulaciones activas en España analizadas: {len(todos_los_items)}")

    # Muestra de depuración en los logs de GitHub Actions
    if todos_los_items:
        muestra_ids = [str(it.get("trip_update", {}).get("trip", {}).get("trip_id", "")) for it in todos_los_items[:8]]
        print(f"Muestra de IDs en el feed: {muestra_ids}")

    registros = []
    for item in todos_los_items:
        trip_update = item.get("trip_update", {})
        trip = trip_update.get("trip", {})
        trip_id = str(trip.get("trip_id", ""))

        if es_tren_extremadura(trip_id):
            delay_segundos = trip_update.get("delay", 0)
            retraso_minutos = round(delay_segundos / 60) if delay_segundos else 0

            stop_updates = trip_update.get("stop_time_update", [])
            estacion = "En trayecto"
            if stop_updates:
                primera = stop_updates[0]
                estacion = primera.get("stop_id", "En trayecto")

            gps = posiciones_gps.get(trip_id, {})
            lat = gps.get("lat")
            lon = gps.get("lon")

            registros.append({
                "tren_id": trip_id,
                "estacion_actual": str(estacion),
                "retraso_minutos": retraso_minutos,
                "estado": "CIRCULANDO",
                "latitud": lat,
                "longitud": lon
            })

    if registros:
        try:
            supabase.table("registros_trenes").insert(registros).execute()
            print(f"Éxito: {len(registros)} trenes extremeños identificados y guardados.")
            for r in registros:
                print(f" -> Tren: {r['tren_id']} | Retraso: {r['retraso_minutos']}m | Estación: {r['estacion_actual']}")
        except Exception as e:
            print(f"Error insertando registros en Supabase: {e}")
    else:
        print("Sin trenes extremeños circulando en este minuto.")

if __name__ == "__main__":
    main()
