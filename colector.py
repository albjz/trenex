import json
import os
import urllib.request
from supabase import create_client

# 1. Conexión segura con Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. Endpoints oficiales de Renfe GTFS-RT
URL_POSICIONES = "https://gtfsrt.renfe.com/vehicle_positions_LD.json"
URL_RETRASOS = "https://gtfsrt.renfe.com/trip_updates_LD.json"

# 3. Lista maestra de trenes oficiales de Extremadura (válidos desde septiembre 2026)
TRENES_EXTREMADURA_RAW = {
    # Alvia (Madrid - Badajoz)
    "190",
    "192",
    "194",
    "291",
    "293",
    "295",
    "297",
    "299",
    # Madrid - Cáceres - Badajoz - Sevilla
    "17012",
    "17014",
    "17018",
    "17021",
    "17026",
    "17028",
    "17029",
    "17030",
    "17031",
    "17032",
    "17033",
    "17190",
    "17191",
    "17192",
    "17193",
    "17702",
    "17705",
    "17706",
    "17707",
    "17815",
    "17817",
    "17823",
    "17902",
    "17967",
    "18773",
    "18775",
    "18779",
    # Zafra - Huelva
    "13086",
    "13087",
    "13088",
    "13089",
    # Corredor Badajoz - Mérida - Puertollano - Alcázar
    "17801",
    "17803",
    "17806",
    "17810",
    "17812",
    "18330",
    "18331",
    "18770",
    "18777",
}

# Normalizamos a formato de 5 caracteres con ceros a la izquierda (ej: '194' -> '00194')
TRENES_EXTREMADURA = {num.zfill(5) for num in TRENES_EXTREMADURA_RAW}


def normalizar_id_tren(raw_id):
  """Extrae los dígitos del tren y los devuelve a 5 caracteres."""
  if not raw_id:
    return None
  digitos = "".join(filter(str.isdigit, str(raw_id)))
  if len(digitos) >= 5:
    return digitos[:5]
  elif len(digitos) > 0:
    return digitos.zfill(5)
  return None


def descargar_json(url):
  headers = {"User-Agent": "Mozilla/5.0"}
  req = urllib.request.Request(url, headers=headers)
  with urllib.request.urlopen(req) as response:
    return json.loads(response.read().decode())


def ejecutar_captura():
  print("Consultando datos en vivo de Renfe...")
  try:
    posiciones_raw = descargar_json(URL_POSICIONES)
    retrasos_raw = descargar_json(URL_RETRASOS)
  except Exception as e:
    print(f"Error descargando datos: {e}")
    return

  # Mapa de retrasos en minutos indexado por identificador normalizado
  mapa_retrasos = {}
  for entidad in retrasos_raw.get("entity", []):
    trip_update = entidad.get("trip_update", {})

    tren_candidato = trip_update.get("vehicle", {}).get("id")
    if not tren_candidato and "trip" in trip_update:
      tren_candidato = trip_update["trip"].get("tripId")

    tren_id = normalizar_id_tren(tren_candidato)

    retraso_seg = trip_update.get("delay")
    if retraso_seg is None and "stop_time_update" in trip_update:
      paradas = trip_update["stop_time_update"]
      if paradas:
        llegada = paradas[-1].get("arrival", {})
        retraso_seg = llegada.get("delay", 0)

    if tren_id and retraso_seg is not None:
      mapa_retrasos[tren_id] = round(retraso_seg / 60)

  # Filtrar posiciones para trenes del catálogo extremeño
  registros = []
  for entidad in posiciones_raw.get("entity", []):
    vehiculo = entidad.get("vehicle", {})

    tren_candidato = vehiculo.get("vehicle", {}).get("id")
    if not tren_candidato and "trip" in vehiculo:
      tren_candidato = vehiculo["trip"].get("tripId")

    tren_id = normalizar_id_tren(tren_candidato)

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
    print(f"Éxito: {len(registros)} registros extremeños guardados.")
  else:
    print("Sin trenes extremeños activos en este momento.")


if __name__ == "__main__":
  ejecutar_captura()
