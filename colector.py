import json
import urllib.request

URL_POSICIONES = "https://gtfsrt.renfe.com/vehicle_positions_LD.json"
URL_RETRASOS = "https://gtfsrt.renfe.com/trip_updates_LD.json"


def descargar(url):
  req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
  with urllib.request.urlopen(req) as resp:
    return json.loads(resp.read().decode())


print("Descargando posiciones...")
pos = descargar(URL_POSICIONES)
entidades_pos = pos.get("entity", [])

print(f"Total vehículos emitiendo señal GPS ahora mismo: {len(entidades_pos)}")

trenes_activos = []
for e in entidades_pos:
  v = e.get("vehicle", {})
  vid = v.get("vehicle", {}).get("id")
  trip = v.get("trip", {}).get("tripId")
  eid = e.get("id")
  trenes_activos.append(f"VehiculoID: {vid} | TripId: {trip} | EntityID: {eid}")

# Mostramos los primeros 25 trenes para ver la estructura exacta
for t in trenes_activos[:25]:
  print(t)
