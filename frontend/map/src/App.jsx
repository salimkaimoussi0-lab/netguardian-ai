import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";

maplibregl.setWorkerUrl(maplibreWorkerUrl);

import BgpTopology from "./BgpTopology";

const PARIS_CENTER = [2.3522, 48.8566];

function esc(value, fallback = "Non disponible") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function arrayText(value, limit = null) {
  let values = [];

  if (Array.isArray(value)) {
    values = value;
  } else if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);

      if (Array.isArray(parsed)) {
        values = parsed;
      } else {
        return value;
      }
    } catch {
      return value;
    }
  } else {
    return "Non disponible";
  }

  if (!values.length) {
    return "Non disponible";
  }

  if (limit && values.length > limit) {
    return (
      values.slice(0, limit).join(", ") +
      ` … (+${values.length - limit})`
    );
  }

  return values.join(", ");
}

function validPoint(feature) {
  if (feature?.geometry?.type !== "Point") {
    return null;
  }

  const coordinates = feature.geometry.coordinates;

  if (
    !Array.isArray(coordinates) ||
    coordinates.length < 2
  ) {
    return null;
  }

  const longitude = Number(coordinates[0]);
  const latitude = Number(coordinates[1]);

  if (
    !Number.isFinite(longitude) ||
    !Number.isFinite(latitude)
  ) {
    return null;
  }

  return {
    longitude,
    latitude
  };
}

async function fetchGeoJSON(path, label) {
  const response = await fetch(path);

  if (!response.ok) {
    throw new Error(
      `${label}: HTTP ${response.status}`
    );
  }

  const data = await response.json();

  return Array.isArray(data.features)
    ? data.features
    : [];
}

function App() {
  const mapContainer = useRef(null);
  const mapRef = useRef(null);

  const wifiMarkersRef = useRef([]);
  const anfrMarkersRef = useRef([]);
  const ripeMarkersRef = useRef([]);
  const peeringMarkersRef = useRef([]);
  const franceIxMarkersRef = useRef([]);

  const [wifiCount, setWifiCount] = useState(0);
  const [anfrCount, setAnfrCount] = useState(0);
  const [ripeCount, setRipeCount] = useState(0);
  const [anchorCount, setAnchorCount] = useState(0);
  const [peeringCount, setPeeringCount] = useState(0);
  const [franceIxCount, setFranceIxCount] = useState(0);

  const [wifiVisible, setWifiVisible] = useState(true);
  const [anfrVisible, setAnfrVisible] = useState(true);
  const [ripeVisible, setRipeVisible] = useState(true);
  const [peeringVisible, setPeeringVisible] = useState(true);
  const [franceIxVisible, setFranceIxVisible] = useState(true);

  const [arcepVisible, setArcepVisible] = useState(true);
  const [arcepCount, setArcepCount] = useState(0);

  const [arcepOperator, setArcepOperator] = useState("all");
  const [arcepTechnology, setArcepTechnology] = useState("all");

  const [arcepOnly3500, setArcepOnly3500] = useState(false);
  const [arcepOnlyAnfr, setArcepOnlyAnfr] = useState(false);

  const [objectFilter, setObjectFilter] = useState("all");
  const [objectsOpen, setObjectsOpen] = useState(false);

  const [status, setStatus] = useState("Chargement...");

  const [bgpVisible, setBgpVisible] = useState(false);

  useEffect(() => {
    if (mapRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: mapContainer.current,

      center: PARIS_CENTER,

      zoom: 11,

      style: {
        version: 8,

        sources: {
          osm: {
            type: "raster",

            tiles: [
              "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            ],

            tileSize: 256,

            attribution: "© OpenStreetMap contributors"
          }
        },

        layers: [
          {
            id: "osm",
            type: "raster",
            source: "osm"
          }
        ]
      }
    });

    mapRef.current = map;

    map.addControl(
      new maplibregl.NavigationControl(),
      "top-right"
    );

    map.addControl(
      new maplibregl.ScaleControl({
        maxWidth: 120,
        unit: "metric"
      }),
      "bottom-right"
    );

    mapRef.current = map;

    map.on("load", async () => {
      try {
        const bounds =
          new maplibregl.LngLatBounds();

        /*
         * ==================================================
         * PARIS WI-FI
         * ==================================================
         */

        const wifiFeatures =
          await fetchGeoJSON(
            "/data/paris_wifi_sites.geojson",
            "Paris Wi-Fi"
          );

        let validWifi = 0;

        for (const feature of wifiFeatures) {
          const point = validPoint(feature);

          if (!point) {
            continue;
          }

          const {
            longitude,
            latitude
          } = point;

          const p =
            feature.properties ?? {};

          const element =
            document.createElement("div");

          element.className =
            "network-marker wifi-marker";

          const popup =
            new maplibregl.Popup({
              offset: 18
            }).setHTML(`
              <div class="network-popup">

                <div class="popup-badge wifi-badge">
                  PARIS WI-FI
                </div>

                <h3>
                  ${esc(p.name, "Site Wi-Fi")}
                </h3>

                <div class="popup-row">
                  <strong>Adresse</strong>
                  <span>
                    ${esc(p.address)}
                    ${esc(p.postal_code, "")}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>État</strong>
                  <span>${esc(p.status)}</span>
                </div>

                <div class="popup-row">
                  <strong>Bornes</strong>
                  <span>
                    ${esc(p.wifi_access_points)}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Source</strong>
                  <span>
                    ${esc(p.source, "Paris Open Data")}
                  </span>
                </div>

              </div>
            `);

          const marker =
            new maplibregl.Marker({
              element,
              anchor: "center"
            })
              .setLngLat([
                longitude,
                latitude
              ])
              .setPopup(popup)
              .addTo(map);

          wifiMarkersRef.current.push({
            marker,
            element,
            category: "wifi"
          });

          bounds.extend([
            longitude,
            latitude
          ]);

          validWifi += 1;
        }

        setWifiCount(validWifi);

        /*
         * ==================================================
         * ANFR
         * ==================================================
         */

        const anfrFeatures =
          await fetchGeoJSON(
            "/data/anfr_paris_sites.geojson",
            "ANFR"
          );

        let validAnfr = 0;

        for (const feature of anfrFeatures) {
          const point = validPoint(feature);

          if (!point) {
            continue;
          }

          const {
            longitude,
            latitude
          } = point;

          const p =
            feature.properties ?? {};

          const generations =
            arrayText(p.generations);

          const operators =
            arrayText(p.operators);

          const systems =
            arrayText(
              p.systems,
              8
            );

          const statuses =
            arrayText(p.statuses);

          const has5G =
            generations
              .toUpperCase()
              .includes("5G");

          const category =
            has5G
              ? "anfr-5g"
              : "anfr-legacy";

          const element =
            document.createElement("div");

          element.className =
            "network-marker anfr-marker";

          if (has5G) {
            element.classList.add(
              "anfr-5g"
            );
          }

          const popup =
            new maplibregl.Popup({
              offset: 18,
              maxWidth: "390px"
            }).setHTML(`
              <div class="network-popup">

                <div class="popup-badge anfr-badge">
                  ${
                    has5G
                      ? "ANFR 5G SITE"
                      : "ANFR MOBILE SITE"
                  }
                </div>

                <h3>
                  Support ${esc(p.sup_id)}
                </h3>

                <div class="popup-row">
                  <strong>Opérateurs</strong>
                  <span>${esc(operators)}</span>
                </div>

                <div class="popup-row">
                  <strong>Technologies</strong>
                  <span>${esc(generations)}</span>
                </div>

                <div class="popup-row">
                  <strong>Systèmes</strong>
                  <span>${esc(systems)}</span>
                </div>

                <div class="popup-row">
                  <strong>Statut</strong>
                  <span>${esc(statuses)}</span>
                </div>

                <div class="popup-row">
                  <strong>Radio systems</strong>
                  <span>
                    ${esc(p.system_count)}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Source</strong>
                  <span>ANFR Open Data</span>
                </div>

              </div>
            `);

          const marker =
            new maplibregl.Marker({
              element,
              anchor: "center"
            })
              .setLngLat([
                longitude,
                latitude
              ])
              .setPopup(popup)
              .addTo(map);

          anfrMarkersRef.current.push({
            marker,
            element,
            category
          });

          bounds.extend([
            longitude,
            latitude
          ]);

          validAnfr += 1;
        }

        setAnfrCount(validAnfr);


        /*
         * ==================================================
         * ARCEP MOBILE WEBGL
         * ==================================================
         */

        console.log(
          "[ARCEP] chargement GeoJSON..."
        );


        const arcepResponse =
          await fetch(
            "/data/arcep_mobile_sites.geojson"
          );


        if (!arcepResponse.ok) {
          throw new Error(
            `ARCEP HTTP ${arcepResponse.status}`
          );
        }


        const arcepData =
          await arcepResponse.json();


        const arcepFeatures =
          Array.isArray(
            arcepData.features
          )
            ? arcepData.features
            : [];


        console.log(
          "[ARCEP] features:",
          arcepFeatures.length
        );


        setArcepCount(
          arcepFeatures.length
        );


        /*
         * Nettoyage défensif.
         *
         * On ne garde que les vrais Point
         * avec longitude / latitude numériques.
         */

        const validArcepFeatures =
          arcepFeatures.filter(
            feature => {

              const coordinates =
                feature
                  ?.geometry
                  ?.coordinates;


              if (
                feature?.geometry?.type
                !== "Point"
              ) {
                return false;
              }


              if (
                !Array.isArray(
                  coordinates
                )
                ||
                coordinates.length < 2
              ) {
                return false;
              }


              const lon =
                Number(
                  coordinates[0]
                );

              const lat =
                Number(
                  coordinates[1]
                );


              return (
                Number.isFinite(lon)
                &&
                Number.isFinite(lat)
                &&
                lon >= -180
                &&
                lon <= 180
                &&
                lat >= -90
                &&
                lat <= 90
              );
            }
          );


        console.log(
          "[ARCEP] valid points:",
          validArcepFeatures.length
        );


        const cleanArcepData = {
          type:
            "FeatureCollection",

          features:
            validArcepFeatures
        };


        /*
         * SOURCE
         */

        if (
          map.getSource(
            "arcep-mobile"
          )
        ) {
          map.removeSource(
            "arcep-mobile"
          );
        }


        map.addSource(
          "arcep-mobile",
          {
            type:
              "geojson",

            data:
              cleanArcepData
          }
        );


        /*
         * LAYER
         *
         * Important :
         * aucune propriété tableau n'est utilisée
         * pour le rendu.
         *
         * Seulement :
         * - has_5g_3500
         * - has_5g
         * - has_4g
         * - anfr_match
         */

        map.addLayer({
          id:
            "arcep-mobile-sites",

          type:
            "circle",

          source:
            "arcep-mobile",

          minzoom:
            0,

          maxzoom:
            24,

          layout: {
            visibility:
              "visible"
          },

          paint: {

            "circle-radius": [
              "interpolate",
              ["linear"],
              ["zoom"],

              5, 1,
              7, 1.3,
              9, 1.8,
              11, 2.6,
              13, 3.8,
              15, 5.5,
              17, 7
            ],


            "circle-color": [
              "case",

              [
                "==",
                [
                  "get",
                  "has_5g_3500"
                ],
                true
              ],
              "#d946ef",

              [
                "==",
                [
                  "get",
                  "has_5g"
                ],
                true
              ],
              "#8b5cf6",

              [
                "==",
                [
                  "get",
                  "has_4g"
                ],
                true
              ],
              "#06b6d4",

              "#f59e0b"
            ],


            "circle-opacity":
              0.68,


            "circle-stroke-width": [
              "case",

              [
                "==",
                [
                  "get",
                  "anfr_match"
                ],
                true
              ],
              1.5,

              0.5
            ],


            "circle-stroke-color":
              "#ffffff",


            "circle-stroke-opacity":
              0.9
          }
        });



        /*
         * Force la couche au sommet du style.
         */

        map.moveLayer(
          "arcep-mobile-sites"
        );


        console.log(
          "[ARCEP] source:",
          Boolean(
            map.getSource(
              "arcep-mobile"
            )
          )
        );


        console.log(
          "[ARCEP] layer:",
          Boolean(
            map.getLayer(
              "arcep-mobile-sites"
            )
          )
        );


        /*
         * POPUP
         */

        map.on(
          "click",
          "arcep-mobile-sites",
          event => {

            const feature =
              event.features?.[0];


            if (!feature) {
              return;
            }


            const p =
              feature.properties ?? {};


            const yes =
              value =>
                value === true
                ||
                value === "true";


            const technologies = [
              yes(p.has_2g)
                ? "2G"
                : null,

              yes(p.has_3g)
                ? "3G"
                : null,

              yes(p.has_4g)
                ? "4G"
                : null,

              yes(p.has_5g)
                ? "5G"
                : null
            ]
              .filter(Boolean)
              .join(" / ");


            const coordinates =
              feature.geometry
                ?.coordinates;


            if (
              !Array.isArray(
                coordinates
              )
            ) {
              return;
            }


            new maplibregl.Popup({
              maxWidth:
                "420px"
            })
              .setLngLat(
                coordinates
              )
              .setHTML(`
                <div class="network-popup">

                  <div class="popup-badge arcep-badge">
                    ARCEP MOBILE
                  </div>

                  <h3>
                    ${esc(
                      p.operator,
                      "Site mobile"
                    )}
                  </h3>


                  <div class="popup-row">
                    <strong>
                      Technologies
                    </strong>

                    <span>
                      ${esc(
                        technologies,
                        "—"
                      )}
                    </span>
                  </div>


                  <div class="popup-row">
                    <strong>
                      5G 3500 MHz
                    </strong>

                    <span>
                      ${
                        yes(
                          p.has_5g_3500
                        )
                          ? "Oui"
                          : "Non"
                      }
                    </span>
                  </div>


                  <div class="popup-row">
                    <strong>
                      Correspondance ANFR
                    </strong>

                    <span>
                      ${
                        yes(
                          p.anfr_match
                        )
                          ? "Oui"
                          : "Non"
                      }
                    </span>
                  </div>


                  <div class="popup-row">
                    <strong>
                      Commune
                    </strong>

                    <span>
                      ${esc(
                        p.cities,
                        "—"
                      )}
                    </span>
                  </div>


                  <div class="popup-row">
                    <strong>
                      Ouverture 5G
                    </strong>

                    <span>
                      ${esc(
                        p.first_5g_opening_date,
                        "—"
                      )}
                    </span>
                  </div>


                  <div class="popup-row">
                    <strong>
                      Source
                    </strong>

                    <span>
                      ARCEP - Mon Réseau Mobile
                    </span>
                  </div>

                </div>
              `)
              .addTo(
                map
              );
          }
        );


        map.on(
          "mouseenter",
          "arcep-mobile-sites",
          () => {
            map.getCanvas()
              .style.cursor =
                "pointer";
          }
        );


        map.on(
          "mouseleave",
          "arcep-mobile-sites",
          () => {
            map.getCanvas()
              .style.cursor =
                "";
          }
        );


        /*
         * ==================================================
         * RIPE ATLAS
         * ==================================================
         */

        const ripeFeatures =
          await fetchGeoJSON(
            "/data/ripe_atlas_paris_probes.geojson",
            "RIPE Atlas"
          );

        let validRipe = 0;
        let validAnchors = 0;

        for (const feature of ripeFeatures) {
          const point = validPoint(feature);

          if (!point) {
            continue;
          }

          const {
            longitude,
            latitude
          } = point;

          const p =
            feature.properties ?? {};

          const isAnchor =
            p.is_anchor === true ||
            p.is_anchor === "true";

          const category =
            isAnchor
              ? "ripe-anchor"
              : "ripe-probe";

          const element =
            document.createElement("div");

          element.className =
            "network-marker ripe-marker";

          if (isAnchor) {
            element.classList.add(
              "ripe-anchor"
            );

            validAnchors += 1;
          }

          const popup =
            new maplibregl.Popup({
              offset: 18,
              maxWidth: "390px"
            }).setHTML(`
              <div class="network-popup">

                <div class="popup-badge ripe-badge">
                  ${
                    isAnchor
                      ? "RIPE ATLAS ANCHOR"
                      : "RIPE ATLAS PROBE"
                  }
                </div>

                <h3>
                  Probe #${esc(p.probe_id)}
                </h3>

                <div class="popup-row">
                  <strong>Statut</strong>
                  <span>${esc(p.status)}</span>
                </div>

                <div class="popup-row">
                  <strong>ASN IPv4</strong>
                  <span>${esc(p.asn_v4)}</span>
                </div>

                <div class="popup-row">
                  <strong>ASN IPv6</strong>
                  <span>${esc(p.asn_v6)}</span>
                </div>

                <div class="popup-row">
                  <strong>Public</strong>
                  <span>
                    ${p.is_public ? "Oui" : "Non"}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Anchor</strong>
                  <span>
                    ${isAnchor ? "Oui" : "Non"}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Position</strong>
                  <span>
                    Approximative / obfusquée
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Source</strong>
                  <span>RIPE Atlas</span>
                </div>

              </div>
            `);

          const marker =
            new maplibregl.Marker({
              element,
              anchor: "center"
            })
              .setLngLat([
                longitude,
                latitude
              ])
              .setPopup(popup)
              .addTo(map);

          ripeMarkersRef.current.push({
            marker,
            element,
            category
          });

          bounds.extend([
            longitude,
            latitude
          ]);

          validRipe += 1;
        }

        setRipeCount(validRipe);
        setAnchorCount(validAnchors);

        /*
         * ==================================================
         * PEERINGDB
         * ==================================================
         */

        const peeringFeatures =
          await fetchGeoJSON(
            "/data/peeringdb_paris_facilities.geojson",
            "PeeringDB"
          );

        let validPeering = 0;

        for (const feature of peeringFeatures) {
          const point = validPoint(feature);

          if (!point) {
            continue;
          }

          const {
            longitude,
            latitude
          } = point;

          const p =
            feature.properties ?? {};

          const networkCount =
            Number(p.network_count) || 0;

          const ixCount =
            Number(p.ix_count) || 0;

          /*
           * Taille proportionnelle au nombre
           * de réseaux présents.
           */
          const size = Math.max(
            14,
            Math.min(
              34,
              12 +
              Math.log2(
                networkCount + 1
              ) * 4
            )
          );

          const element =
            document.createElement("div");

          element.className =
            "network-marker peeringdb-marker";

          if (ixCount > 0) {
            element.classList.add(
              "peeringdb-has-ix"
            );
          }

          element.style.width =
            `${size}px`;

          element.style.height =
            `${size}px`;

          element.title =
            `${esc(p.name)} — ${networkCount} networks`;

          const networks =
            arrayText(
              p.network_names,
              12
            );

          const asns =
            arrayText(
              p.network_asns,
              15
            );

          const exchanges =
            arrayText(
              p.ix_names,
              10
            );

          const popup =
            new maplibregl.Popup({
              offset: 22,
              maxWidth: "440px"
            }).setHTML(`
              <div class="network-popup">

                <div class="popup-badge peeringdb-badge">
                  PEERINGDB FACILITY
                </div>

                <h3>
                  ${esc(p.name, "Datacenter")}
                </h3>

                <div class="popup-row">
                  <strong>Organisation</strong>
                  <span>
                    ${esc(p.org_name)}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Ville</strong>
                  <span>
                    ${esc(p.city)}
                    ${esc(p.zipcode, "")}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Adresse</strong>
                  <span>
                    ${esc(p.address1)}
                    ${esc(p.address2, "")}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Réseaux</strong>
                  <span>
                    ${networkCount}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>ASN</strong>
                  <span>
                    ${esc(asns)}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Networks</strong>
                  <span>
                    ${esc(networks)}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>IX présents</strong>
                  <span>
                    ${ixCount}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Exchanges</strong>
                  <span>
                    ${esc(exchanges)}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Distance Paris</strong>
                  <span>
                    ${esc(p.distance_to_paris_km)} km
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Statut</strong>
                  <span>
                    ${esc(p.status)}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Source</strong>
                  <span>PeeringDB</span>
                </div>

              </div>
            `);

          const marker =
            new maplibregl.Marker({
              element,
              anchor: "center"
            })
              .setLngLat([
                longitude,
                latitude
              ])
              .setPopup(popup)
              .addTo(map);

          peeringMarkersRef.current.push({
            marker,
            element,
            category:
              "peeringdb-facility"
          });

          bounds.extend([
            longitude,
            latitude
          ]);

          validPeering += 1;
        }

        setPeeringCount(
          validPeering
        );

        /*
         * ==================================================
         * FRANCE-IX
         * ==================================================
         */

        const franceIxFeatures =
          await fetchGeoJSON(
            "/data/france_ix_paris_pops.geojson",
            "France-IX"
          );

        let validFranceIx = 0;

        for (const feature of franceIxFeatures) {
          const point = validPoint(feature);

          if (!point) {
            continue;
          }

          const {
            longitude,
            latitude
          } = point;

          const p =
            feature.properties ?? {};

          const memberCount =
            Number(
              p.colocated_member_count
            ) || 0;

          const services =
            arrayText(
              p.services,
              10
            );

          const element =
            document.createElement("div");

          element.className =
            "network-marker franceix-marker";

          /*
           * On augmente légèrement la taille
           * selon le nombre de réseaux
           * colocalisés au PoP.
           */
          const size = Math.max(
            18,
            Math.min(
              34,
              18 +
              Math.log2(
                memberCount + 1
              ) * 2
            )
          );

          element.style.width =
            `${size}px`;

          element.style.height =
            `${size}px`;

          element.title =
            `France-IX - ${p.name ?? "PoP"}`;

          const matched =
            p.matched_netguardian_peeringdb === true ||
            p.matched_netguardian_peeringdb === "true";

          const popup =
            new maplibregl.Popup({
              offset: 24,
              maxWidth: "430px"
            }).setHTML(`
              <div class="network-popup">

                <div class="popup-badge franceix-badge">
                  FRANCE-IX POP
                </div>

                <h3>
                  ${esc(p.name, "France-IX PoP")}
                </h3>

                <div class="popup-row">
                  <strong>Facility ID</strong>
                  <span>
                    ${esc(p.facility_id)}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Organisation</strong>
                  <span>
                    ${esc(p.organization)}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Ville</strong>
                  <span>
                    ${esc(p.city)}
                    ${esc(p.postal_code, "")}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Adresse</strong>
                  <span>
                    ${esc(p.address1)}
                    ${esc(p.address2, "")}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Service France-IX</strong>
                  <span>
                    ${esc(services)}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Réseaux colocalisés</strong>
                  <span>
                    ${memberCount}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>PeeringDB match</strong>
                  <span>
                    ${matched ? "Oui" : "Non"}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Relation</strong>
                  <span>
                    ${esc(
                      p.relation_type,
                      "IX_PRESENT_AT_FACILITY"
                    )}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Source</strong>
                  <span>
                    ${esc(
                      p.source,
                      "PeeringDB / France-IX"
                    )}
                  </span>
                </div>

                <div class="popup-row">
                  <strong>Preuve</strong>
                  <span>
                    ${esc(
                      p.evidence_type,
                      "PUBLIC_DECLARATION"
                    )}
                  </span>
                </div>

              </div>
            `);

          const franceIxMarker =
            new maplibregl.Marker({
              element,
              anchor: "center"
            })
              .setLngLat([
                longitude,
                latitude
              ])
              .setPopup(popup)
              .addTo(map);

          franceIxMarkersRef.current.push({
            marker: franceIxMarker,
            element,
            category:
              "franceix-pop"
          });

          bounds.extend([
            longitude,
            latitude
          ]);

          validFranceIx += 1;
        }

        setFranceIxCount(
          validFranceIx
        );

        /*
         * ==================================================
         * INITIAL MAP FIT
         * ==================================================
         */

        if (!bounds.isEmpty()) {
          map.fitBounds(
            bounds,
            {
              padding: 60,
              maxZoom: 12.2,
              duration: 1200
            }
          );
        }

        setStatus(
          "Réseau Paris chargé"
        );

        console.log(
          "[NetGuardian] Wi-Fi:",
          validWifi
        );

        console.log(
          "[NetGuardian] ANFR:",
          validAnfr
        );

        console.log(
          "[NetGuardian] RIPE Atlas:",
          validRipe
        );

        console.log(
          "[NetGuardian] RIPE Anchors:",
          validAnchors
        );

        console.log(
          "[NetGuardian] PeeringDB facilities:",
          validPeering
        );

        console.log(
          "[NetGuardian] France-IX PoPs:",
          validFranceIx
        );

      } catch (error) {
        console.error(
          "[NetGuardian]",
          error
        );

        setStatus(
          "Erreur de chargement"
        );
      }
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  /*
   * ==================================================
   * VISIBILITY + NETWORK OBJECT FILTER
   * ==================================================
   */

  useEffect(() => {
    for (
      const item
      of wifiMarkersRef.current
    ) {
      const allowed =
        objectFilter === "all" ||
        objectFilter === "wifi";

      item.element.style.display =
        wifiVisible && allowed
          ? "block"
          : "none";
    }

    for (
      const item
      of anfrMarkersRef.current
    ) {
      const allowed =
        objectFilter === "all" ||
        objectFilter === item.category;

      item.element.style.display =
        anfrVisible && allowed
          ? "block"
          : "none";
    }

    for (
      const item
      of ripeMarkersRef.current
    ) {
      const allowed =
        objectFilter === "all" ||
        objectFilter === item.category;

      item.element.style.display =
        ripeVisible && allowed
          ? "block"
          : "none";
    }

    for (
      const item
      of peeringMarkersRef.current
    ) {
      const allowed =
        objectFilter === "all" ||
        objectFilter ===
          "peeringdb-facility";

      item.element.style.display =
        peeringVisible && allowed
          ? "block"
          : "none";
    }

    for (
      const item
      of franceIxMarkersRef.current
    ) {
      const allowed =
        objectFilter === "all" ||
        objectFilter ===
          "franceix-pop";

      item.element.style.display =
        franceIxVisible && allowed
          ? "block"
          : "none";
    }

  }, [
    objectFilter,
    wifiVisible,
    anfrVisible,
    ripeVisible,
    peeringVisible,
    franceIxVisible,
    wifiCount,
    anfrCount,
    ripeCount,
    peeringCount,
    franceIxCount
  ]);

  function selectObjectFilter(filter) {
    setObjectFilter(filter);

    if (filter === "all") {
      setWifiVisible(true);
      setAnfrVisible(true);
      setRipeVisible(true);
      setPeeringVisible(true);
      setFranceIxVisible(true);
    }

    if (filter === "wifi") {
      setWifiVisible(true);
      setAnfrVisible(false);
      setRipeVisible(false);
      setPeeringVisible(false);
      setFranceIxVisible(false);
    }

    if (
      filter === "anfr-legacy" ||
      filter === "anfr-5g"
    ) {
      setWifiVisible(false);
      setAnfrVisible(true);
      setRipeVisible(false);
      setPeeringVisible(false);
      setFranceIxVisible(false);
    }

    if (
      filter === "ripe-probe" ||
      filter === "ripe-anchor"
    ) {
      setWifiVisible(false);
      setAnfrVisible(false);
      setRipeVisible(true);
      setPeeringVisible(false);
      setFranceIxVisible(false);
    }

    if (
      filter ===
      "peeringdb-facility"
    ) {
      setWifiVisible(false);
      setAnfrVisible(false);
      setRipeVisible(false);
      setPeeringVisible(true);
      setFranceIxVisible(false);
    }

    if (
      filter === "franceix-pop"
    ) {
      setWifiVisible(false);
      setAnfrVisible(false);
      setRipeVisible(false);
      setPeeringVisible(false);
      setFranceIxVisible(true);
    }

    setObjectsOpen(false);
  }

  function getFilterLabel() {
    switch (objectFilter) {
      case "wifi":
        return "Paris Wi-Fi";

      case "anfr-legacy":
        return "ANFR 2G/3G/4G";

      case "anfr-5g":
        return "ANFR 5G";

      case "ripe-probe":
        return "RIPE Probes";

      case "ripe-anchor":
        return "RIPE Anchors";

      case "peeringdb-facility":
        return "PeeringDB";

      case "franceix-pop":
        return "France-IX";

      case "arcep-mobile":
        return "ARCEP Mobile";

      default:
        return "Tous";
    }
  }

  const totalNodes =
    wifiCount +
    anfrCount +
    ripeCount +
    peeringCount +
    franceIxCount +
    arcepCount;

  /*
   * ==========================================================
   * ARCEP MOBILE - VISIBILITY + FILTERS
   * ==========================================================
   */

  useEffect(() => {

    const map =
      mapRef.current;


    if (!map) {
      return;
    }


    const layerId =
      "arcep-mobile-sites";


    if (
      !map.getLayer(
        layerId
      )
    ) {
      return;
    }


    /*
     * VISIBILITY
     */

    const objectAllowed =
      objectFilter === "all"
      ||
      objectFilter ===
        "arcep-mobile";


    const visible =
      arcepVisible
      &&
      objectAllowed;


    map.setLayoutProperty(
      layerId,
      "visibility",
      visible
        ? "visible"
        : "none"
    );


    /*
     * FILTERS
     */

    const conditions = [];


    if (
      arcepOperator !== "all"
    ) {
      conditions.push([
        "==",
        [
          "get",
          "operator"
        ],
        arcepOperator
      ]);
    }


    if (
      arcepTechnology !== "all"
    ) {

      const field =
        `has_${arcepTechnology.toLowerCase()}`;


      conditions.push([
        "==",
        [
          "get",
          field
        ],
        true
      ]);
    }


    if (
      arcepOnly3500
    ) {
      conditions.push([
        "==",
        [
          "get",
          "has_5g_3500"
        ],
        true
      ]);
    }


    if (
      arcepOnlyAnfr
    ) {
      conditions.push([
        "==",
        [
          "get",
          "anfr_match"
        ],
        true
      ]);
    }


    const filter =
      conditions.length
        ? [
            "all",
            ...conditions
          ]
        : null;


    map.setFilter(
      layerId,
      filter
    );


    /*
     * Toujours garder ARCEP au-dessus.
     */

    if (visible) {
      map.moveLayer(
        layerId
      );
    }


  }, [
    objectFilter,
    arcepVisible,
    arcepOperator,
    arcepTechnology,
    arcepOnly3500,
    arcepOnlyAnfr
  ]);






  return (
    <div className="app">

      <header className="topbar">

        <div>
          <div className="eyebrow">
            NETWORK INTELLIGENCE
          </div>

          <h1>
            NetGuardian Paris
          </h1>
        </div>

        <div className="system-status">

          <span className="green-dot" />

          <div>
            <strong>
              {status}
            </strong>

            <small>
              {totalNodes} network nodes
            </small>
          </div>

        </div>

      </header>

      <main className="workspace">

        <aside className="sidebar">

          <h2>
            Network Layers
          </h2>

          <button
            className={
              wifiVisible
                ? "layer layer-button active"
                : "layer layer-button"
            }
            onClick={() =>
              setWifiVisible(!wifiVisible)
            }
          >
            <span>📶</span>

            <div>
              <strong>
                Paris Wi-Fi
              </strong>

              <small>
                {wifiCount} sites
              </small>
            </div>

            <span className="layer-state">
              {wifiVisible ? "ON" : "OFF"}
            </span>
          </button>

          <button
            className={
              anfrVisible
                ? "layer layer-button anfr-active"
                : "layer layer-button"
            }
            onClick={() =>
              setAnfrVisible(!anfrVisible)
            }
          >
            <span>📡</span>

            <div>
              <strong>
                Antennes ANFR
              </strong>

              <small>
                {anfrCount} sites
              </small>
            </div>

            <span className="layer-state">
              {anfrVisible ? "ON" : "OFF"}
            </span>
          </button>

          <button
            className={
              ripeVisible
                ? "layer layer-button ripe-active"
                : "layer layer-button"
            }
            onClick={() =>
              setRipeVisible(!ripeVisible)
            }
          >
            <span>🌐</span>

            <div>
              <strong>
                RIPE Atlas
              </strong>

              <small>
                {ripeCount} probes
                {" · "}
                {anchorCount} anchors
              </small>
            </div>

            <span className="layer-state">
              {ripeVisible ? "ON" : "OFF"}
            </span>
          </button>

          <button
            className={
              peeringVisible
                ? "layer layer-button peeringdb-active"
                : "layer layer-button"
            }
            onClick={() =>
              setPeeringVisible(
                !peeringVisible
              )
            }
          >
            <span>🏢</span>

            <div>
              <strong>
                PeeringDB
              </strong>

              <small>
                {peeringCount} facilities
              </small>
            </div>

            <span className="layer-state">
              {peeringVisible ? "ON" : "OFF"}
            </span>
          </button>

          <button
            className={
              arcepVisible
                ? "layer layer-button arcep-active"
                : "layer layer-button"
            }
            onClick={() =>
              setArcepVisible(
                !arcepVisible
              )
            }
          >
            <span>📱</span>

            <div>
              <strong>
                ARCEP Mobile
              </strong>

              <small>
                {arcepCount} sites opérateur
              </small>
            </div>

            <span className="layer-state">
              {arcepVisible
                ? "ON"
                : "OFF"}
            </span>
          </button>


          {arcepVisible && (
            <div className="arcep-controls">

              <div className="arcep-control">

                <label>
                  Opérateur
                </label>

                <select
                  value={arcepOperator}
                  onChange={
                    event =>
                      setArcepOperator(
                        event.target.value
                      )
                  }
                >
                  <option value="all">
                    Tous
                  </option>

                  <option value="Orange">
                    Orange
                  </option>

                  <option value="SFR">
                    SFR
                  </option>

                  <option value="Bouygues Telecom">
                    Bouygues Telecom
                  </option>

                  <option value="Free Mobile">
                    Free Mobile
                  </option>
                </select>

              </div>


              <div className="arcep-control">

                <label>
                  Technologie
                </label>

                <select
                  value={arcepTechnology}
                  onChange={
                    event =>
                      setArcepTechnology(
                        event.target.value
                      )
                  }
                >
                  <option value="all">
                    Toutes
                  </option>

                  <option value="2G">
                    2G
                  </option>

                  <option value="3G">
                    3G
                  </option>

                  <option value="4G">
                    4G
                  </option>

                  <option value="5G">
                    5G
                  </option>
                </select>

              </div>


              <label className="arcep-check">

                <input
                  type="checkbox"
                  checked={arcepOnly3500}
                  onChange={
                    event =>
                      setArcepOnly3500(
                        event.target.checked
                      )
                  }
                />

                5G 3500 MHz uniquement

              </label>


              <label className="arcep-check">

                <input
                  type="checkbox"
                  checked={arcepOnlyAnfr}
                  onChange={
                    event =>
                      setArcepOnlyAnfr(
                        event.target.checked
                      )
                  }
                />

                Correspondance ANFR uniquement

              </label>


              <button
                type="button"
                className="arcep-reset"
                onClick={() => {
                  setArcepOperator("all");
                  setArcepTechnology("all");
                  setArcepOnly3500(false);
                  setArcepOnlyAnfr(false);
                }}
              >
                Réinitialiser les filtres
              </button>

            </div>
          )}

          <button
            className={
              franceIxVisible
                ? "layer layer-button franceix-active"
                : "layer layer-button"
            }
            onClick={() =>
              setFranceIxVisible(
                !franceIxVisible
              )
            }
          >
            <span>🔀</span>

            <div>
              <strong>
                France-IX
              </strong>

              <small>
                {franceIxCount} PoPs
              </small>
            </div>

            <span className="layer-state">
              {franceIxVisible ? "ON" : "OFF"}
            </span>
          </button>

          <button
            className={
              bgpVisible
                ? "layer layer-button bgp-active"
                : "layer layer-button"
            }
            onClick={() =>
              setBgpVisible(
                !bgpVisible
              )
            }
          >
            <span>🧭</span>

            <div>
              <strong>
                BGP / RIPEstat
              </strong>

              <small>
                Logical topology
              </small>
            </div>

            <span className="layer-state">
              {bgpVisible ? "ON" : "OFF"}
            </span>
          </button>

          <div className="network-object-section">

            <button
              className="network-object-header"
              onClick={() =>
                setObjectsOpen(
                  !objectsOpen
                )
              }
            >
              <span>
                NETWORK OBJECTS
              </span>

              <span className="network-object-current">
                {getFilterLabel()}
              </span>

              <span className="network-object-arrow">
                {objectsOpen ? "▲" : "▼"}
              </span>
            </button>

            {objectsOpen && (
              <div className="network-object-menu">

                <button
                  className={
                    objectFilter === "all"
                      ? "object-option selected"
                      : "object-option"
                  }
                  onClick={() =>
                    selectObjectFilter("all")
                  }
                >
                  <span className="object-icon all-symbol" />
                  Tous les objets
                </button>

                <button
                  className={
                    objectFilter === "wifi"
                      ? "object-option selected"
                      : "object-option"
                  }
                  onClick={() =>
                    selectObjectFilter("wifi")
                  }
                >
                  <span className="object-icon wifi-symbol" />
                  Paris Wi-Fi
                </button>

                <button
                  className={
                    objectFilter === "anfr-legacy"
                      ? "object-option selected"
                      : "object-option"
                  }
                  onClick={() =>
                    selectObjectFilter(
                      "anfr-legacy"
                    )
                  }
                >
                  <span className="object-icon anfr-symbol" />
                  ANFR 2G / 3G / 4G
                </button>

                <button
                  className={
                    objectFilter === "anfr-5g"
                      ? "object-option selected"
                      : "object-option"
                  }
                  onClick={() =>
                    selectObjectFilter(
                      "anfr-5g"
                    )
                  }
                >
                  <span className="object-icon anfr5-symbol" />
                  ANFR 5G
                </button>

                <button
                  className={
                    objectFilter === "ripe-probe"
                      ? "object-option selected"
                      : "object-option"
                  }
                  onClick={() =>
                    selectObjectFilter(
                      "ripe-probe"
                    )
                  }
                >
                  <span className="object-icon ripe-symbol" />
                  RIPE Atlas Probes
                </button>

                <button
                  className={
                    objectFilter === "ripe-anchor"
                      ? "object-option selected"
                      : "object-option"
                  }
                  onClick={() =>
                    selectObjectFilter(
                      "ripe-anchor"
                    )
                  }
                >
                  <span className="object-icon ripe-anchor-symbol" />
                  RIPE Atlas Anchors
                </button>

                <button
                  className={
                    objectFilter === "peeringdb-facility"
                      ? "object-option selected"
                      : "object-option"
                  }
                  onClick={() =>
                    selectObjectFilter(
                      "peeringdb-facility"
                    )
                  }
                >
                  <span className="object-icon peeringdb-symbol" />
                  PeeringDB Facilities
                </button>

                <button
                  className={
                    objectFilter === "franceix-pop"
                      ? "object-option selected"
                      : "object-option"
                  }
                  onClick={() =>
                    selectObjectFilter(
                      "franceix-pop"
                    )
                  }
                >
                  <span className="object-icon franceix-symbol" />
                  France-IX PoPs
                </button>

                <button
                  className={
                    objectFilter ===
                      "arcep-mobile"
                      ? "object-option selected"
                      : "object-option"
                  }
                  onClick={() => {
                    setObjectFilter(
                      "arcep-mobile"
                    );

                    setObjectsOpen(
                      false
                    );
                  }}
                >
                  <span
                    className="object-icon arcep-symbol"
                  />

                  ARCEP Mobile
                </button>

              </div>
            )}

          </div>

          <div className="legend">

            <h3>
              Network objects
            </h3>

            <p>
              <span className="legend-symbol wifi-symbol" />
              Paris Wi-Fi
            </p>

            <p>
              <span className="legend-symbol anfr-symbol" />
              ANFR 2G/3G/4G
            </p>

            <p>
              <span className="legend-symbol anfr5-symbol" />
              ANFR 5G
            </p>

            <p>
              <span className="legend-symbol ripe-symbol" />
              RIPE Probe
            </p>

            <p>
              <span className="legend-symbol ripe-anchor-symbol" />
              RIPE Anchor
            </p>

            <p>
              <span className="legend-square peeringdb-symbol" />
              PeeringDB Facility
            </p>

            <p>
              <span className="legend-diamond franceix-symbol" />
              France-IX PoP
            </p>

            <p>
              <span className="legend-circle arcep-symbol" />
              ARCEP Mobile
            </p>

          </div>

          <div className="legend">

            <h3>
              Data provenance
            </h3>

            <p>🟢 Public declaration</p>
            <p>🔵 Observed</p>
            <p>🟠 Inferred</p>
            <p>🟣 Simulated</p>

          </div>

        </aside>

        <section className="map-area">

          <div
            ref={mapContainer}
            className="map"
          />

        </section>

      </main>

      <BgpTopology
        visible={bgpVisible}
        onClose={() =>
          setBgpVisible(false)
        }
      />

    </div>
  );
}

export default App;
