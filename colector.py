import os
import requests
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Faltan las variables de entorno SUPABASE_URL o SUPABASE_KEY.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Códigos clave del corredor de Extremadura
TRENES_EXTREMADURA = [
    "190", "192", "194", "291", "293", "295", "297", "299",
    "17012", "17018", "17021", "17028", "17029", "17801",
    "17806", "18330", "18331", "18770", "18773", "18775", "18779"
]

URL_TRIP_UPDATES = "https://gtfsrt.renfe.com/trip_updates_LD.json"
URL_VEHICLE_POSITIONS = "https://gtfsrt.renfe.com/vehicle_positions_LD.json"

def es_tren_extremadura(trip_id: str) -> bool:
    trip_str = str(trip_id)
    return any(codigo in trip_str for codigo in TRENES_EXTREMADURA)

def obtener_posiciones_gps():
    posiciones = {}
    try:
        resp = requests.get(URL_VEHICLE_POSITIONS, timeout=10)
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
                        posiciones[trip_id] = {"lat": float(lat), "lon": float(lon)}
    except Exception as e:
        print(f"Aviso al descargar vehicle_positions: {e}")
    return posiciones

def main():
    print("Descargando telemetría oficial de Renfe...")
    posiciones_gps = obtener_posiciones_gps()

    try:
        resp = requests.get(URL_TRIP_UPDATES, timeout=10)
        resp.raise_for_status()
        datos = resp.json()
    except Exception as e:
        print(f"Error al descargar trip_updates: {e}")
        return

    registros = []
    for item in datos.get("entity", []):
        trip_update = item.get("trip_update", {})
        trip = trip_update.get("trip", {})
        trip_id = trip.get("trip_id", "")

        if es_tren_extremadura(trip_id):
            delay_segundos = trip_update.get("delay", 0)
            retraso_minutos = round(delay_segundos / 60) if delay_segundos else 0

            # Última parada reportada
            stop_updates = trip_update.get("stop_time_update", [])
            estacion = "En trayecto"
            if stop_updates:
                primera = stop_updates[0]
                estacion = primera.get("stop_id", "En trayecto")

            # Coordenadas GPS si están disponibles en vehicle_positions
            gps = posiciones_gps.get(trip_id, {})
            lat = gps.get("lat")
            lon = gps.get("lon")

            registros.append({
                "tren_id": str(trip_id),
                "estacion_actual": str(estacion),
                "retraso_minutos": retraso_minutos,
                "estado": "CIRCULANDO",
                "latitud": lat,
                "longitud": lon
            })

    if registros:
        res = supabase.table("registros_trenes").insert(registros).execute()
        print(f"Éxito: {len(registros)} trenes extremeños guardados.")
    else:
        print("Sin trenes extremeños circulando en este minuto.")

if __name__ == "__main__":
    main()
