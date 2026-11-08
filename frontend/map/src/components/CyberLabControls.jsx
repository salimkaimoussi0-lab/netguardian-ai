import {
  useCallback,
  useEffect,
  useState,
} from "react";

import "./CyberLabControls.css";


const API_URL =
  import.meta.env.VITE_CYBER_API_URL
  || (
    import.meta.env.DEV
      ? "http://127.0.0.1:8780"
      : null
  );


const SCENARIOS = [
  {
    id:
      "normal",

    name:
      "Normal Traffic",

    description:
      "Legitimate ICMP + HTTP traffic",
  },

  {
    id:
      "port_scan",

    name:
      "Port Scan",

    description:
      "Controlled reconnaissance h3 → h2",
  },

  {
    id:
      "http_error_burst",

    name:
      "HTTP Error Burst",

    description:
      "Multiple abnormal HTTP 404 requests",
  },

  {
    id:
      "connection_burst",

    name:
      "Connection Burst",

    description:
      "Rapid TCP connections to h2",
  },

  {
    id:
      "high_bandwidth",

    name:
      "High Bandwidth",

    description:
      "Controlled iperf3 traffic",
  },
];


export default function CyberLabControls() {

  const [
    collapsed,
    setCollapsed,
  ] = useState(false);

  const [
    status,
    setStatus,
  ] = useState(null);

  const [
    error,
    setError,
  ] = useState(null);


  const refreshStatus = useCallback(
    async () => {

      if (!API_URL) {

        setStatus(null);

        return;
      }


      try {

        const response = await fetch(
          `${API_URL}/api/lab/status`
        );


        if (!response.ok) {

          throw new Error(
            `HTTP ${response.status}`
          );
        }


        const data = await response.json();

        setStatus(
          data
        );

        setError(
          null
        );


      } catch {

        setStatus(
          null
        );

        setError(
          "Cyber Engine offline"
        );
      }
    },

    []
  );


  useEffect(
    () => {

      refreshStatus();


      const timer = setInterval(
        refreshStatus,
        1000
      );


      return () => clearInterval(
        timer
      );
    },

    [
      refreshStatus
    ]
  );


  const runScenario = async (
    scenario
  ) => {

    if (!API_URL) {
      return;
    }


    try {

      setError(
        null
      );


      const response = await fetch(
        `${API_URL}/api/lab/scenarios/${scenario}`,
        {
          method:
            "POST",
        }
      );


      const data = await response.json();


      if (!response.ok) {

        if (
          data.error
          === "LAB_BUSY"
        ) {

          throw new Error(
            `Lab busy: ${
              data.current_scenario
              || "scenario running"
            }`
          );
        }


        throw new Error(
          data.error
          || `HTTP ${response.status}`
        );
      }


      await refreshStatus();


    } catch (
      exception
    ) {

      setError(
        exception.message
        || "Unable to start scenario"
      );
    }
  };


  const online = Boolean(
    status?.online
  );

  const running = (
    status?.state
    === "RUNNING"
  );


  return (
    <section
      className="cyber-control-panel"
    >

      <header
        className="cyber-control-header"
      >

        <div>

          <div
            className="cyber-control-eyebrow"
          >
            NETGUARDIAN
          </div>

          <strong>
            Cyber Lab Control
          </strong>

        </div>


        <div className="cyber-control-header-actions">

          <span
            className={
              online
                ? "lab-state online"
                : "lab-state offline"
            }
          >
            {online
              ? status.state
              : "OFFLINE"}
          </span>

          <button
            type="button"
            className="cyber-collapse-button"
            onClick={() => setCollapsed(value => !value)}
            aria-label={
              collapsed
                ? "Déplier Cyber Lab Control"
                : "Plier Cyber Lab Control"
            }
            title={
              collapsed
                ? "Déplier"
                : "Plier"
            }
          >
            {collapsed ? "+" : "−"}
          </button>

        </div>

      </header>

      {!collapsed && (
        <>


      <div
        className="lab-topology"
      >

        <div className="lab-host">
          <strong>h1</strong>
          <span>Client</span>
          <small>10.10.0.11</small>
        </div>

        <div className="lab-arrow">
          ──
        </div>

        <div className="lab-switch">
          <strong>s1</strong>
          <span>OVS</span>
        </div>

        <div className="lab-arrow">
          ──
        </div>

        <div className="lab-host">
          <strong>h2</strong>
          <span>Server</span>
          <small>10.10.0.20</small>
        </div>

      </div>


      <div
        className="lab-test-host"
      >
        Test Host:
        {" "}
        <strong>h3</strong>
        {" · "}
        10.10.0.30
      </div>


      <div
        className="scenario-list"
      >

        {SCENARIOS.map(
          scenario => (

            <button
              key={
                scenario.id
              }

              type="button"

              disabled={
                !online
                || running
              }

              className="scenario-button"

              onClick={
                () => runScenario(
                  scenario.id
                )
              }
            >

              <div>

                <strong>
                  {scenario.name}
                </strong>

                <small>
                  {scenario.description}
                </small>

              </div>


              <span>
                {(
                  running
                  &&
                  status.current_scenario
                  === scenario.id
                )
                  ? "RUNNING"
                  : "▶ RUN"}
              </span>

            </button>

          )
        )}

      </div>


      {running && (

        <div
          className="lab-running"
        >
          Scenario running:
          {" "}
          <strong>
            {status.current_scenario}
          </strong>
        </div>

      )}


      {!running
        &&
        status?.last_scenario
        && (

          <div
            className="lab-last-run"
          >

            Last:
            {" "}

            <strong>
              {status.last_scenario}
            </strong>

            {" · "}

            {status.last_status}

          </div>

        )}


      {error && (

        <div
          className="lab-error"
        >
          {error}
        </div>

      )}

        </>
      )}

    </section>
  );
}
