import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { apiUrl, time } from '../api'
import { useQuery } from '../useQuery'
import { usePolling } from '../usePolling'
import { Feedback, Icon, Notice, ago, classIcon, useNow } from '../components'

const DEMO_ORIGIN = { longitude: 78.4867, latitude: 17.3850 }
// Approximate landmark coordinates (longitude, latitude) for picking an origin without typing.
const PLACES = [
  { name: 'Hyderabad demo origin', longitude: 78.4867, latitude: 17.3850 },
  { name: 'Charminar', longitude: 78.4747, latitude: 17.3616 },
  { name: 'Hussain Sagar', longitude: 78.4735, latitude: 17.4239 },
  { name: 'Secunderabad Station', longitude: 78.5018, latitude: 17.4344 },
  { name: 'Ameerpet', longitude: 78.4483, latitude: 17.4375 },
  { name: 'Begumpet', longitude: 78.4675, latitude: 17.4447 },
  { name: 'Banjara Hills', longitude: 78.4483, latitude: 17.4126 },
  { name: 'HITEC City', longitude: 78.3816, latitude: 17.4435 },
  { name: 'Gachibowli', longitude: 78.3489, latitude: 17.4401 },
  { name: 'RGIA Airport', longitude: 78.4298, latitude: 17.2403 },
]

function metres(a, b) {
  const rad = Math.PI / 180, dLat = (b.latitude - a.latitude) * rad, dLon = (b.longitude - a.longitude) * rad
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.latitude * rad) * Math.cos(b.latitude * rad) * Math.sin(dLon / 2) ** 2
  return 12742000 * Math.asin(Math.sqrt(h))
}
function placeName(origin) {
  const near = PLACES.map(place => ({ place, distance: metres(place, origin) })).sort((a, b) => a.distance - b.distance)[0]
  if (near.distance < 60) return near.place.name
  return near.distance < 1500 ? 'Near ' + near.place.name : 'Dropped pin'
}
const round = value => Math.round(value * 10000) / 10000

function VehicleMap({ origin, items, selected, hovered, onSelect, onHover, onOrigin }) {
  const element = useRef(null)
  const map = useRef(null)
  const layers = useRef(null)
  const [tileError, setTileError] = useState(false)
  useEffect(() => {
    let current = true
    map.current = L.map(element.current, { zoomControl: false, dragging: !L.Browser.mobile, scrollWheelZoom: !L.Browser.mobile })
      .setView([origin.latitude, origin.longitude], 13)
    L.control.zoom({ position: 'bottomright' }).addTo(map.current)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).on('tileerror', () => { if (current) setTileError(true) }).addTo(map.current)
    layers.current = L.layerGroup().addTo(map.current)
    map.current.on('click', event => onOrigin({ longitude: round(event.latlng.lng), latitude: round(event.latlng.lat) }))
    const resize = window.ResizeObserver ? new ResizeObserver(() => map.current.invalidateSize()) : null
    resize?.observe(element.current)
    return () => { current = false; resize?.disconnect(); map.current.remove() }
  }, [])
  useEffect(() => { map.current.fitBounds(L.latLng([origin.latitude, origin.longitude]).toBounds(10500), { padding: [16, 16] }) }, [origin])
  useEffect(() => {
    const vehicle = items.find(item => item.vehicleId === selected)
    if (!vehicle) return
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    map.current.flyTo([vehicle.latitude, vehicle.longitude], Math.max(map.current.getZoom(), 14), still ? { animate: false } : { duration: 0.5 })
  }, [selected])
  useEffect(() => {
    layers.current.clearLayers()
    const point = [origin.latitude, origin.longitude]
    L.circle(point, { radius: 5000, color: 'rgba(255,255,255,.4)', weight: 1, fillColor: '#7CFFB2', fillOpacity: 0.04, interactive: false }).addTo(layers.current)
    const pin = L.marker(point, { draggable: true, autoPan: true, keyboard: false, zIndexOffset: 2000,
      icon: L.divIcon({ className: '', html: '<div class="origin-pin"><span></span></div>', iconSize: [28, 36], iconAnchor: [14, 34] }) })
      .addTo(layers.current).bindTooltip('Drag me, or tap the map', { direction: 'top', offset: [0, -30] })
    pin.on('dragend', () => { const at = pin.getLatLng(); onOrigin({ longitude: round(at.lng), latitude: round(at.lat) }) })
    items.forEach((vehicle, index) => {
      const label = document.createElement('span'); label.textContent = vehicle.licensePlate + ' · ' + (vehicle.distanceMeters / 1000).toFixed(2) + ' km'
      const active = selected === vehicle.vehicleId || hovered === vehicle.vehicleId
      L.marker([vehicle.latitude, vehicle.longitude], {
        icon: L.divIcon({ className: '', html: `<div class="car-marker${active ? ' active' : ''}">${index + 1}</div>`, iconSize: [26, 26] }),
        zIndexOffset: active ? 1000 : -index, keyboard: false,
      }).addTo(layers.current).bindTooltip(label, { direction: 'top', offset: [0, -14], permanent: selected === vehicle.vehicleId })
        .on('click', event => { L.DomEvent.stopPropagation(event); onSelect(vehicle.vehicleId) })
        .on('mouseover', () => onHover(vehicle.vehicleId)).on('mouseout', () => onHover(null))
    })
  }, [origin, items, selected, hovered, onSelect, onHover, onOrigin])
  return <><div ref={element} className="vehicle-map" aria-label="Map of vehicles within five kilometres. Tap the map or drag the pin to move the search origin." />
    {tileError && <p className="muted map-fallback" role="status">Map tiles could not load. Coordinates and distances are still available in the list.</p>}</>
}

export default function Nearby() {
  const [inputs, setInputs] = useState({ longitude: '78.4867', latitude: '17.3850' })
  const [origin, setOrigin] = useState(DEMO_ORIGIN)
  const [inputError, setInputError] = useState('')
  const [locating, setLocating] = useState(false)
  const [place, setPlace] = useState('')
  const [selected, setSelected] = useState(null)
  const [hovered, setHovered] = useState(null)
  const now = useNow(5000)
  const query = useQuery(apiUrl('/api/vehicles/nearby', { ...origin, limit: 50 }))
  usePolling(query.reload, query.loading)
  useEffect(() => { if (selected) document.getElementById('vehicle-' + selected)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }) }, [selected])
  const moveTo = useRef(null)
  moveTo.current = next => {
    setInputError(''); setSelected(null); setOrigin(next)
    setInputs({ longitude: String(next.longitude), latitude: String(next.latitude) })
  }
  const [onOrigin] = useState(() => next => moveTo.current(next))
  function apply(event) {
    event.preventDefault()
    const longitude = Number(inputs.longitude), latitude = Number(inputs.latitude)
    if (!inputs.longitude.trim() || !inputs.latitude.trim() || !Number.isFinite(longitude) || !Number.isFinite(latitude) || longitude < -180 || longitude > 180 || latitude < -90 || latitude > 90) {
      setInputError('Enter longitude from −180 to 180 and latitude from −90 to 90. The list below still shows the last valid origin.'); return
    }
    moveTo.current({ longitude, latitude })
  }
  function pickPlace(value) {
    setPlace(value)
    const match = PLACES.find(item => item.name.toLowerCase() === value.trim().toLowerCase())
    if (match) { moveTo.current({ longitude: match.longitude, latitude: match.latitude }); setPlace('') }
  }
  function locate() {
    if (!navigator.geolocation) { setInputError('This browser cannot share a location. Pick a place instead.'); return }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(position => {
      setLocating(false); moveTo.current({ longitude: round(position.coords.longitude), latitude: round(position.coords.latitude) })
    }, () => { setLocating(false); setInputError('Location is blocked or unavailable. Pick a place or tap the map instead.') }, { timeout: 8000, maximumAge: 60000 })
  }
  const items = query.data?.items || []
  const isDemoOrigin = origin.longitude === DEMO_ORIGIN.longitude && origin.latitude === DEMO_ORIGIN.latitude
  const farFromDemo = metres(origin, DEMO_ORIGIN) > 15000
  return <><div className="nearby-stage">
    <VehicleMap origin={origin} items={items} selected={selected} hovered={hovered} onSelect={setSelected} onHover={setHovered} onOrigin={onOrigin} />
    <h2 className="stage-title">Nearby vehicle map</h2>
    <section className="stage-panel stage-search" aria-label="Search origin">
      <label className="where">Where from?<input list="nearby-places" value={place} placeholder="Search a landmark, or tap the map" onChange={event => pickPlace(event.target.value)} /></label>
      <datalist id="nearby-places">{PLACES.map(item => <option key={item.name} value={item.name} />)}</datalist>
      <div className="origin-chips">
        <button type="button" className="small secondary" onClick={locate} disabled={locating}><Icon name="nearby" size={14} />{locating ? 'Locating…' : 'Use my location'}</button>
        <button type="button" className="small secondary" aria-pressed={isDemoOrigin} onClick={() => moveTo.current(DEMO_ORIGIN)}>Demo origin</button>
      </div>
      <p className="origin-name"><span className="pin-dot" />{placeName(origin)} · 5 km radius</p>
      <form className="coords" onSubmit={apply}>
        <label>Longitude<input inputMode="decimal" value={inputs.longitude} onChange={event => setInputs({ ...inputs, longitude: event.target.value })} /></label>
        <label>Latitude<input inputMode="decimal" value={inputs.latitude} onChange={event => setInputs({ ...inputs, latitude: event.target.value })} /></label>
        <button className="small secondary" disabled={query.loading}>Find vehicles</button>
      </form>
      {inputError && <Notice kind="error">{inputError}</Notice>}
      {farFromDemo && !query.loading && items.length === 0 && <button type="button" className="small" onClick={() => moveTo.current(DEMO_ORIGIN)}>Jump to the demo area</button>}
    </section>
    <section className="stage-panel stage-list"><div className="card-head" style={{ marginBottom: 6 }}><div><h2>Vehicles by distance</h2><p className="muted">{items.length} {items.length === 1 ? 'vehicle' : 'vehicles'} within 5 km · maximum 50</p></div>
      <span className="live-chip"><span className="live-dot" />{query.data ? 'Updated ' + ago(query.data.checkedAt || query.loadedAt, now) : 'Connecting…'}</span></div>
      <Feedback query={query} hasRows={items.length} empty="No fresh available vehicles within 5 km." hint="Demo pings expire after two hours. Try the demo origin." rows={4} />
      <ul className="vehicle-list">{items.map((row, index) => <li key={row.vehicleId} id={'vehicle-' + row.vehicleId}><button className={(selected === row.vehicleId ? 'selected' : '') + (hovered === row.vehicleId ? ' hovered' : '')} aria-pressed={selected === row.vehicleId}
        onClick={() => setSelected(row.vehicleId)} onMouseEnter={() => setHovered(row.vehicleId)} onMouseLeave={() => setHovered(null)}>
        <span className="vicon"><b>{index + 1}</b><Icon name={classIcon(row.class)} size={16} /></span>
        <span><strong>{row.licensePlate}</strong><small>{row.class} · pinged {ago(row.pingAt, now)}</small><small className="sr-only">Updated {time(row.pingAt)} · longitude {row.longitude.toFixed(5)}, latitude {row.latitude.toFixed(5)}</small></span>
        <span className="distance">{(row.distanceMeters / 1000).toFixed(2)}<small>km</small></span></button></li>)}</ul>
    </section></div>
    <div className="update-note"><span className="live-dot" />Auto update every 10 seconds while visible · Last successful update: {time(query.data?.checkedAt)}</div>
  </>
}
