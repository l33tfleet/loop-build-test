# Planet data source

`data/planets.json` is a committed snapshot; the app never fetches data at runtime.

- Source: [NASA Planetary Fact Sheet](https://nssdc.gsfc.nasa.gov/planetary/factsheet/)
- Field: equatorial diameter, in kilometres (`diameter_km`)
- Snapshot taken: 2026-10-24

To refresh, copy the values from the fact sheet into `data/planets.json` and keep the
planets in order from the Sun. The expected values live in
`tests/regressions/test_planet_shelf.py`; cover changes with a new regression file.
