# NetGuardian Paris - Data Ingestion

This module collects and normalizes public network infrastructure
and Internet measurement data related to Paris and Île-de-France.

## Sources

- Paris Open Data — public Wi-Fi
- ANFR — radio sites and antennas
- ARCEP — fixed and mobile network data
- RIPE Atlas — probes, ping and traceroute measurements
- PeeringDB — facilities, networks and Internet Exchanges
- France-IX — Paris Internet Exchange data
- RIPEstat — ASN, BGP and routing information

## Data pipeline

Public APIs / Open Data
        |
        v
data_ingestion/
        |
        v
data/raw/
        |
        v
Normalization
        |
        v
data/interim/
        |
        v
Geospatial enrichment
        |
        v
data/processed/
        |
        v
PostgreSQL + PostGIS
        |
        v
NetGuardian Paris API
        |
        v
Interactive Network Map
