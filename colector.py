import json
import os
import urllib.request
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

URL_POSICIONES = "https://gtfsrt.renfe.com/vehicle_positions_LD.json"
URL_RETRASOS = "https://gtfsrt.renfe.com/trip_updates_LD.json"

# Códigos limpios de los trenes extremeños según las tablas oficiales
TRENES_BUSCADOS = [
    # Alvia
    "190",
    "192",
    "194",
    "291",
    "293",
    "295",
    "297",
    "299",
    # Regionales / Media Distancia Madrid - Cáceres - Badajoz - Sevilla
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
    # Corredor Badajoz - Puertollano - Alcázar
    "17801",
    "17803",
    "17806",
    "17810",
    "17812",
    "18330",
    "18331",
    "18770",
    "18777",
]


def coincide_tren(cadena_texto):
  """Comprueba si alguno de los números extremeños está dentro del identificador de Renfe."""
  if not cadena_texto:
    return None
  texto = str(cadena_texto)
  for num in TRENES_BUSCADOS:
    if num in texto:
      return num
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

  # Mapa de retrasos
  mapa_retrasos = {}
  for entidad in retrasos_raw.get("entity", []):
    trip_update = entidad.get("trip_update", {})

    id_vehiculo = trip_update.get("vehicle", {}).get("id", "")
    id_trip = trip_update.get("trip", {}).get("tripId", "")
    tren_detectado = coincide_tren(id_vehiculo) or coincide_tren(id_trip)

    if tren_detectado:
      retraso_seg = trip_update.get("delay")
      if retraso_seg is None and "stop_time_update" in trip_update:
        paradas = trip_update["stop_time_update"]
        if paradas:
          llegada = paradas[-1].get("arrival", {})
          retraso_seg = llegada.get("delay", 0)

      if retraso_seg is not None:
        mapa_retrasos[tren_detectado] = round(retraso_seg / 60)

  # Filtrar posiciones
  registros = []
  for entidad in posiciones_raw.get("entity", []):
    vehiculo = entidad.get("vehicle", {})

    id_vehiculo = vehiculo.get("vehicle", {}).get("id", "")
    id_trip = vehiculo.get("trip", {}).get("tripId", "")
    id_entidad = entidad.get("id", "")

    tren_detectado = (
        coincide_tren(id_vehiculo)
        or coincide_tren(id_trip)
        or coincide_tren(id_entidad)
    )

    if tren_detectado:
      retraso_min = mapa_retrasos.get(tren_detectado, 0)
      registros.append({
          "tren_id": tren_detectado,
          "estacion_actual": vehiculo.get("stopId", "En trayecto"),
          "retraso_minutos": retraso_min,
          "estado": vehiculo.get("currentStatus", "DESCONOCIDO"),
      })

  if registros:
    supabase.table("registros_trenes").insert(registros).execute()
    print(f"Éxito: {len(registros)} registros guardados: {registros}")
  else:
    print("Sin trenes extremeños activos en este momento.")


if __name__ == "__main__":
  ejecutar_captura()
