import os
import re
import requests
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Faltan variables de entorno SUPABASE_URL o SUPABASE_KEY.")
    exit(0)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Error Supabase: {e}")
    exit(0)

# Códigos comerciales de interés
CODIGOS_EXTREMADURA = {
    "190", "192", "194", "291", "293", "295", "297", "299",
    "17012", "17018", "17021", "17028", "17029",
    "17801", "17806", "18330", "18331", "18770", "18773", "18775", "18779"
}

# Límites geográficos aproximados del corredor y región extremeña
GEO_LAT_MIN, GEO_LAT_MAX = 37.8, 40.5
GEO_LON_MIN, GEO_LON_MAX = -7.5, -4.5

ENDPOINTS_TRIP = [
    "https://gtfsrt.renfe.com/trip_updates_LD.json",
    "https://gtfsrt.renfe.com/trip_updates_MD.json"
]

ENDPOINTS_POS = [
    "https://gtfsrt.renfe.com/vehicle_positions_LD.json",
    "https://gtfsrt.renfe.com/vehicle_positions_MD.json"
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def en_zona_extremadura(lat, lon):
    if lat is None or lon is None:
        return False
    return (GEO_LAT_MIN <= lat <= GEO_LAT_MAX) and (GEO_LON_MIN <= lon <= GEO_LON_MAX)

def coincide_codigo(trip_id_str):
    nums = re.findall(r'\d+', trip_id_str)
    for n in nums:
        if n in CODIGOS_EXTREMADURA or n.lstrip('0') in CODIGOS_EXTREMADURA:
            return True
    return False

def main():
    print("Consultando feeds en vivo de Renfe...")
    
    # 1. Obtener posiciones GPS
    posiciones = {}
    for url in ENDPOINTS_POS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                for ent in r.json().get("entity", []):
                    veh = ent.get("vehicle", {})
                    t_id = str(veh.get("trip", {}).get("trip_id", "")).strip()
                    pos = veh.get("position", {})
                    if t_id and pos.get("latitude") and pos.get("longitude"):
                        posiciones[t_id] = {
                            "lat": float(pos["latitude"]),
                            "lon": float(pos["longitude"])
                        }
        except Exception as e:
            print(f"Aviso posiciones ({url}): {e}")

    # 2. Obtener actualizaciones y demoras
    items_via = []
    for url in ENDPOINTS_TRIP:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                entidades = r.json().get("entity", [])
                items_via.extend(entidades)
                print(f"Feed {url.split('/')[-1]}: {len(entidades)} servicios recibidos.")
        except Exception as e:
            print(f"Aviso delays ({url}): {e}")

    registros = []
    
    for item in items_via:
        tu = item.get("trip_update", {})
        trip_id = str(tu.get("trip", {}).get("trip_id", "")).strip()
        if not trip_id:
            continue

        gps = posiciones.get(trip_id, {})
        lat = gps.get("lat")
        lon = gps.get("lon")

        # Criterio dual: por código O por estar físicamente en Extremadura
        es_de_interes = coincide_codigo(trip_id) or en_zona_extremadura(lat, lon)

        if es_de_interes:
            delay_sec = tu.get("delay", 0)
            retraso = round(delay_sec / 60) if delay_sec else 0

            estacion = "En trayecto"
            stu = tu.get("stop_time_update", [])
            if stu:
                estacion = stu[0].get("stop_id", "En trayecto")

            registros.append({
                "tren_id": trip_id,
                "estacion_actual": str(estacion),
                "retraso_minutos": retraso,
                "estado": "CIRCULANDO",
                "latitud": lat,
                "longitud": lon
            })

    if registros:
        try:
            supabase.table("registros_trenes").insert(registros).execute()
            print(f"ÉXITO: Se han guardado {len(registros)} circulaciones:")
            for reg in registros:
                print(f" -> {reg['tren_id']} | Retraso: {reg['retraso_minutos']}m | Lat/Lon: ({reg['latitud']}, {reg['longitud']})")
        except Exception as e:
            print(f"Error al insertar en Supabase: {e}")
    else:
        print("No se encontraron circulaciones que coincidan por código o zona.")
        # Muestra los primeros 5 trenes para ver cómo los nombra Renfe
        if items_via:
            muestra = [it.get("trip_update", {}).get("trip", {}).get("trip_id") for it in items_via[:6]]
            print(f"Ejemplos de trip_id que Renfe está usando ahora mismo: {muestra}")

if __name__ == "__main__":
    main()
