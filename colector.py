import json
import os
import urllib.request
from supabase import create_client

# Leemos las credenciales desde los secretos de GitHub
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

URL_POSICIONES = "https://gtfsrt.renfe.com/vehicle_positions_LD.json"
URL_RETRASOS = "https://gtfsrt.renfe.com/trip_updates_LD.json"

TRENES_EXTREMADURA = {
    "00190",
    "00194",
    "00197",
    "00198",
    "17900",
    "17902",
    "17903",
    "17905",
    "17907",
    "17908",
    "17914",
    "17916",
    "17917",
    "18770",
    "18771",
    "18776",
    "18779",
}


def descargar_json(url):
  headers = {"User-Agent": "Mozilla/5.0"}
  req = urllib.request.Request(url, headers=headers)
  with urllib.request.urlopen(req) as response:
    return json.loads(response.read().decode())


def ejecutar_captura():
  print("Consultando datos de Renfe...")
  try:
    posiciones_raw = descargar_json(URL_POSICIONES)
    retrasos_raw = descargar_json(URL_RETRASOS)
  except Exception as e:
    print(f"Error descargando datos: {e}")
    return

  mapa_retrasos = {}
  for entidad in retrasos_raw.get("entity", []):
    trip_update = entidad.get("trip_update", {})
    vehiculo_id = trip_update.get("vehicle", {}).get("id")

    if not vehiculo_id and "trip" in trip_update:
      trip_id = trip_update["trip"].get("tripId", "")
      vehiculo_id = trip_id[:5] if len(trip_id) >= 5 else None

    retraso_seg = trip_update.get("delay")
    if retraso_seg is None and "stop_time_update" in trip_update:
      paradas = trip_update["stop_time_update"]
      if paradas:
        llegada = paradas[-1].get("arrival", {})
        retraso_seg = llegada.get("delay", 0)

    if vehiculo_id and retraso_seg is not None:
      mapa_retrasos[vehiculo_id] = round(retraso_seg / 60)

  registros = []
  for entidad in posiciones_raw.get("entity", []):
    vehiculo = entidad.get("vehicle", {})
    tren_id = vehiculo.get("vehicle", {}).get("id")

    if not tren_id and "trip" in vehiculo:
      trip_id = vehiculo["trip"].get("tripId", "")
      tren_id = trip_id[:5] if len(trip_id) >= 5 else None

    if tren_id in TRENES_EXTREMADURA:
      retraso_min = mapa_retrasos.get(tren_id, 0)
      registros.append({
          "tren_id": tren_id,
          "estacion_actual": vehiculo.get("stopId", "En trayecto"),
          "retraso_minutos": retraso_min,
          "estado": vehiculo.get("currentStatus", "DESCONOCIDO"),
      })

  if registros:
    supabase.table("registros_trenes").insert(registros).execute()
    print(f"Éxito: {len(registros)} registros guardados.")
  else:
    print("Sin trenes extremeños activos en este momento.")


if __name__ == "__main__":
  ejecutar_captura()
