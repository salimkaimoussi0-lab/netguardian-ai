import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

const PARIS_CENTER = [2.3522, 48.8566];

function App() {
  const mapContainer = useRef(null);
  const mapRef = useRef(null);

  const [count, setCount] = useState(0);
  const [status, setStatus] = useState("Chargement...");

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

    map.on("load", async () => {
      try {
        console.log(
          "[NetGuardian] map loaded"
        );

        const response = await fetch(
          "/data/paris_wifi_sites.geojson"
        );

        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}`
          );
        }

        const data = await response.json();

        console.log(
          "[NetGuardian] GeoJSON:",
          data
        );

        const features =
          Array.isArray(data.features)
            ? data.features
            : [];

        const validFeatures =
          features.filter((feature) => {
            if (
              feature.geometry?.type !== "Point"
            ) {
              return false;
            }

            const coordinates =
              feature.geometry.coordinates;

            if (
              !Array.isArray(coordinates) ||
              coordinates.length < 2
            ) {
              return false;
            }

            const longitude =
              Number(coordinates[0]);

            const latitude =
              Number(coordinates[1]);

            return (
              Number.isFinite(longitude) &&
              Number.isFinite(latitude)
            );
          });

        console.log(
          "[NetGuardian] valid points:",
          validFeatures.length
        );

        setCount(validFeatures.length);

        const bounds =
          new maplibregl.LngLatBounds();

        validFeatures.forEach(
          (feature, index) => {
            const coordinates =
              feature.geometry.coordinates;

            const longitude =
              Number(coordinates[0]);

            const latitude =
              Number(coordinates[1]);

            const properties =
              feature.properties ?? {};

            console.log(
              `Point ${index}:`,
              longitude,
              latitude,
              properties.name
            );

            /*
             * Marqueur HTML.
             * Impossible à confondre avec la carte.
             */

            const markerElement =
              document.createElement("div");

            markerElement.className =
              "wifi-marker";

            markerElement.title =
              properties.name ||
              "Paris Wi-Fi";

            const popup =
              new maplibregl.Popup({
                offset: 18
              }).setHTML(`
                <div class="wifi-popup">

                  <div class="popup-badge">
                    PARIS WI-FI
                  </div>

                  <h3>
                    ${
                      properties.name ||
                      "Site Wi-Fi"
                    }
                  </h3>

                  <p>
                    <strong>Adresse</strong><br>
                    ${
                      properties.address ||
                      "Non disponible"
                    }
                    ${
                      properties.postal_code ||
                      ""
                    }
                  </p>

                  <p>
                    <strong>État</strong><br>
                    ${
                      properties.status ||
                      "Non disponible"
                    }
                  </p>

                  <p>
                    <strong>Bornes Wi-Fi</strong><br>
                    ${
                      properties.wifi_access_points ??
                      "Non disponible"
                    }
                  </p>

                  <p>
                    <strong>Source</strong><br>
                    ${
                      properties.source ||
                      "Paris Open Data"
                    }
                  </p>

                  <p>
                    <strong>Coordonnées</strong><br>
                    ${latitude.toFixed(5)},
                    ${longitude.toFixed(5)}
                  </p>

                </div>
              `);

            new maplibregl.Marker({
              element: markerElement,
              anchor: "center"
            })
              .setLngLat([
                longitude,
                latitude
              ])
              .setPopup(popup)
              .addTo(map);

            bounds.extend([
              longitude,
              latitude
            ]);
          }
        );

        if (
          validFeatures.length > 0 &&
          !bounds.isEmpty()
        ) {
          map.fitBounds(
            bounds,
            {
              padding: 60,
              maxZoom: 13
            }
          );
        }

        setStatus(
          `${validFeatures.length} sites affichés`
        );

      } catch (error) {
        console.error(
          "[NetGuardian ERROR]",
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
              {count} sites Wi-Fi
            </small>
          </div>

        </div>

      </header>

      <main className="workspace">

        <aside className="sidebar">

          <h2>
            Network Layers
          </h2>

          <div className="layer active">
            📶

            <div>
              <strong>
                Paris Wi-Fi
              </strong>

              <small>
                {count} sites
              </small>
            </div>
          </div>

          <div className="layer future">
            📡 Antennes ANFR
          </div>

          <div className="layer future">
            📱 ARCEP Mobile
          </div>

          <div className="layer future">
            🌐 RIPE Atlas
          </div>

          <div className="layer future">
            🏢 PeeringDB
          </div>

          <div className="layer future">
            🔀 France-IX
          </div>

          <div className="layer future">
            🧭 BGP / RIPEstat
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

    </div>
  );
}

export default App;
