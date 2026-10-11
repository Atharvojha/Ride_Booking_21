import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { apiUrl, time } from '../api'
import { useQuery } from '../useQuery'
import { usePolling } from '../usePolling'
import { Feedback, Notice } from '../components'

function VehicleMap({ origin, items, selected, onSelect }) {
  const element = useRef(null)
  const map = useRef(null)
  const layers = useRef(null)
  const [tileError, setTileError] = useState(false)
  useEffect(() => {
    let current = true
    map.current = L.map(element.current).setView([origin.latitude, origin.longitude], 12)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).on('tileerror', () => { if (current) setTileError(true) }).addTo(map.current)
    layers.current = L.layerGroup().addTo(map.current)
    return () => { current = false; map.current.remove() }
  }, [])
  useEffect(() => {
    layers.current.clearLayers()
    const point = [origin.latitude, origin.longitude]
    L.circle(point, { radius: 5000, color: '#3567e8', weight: 1, fillOpacity: 0.05 }).addTo(layers.current)
    L.circleMarker(point, { radius: 8, color: '#17233f', fillColor: '#17233f', fillOpacity: 1 }).addTo(layers.current).bindTooltip('Search origin')
    items.forEach(vehicle => {
      const label = document.createElement('span'); label.textContent = vehicle.licensePlate
      L.circleMarker([vehicle.latitude, vehicle.longitude], { radius: selected === vehicle.vehicleId ? 11 : 7,
        color: selected === vehicle.vehicleId ? '#17233f' : '#3567e8', fillColor: '#3567e8', fillOpacity: 1,
      }).addTo(layers.current).bindTooltip(label).on('click', () => onSelect(vehicle.vehicleId))
    })
    map.current.fitBounds(L.latLng(point).toBounds(11000), { padding: [12, 12] })
  }, [origin, items, selected, onSelect])
  return <><div ref={element} className="vehicle-map" aria-label="Map of vehicles within five kilometres" />
    {tileError && <p className="muted">Map tiles could not load. Coordinates and distances are still available in the list.</p>}</>
}

export default function Nearby() {
  const [inputs, setInputs] = useState({ longitude: '78.4867', latitude: '17.3850' })
  const [origin, setOrigin] = useState({ longitude: 78.4867, latitude: 17.3850 })
  const [inputError, setInputError] = useState('')
  const [selected, setSelected] = useState(null)
  const query = useQuery(apiUrl('/api/vehicles/nearby', { ...origin, limit: 50 }))
  usePolling(query.reload, query.loading)
  function apply(event) {
    event.preventDefault()
    const longitude = Number(inputs.longitude), latitude = Number(inputs.latitude)
    if (!inputs.longitude.trim() || !inputs.latitude.trim() || !Number.isFinite(longitude) || !Number.isFinite(latitude) || longitude < -180 || longitude > 180 || latitude < -90 || latitude > 90) {
      setInputError('Enter longitude from −180 to 180 and latitude from −90 to 90.'); return
    }
    setInputError(''); setSelected(null); setOrigin({ longitude, latitude })
  }
  const items = query.data?.items || []
  return <><section className="card"><form className="filters" onSubmit={apply}>
    <label>Longitude<input inputMode="decimal" value={inputs.longitude} onChange={event => setInputs({ ...inputs, longitude: event.target.value })} /></label>
    <label>Latitude<input inputMode="decimal" value={inputs.latitude} onChange={event => setInputs({ ...inputs, latitude: event.target.value })} /></label>
    <button disabled={query.loading}>Find vehicles</button><button className="secondary" type="button" disabled={query.loading} onClick={query.reload}>Refresh positions</button></form>
    {inputError && <Notice kind="error">{inputError}</Notice>}<p className="muted">Hyderabad demo origin · 5 km radius · Fresh positions from the last two hours.</p></section>
    <div className="map-layout"><section className="card map-card"><h2>Nearby vehicle map</h2><VehicleMap origin={origin} items={items} selected={selected} onSelect={setSelected} /></section>
      <section className="card"><h2>Vehicles by distance</h2><p className="muted">{items.length} vehicles shown · maximum 50</p>
        <Feedback query={query} hasRows={items.length} empty="No fresh available vehicles within 5 km. Demo pings expire after two hours." />
        <ul className="vehicle-list">{items.map(row => <li key={row.vehicleId}><button className={selected === row.vehicleId ? 'selected' : ''} aria-pressed={selected === row.vehicleId} onClick={() => setSelected(row.vehicleId)}><strong>{row.licensePlate}<span>{(row.distanceMeters / 1000).toFixed(2)} km</span></strong><small>{row.class} · Updated {time(row.pingAt)}</small><small>{row.latitude.toFixed(5)}, {row.longitude.toFixed(5)}</small></button></li>)}</ul>
      </section></div><div className="update-note"><span className="live-dot" />Auto update every 10 seconds while visible · Last successful update: {time(query.data?.checkedAt)}</div>
  </>
}
