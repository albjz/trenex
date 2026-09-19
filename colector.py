import json
import os
import urllib.request
from supabase import create_client

# Credenciales de Supabase desde Secrets de GitHub
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Endpoints oficiales GTFS-RT de Renfe
URL_POSICIONES = "https://gtfsrt.renfe.com/vehicle_positions_LD.json"
URL_RETRASOS = "https://gtfsrt.renfe.com/trip_updates_LD.json"

# Catálogo completo oficial de trenes que dan servicio en Extremadura
# Los Alvia (19x/29x) se mapean con prefijo 04 (04190...) y los regionales con sus 5 dígitos
TRENES_EXTREMADURA = {
    # Alvia (Chamartín - Cáceres - Mérida - Badajoz)
    "04190",
    "04192",
    "04194",
    "04291",
    "04293",
    "04295",
    "04297",
    "04299",
    "00190",
    "00192",
    "00194",
    "00291",
    "00293",
    "00295",
    "00297",
    "00299",
    # Regionales Exprés y Media Distancia Madrid - Extremadura - Sevilla
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
    # Corredor Badajoz - Puertollano - Alcázar de San Juan
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


def descargar_json(url):
  req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
  with urllib.request.urlopen(req) as resp:
    return json.loads(resp.read().decode())


def extraer_id_tren(vehiculo_data):
  """Extrae el identificador de 5 dígitos del tren."""
  vid = str(vehiculo_data.get("vehicle", {}).get("id", ""))
  trip = str(vehiculo_data.get("trip", {}).get("tripId", ""))

  for candidato in [vid, trip[:5]]:
    if candidato in TRENES_EXTREMADURA:
      return candidato
  return None


def ejecutar_captura():
  print("Descargando telemetría oficial de Renfe...")
  try:
    posiciones = descargar_json(URL_POSICIONES)
    retrasos = descargar_json(URL_RETRASOS)
  except Exception as e:
    print(f"Error en descarga: {e}")
    return

  # 1. Mapear retrasos detectados
  mapa_retrasos = {}
  for entidad in retrasos.get("entity", []):
    trip_update = entidad.get("trip_update", {})
    tren_id = extraer_id_tren(trip_update)
    if tren_id:
      retraso_seg = trip_update.get("delay")
      if retraso_seg is None and "stop_time_update" in trip_update:
        paradas = trip_update["stop_time_update"]
        if paradas:
          retraso_seg = paradas[-1].get("arrival", {}).get("delay", 0)

      if retraso_seg is not None:
        mapa_retrasos[tren_id] = round(retraso_seg / 60)

  # 2. Mapear posiciones en vía
  registros = []
  for entidad in posiciones.get("entity", []):
    vehiculo = entidad.get("vehicle", {})
    tren_id = extraer_id_tren(vehiculo)

    if tren_id:
      # Limpiamos el nombre comercial para la web (ej: '04194' -> 'Alvia 194')
      nombre_comercial = (
          f"Alvia {tren_id[-3:]}"
          if tren_id.startswith(("0419", "0429", "0019", "0029"))
          else f"Tren {tren_id}"
      )

      registros.append({
          "tren_id": nombre_comercial,
          "estacion_actual": vehiculo.get("stopId", "En trayecto"),
          "retraso_minutos": mapa_retrasos.get(tren_id, 0),
          "estado": vehiculo.get("currentStatus", "CIRCULANDO"),
      })

  # 3. Guardar en Supabase
  if registros:
    supabase.table("registros_trenes").insert(registros).execute()
    print(f"Éxito: {len(registros)} trenes extremeños guardados.")
  else:
    print("Sin trenes extremeños circulando en este minuto.")


if __name__ == "__main__":
  ejecutar_captura()
