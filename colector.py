import os
import requests
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Faltan las variables de entorno SUPABASE_URL o SUPABASE_KEY.")
    exit(0)  # Salida limpia para no saturar con emails si faltan secretos temporales

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Error inicializando cliente Supabase: {e}")
    exit(0)

TRENES_EXTREMADURA = [
    "190", "192", "194", "291", "293", "295", "297", "299",
    "17012", "17018", "17021", "17028", "17029", "17801",
    "17806", "18330", "18331", "18770", "18773", "18775", "18779"
]

URL_TRIP_UPDATES = "https://gtfsrt.renfe.com/trip_updates_LD.json"
URL_VEHICLE_POSITIONS = "https://gtfsrt.renfe.com/vehicle_positions_LD.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ObservatorioFerroviarioExtremadura/1.0"
}

def es_tren_extremadura(trip_id: str) -> bool:
    trip_str = str(trip_id)
    return any(codigo in trip_str for codigo in TRENES_EXTREMADURA)

def obtener_posiciones_gps():
    posiciones = {}
    try:
        resp = requests.get(URL_VEHICLE_POSITIONS, headers=HEADERS, timeout=15)
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
        print(f"Aviso: No se pudo obtener vehicle_positions en esta pasada ({e})")
    return posiciones

def main():
    print("Descargando telemetría oficial de Renfe...")
    posiciones_gps = obtener_posiciones_gps()

    try:
        resp = requests.get(URL_TRIP_UPDATES, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"Servidor de Renfe no disponible (HTTP {resp.status_code}). Reintentando en la próxima ventana.")
            return
        datos = resp.json()
    except requests.exceptions.Timeout:
        print("Timeout al conectar con el servidor de Renfe. Reintentando en la próxima ventana.")
        return
    except requests.exceptions.RequestException as e:
        print(f"Error de red al consultar Renfe: {e}")
        return
    except Exception as e:
        print(f"Error al decodificar JSON de Renfe: {e}")
        return

    registros = []
    for item in datos.get("entity", []):
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
            print(f"Éxito: {len(registros)} trenes extremeños guardados.")
        except Exception as e:
            print(f"Error insertando registros en Supabase: {e}")
    else:
        print("Sin trenes extremeños circulando en este minuto.")

if __name__ == "__main__":
    main()
