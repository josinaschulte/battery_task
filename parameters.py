battery = {
    "capacity_kwh": 20.0,
    "soc_initial_kwh": 10.0,  # initial state of charge
    "soc_min_kwh": 2.0,  # minimal state of charge
    "soc_max_kwh": 20.0,  # maximal state of charge
    "charge_power_max_kw": 10.0,
    "discharge_power_max_kw": 10.0,
    "eta_charge": 0.95,  # charge efficiency
    "eta_discharge": 0.95,  # discharge efficiency
}

grid = {
    "demand_price_eur_per_kwh": [
        0.18,
        0.17,
        0.16,
        0.15,
        0.14,
        0.13,
        0.14,
        0.18,
        0.24,
        0.28,
        0.32,
        0.35,
        0.31,
        0.27,
        0.23,
        0.21,
        0.22,
        0.26,
        0.30,
        0.29,
        0.25,
        0.22,
        0.20,
        0.19,
    ],  # price per hour, spot preis/ergebnis day ahead markt
    "supply_price_eur_per_kwh": 0.20,
}