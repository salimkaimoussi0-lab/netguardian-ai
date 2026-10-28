import {
  useEffect,
  useState,
} from "react";

import "./CyberRangeLive.css";


const WS_URL =
  import.meta.env.VITE_CYBER_WS_URL
  || "ws://127.0.0.1:8765";


function formatTime(value) {

  if (!value) {
    return "--:--:--";
  }

  try {

    return new Date(
      value
    ).toLocaleTimeString(
      "fr-FR",
      {
        hour:
          "2-digit",

        minute:
          "2-digit",

        second:
          "2-digit",
      }
    );

  } catch {

    return "--:--:--";
  }
}


function eventTitle(event) {

  switch (event.type) {

    case "SECURITY_ALERT":
      return "⚠ SECURITY ALERT";

    case "HTTP_REQUEST":
      return "HTTP";

    case "THROUGHPUT":
      return "TRAFFIC";

    case "ICMP":
      return "ICMP";

    case "NETWORK_WEIRD":
      return "NETWORK WEIRD";

    default:
      return "CONNECTION";
  }
}


function eventDescription(event) {

  if (
    event.type
    === "SECURITY_ALERT"
  ) {

    if (
      event.alert_type
      === "PORT_SCAN"
    ) {

      return (
        `PORT SCAN · `
        + `${event.unique_ports || 0} ports · `
        + `${event.window_seconds || "?"}s`
      );
    }


    if (
      event.alert_type
      === "CONNECTION_BURST"
    ) {

      return (
        `CONNECTION BURST · `
        + `${event.connections || 0} connections · `
        + `port ${event.destination_port || "?"}`
      );
    }


    if (
      event.alert_type
      === "HTTP_ERROR_BURST"
    ) {

      return (
        `HTTP ERROR BURST · `
        + `${event.errors || 0} errors`
      );
    }


    if (
      event.alert_type
      === "HIGH_BANDWIDTH"
    ) {

      return (
        `HIGH BANDWIDTH · `
        + `${event.throughput_mbps || 0} Mbps`
      );
    }


    return (
      event.alert_type
      || "Security anomaly"
    );
  }


  if (
    event.type
    === "HTTP_REQUEST"
  ) {

    return (
      `${event.method || "HTTP"} `
      + `${event.uri || "/"} `
      + `→ ${event.status_code || "?"}`
    );
  }


  if (
    event.type
    === "THROUGHPUT"
  ) {

    if (
      event.throughput_mbps
      != null
    ) {

      return (
        `${event.throughput_mbps} Mbps`
      );
    }

    return "iperf3 traffic";
  }


  if (
    event.type
    === "ICMP"
  ) {

    return (
      `${event.orig_packets || 0} packets`
    );
  }


  if (
    event.type
    === "NETWORK_WEIRD"
  ) {

    return (
      event.name
      || "Zeek anomaly"
    );
  }


  return (
    `${event.protocol || "network"}`
    + (
      event.destination_port
        ? ` :${event.destination_port}`
        : ""
    )
  );
}


export default function CyberRangeLive() {

  const [
    connected,
    setConnected,
  ] = useState(false);

  const [
    events,
    setEvents,
  ] = useState([]);

  const [
    collapsed,
    setCollapsed,
  ] = useState(false);


  useEffect(
    () => {

      let socket = null;

      let reconnectTimer = null;

      let stopped = false;


      const connect = () => {

        if (stopped) {
          return;
        }


        socket = new WebSocket(
          WS_URL
        );


        socket.onopen = () => {

          setConnected(true);

          console.log(
            "[CyberRange] WebSocket connected"
          );
        };


        socket.onmessage = (
          message
        ) => {

          try {

            const data = JSON.parse(
              message.data
            );


            if (
              data.type
              === "SNAPSHOT"
            ) {

              setEvents(
                [
                  ...(data.events || [])
                ]
                  .reverse()
                  .slice(
                    0,
                    50
                  )
              );

              return;
            }


            if (
              data.type
              === "PONG"
            ) {
              return;
            }


            setEvents(
              current => [
                data,
                ...current,
              ].slice(
                0,
                50
              )
            );

          } catch (
            error
          ) {

            console.error(
              "[CyberRange] invalid event",
              error
            );
          }
        };


        socket.onerror = () => {

          setConnected(
            false
          );
        };


        socket.onclose = () => {

          setConnected(
            false
          );

          if (!stopped) {

            reconnectTimer =
              setTimeout(
                connect,
                2000
              );
          }
        };
      };


      connect();


      return () => {

        stopped = true;

        clearTimeout(
          reconnectTimer
        );

        socket?.close();
      };
    },

    []
  );


  return (
    <section
      className={
        `cyber-live-panel `
        + (
          collapsed
            ? "cyber-live-collapsed"
            : ""
        )
      }
    >

      <header
        className="cyber-live-header"
      >

        <div>

          <div
            className="cyber-live-eyebrow"
          >
            CYBER RANGE
          </div>

          <strong>
            Live Network Activity
          </strong>

        </div>


        <div
          className="cyber-live-actions"
        >

          <span
            className={
              connected
                ? "cyber-live-status online"
                : "cyber-live-status offline"
            }
          >
            {connected
              ? "LIVE"
              : "OFFLINE"}
          </span>


          <button
            type="button"
            onClick={
              () => setCollapsed(
                value => !value
              )
            }
          >
            {collapsed
              ? "+"
              : "−"}
          </button>

        </div>

      </header>


      {!collapsed && (

        <div
          className="cyber-live-events"
        >

          {events.length === 0 && (

            <div
              className="cyber-live-empty"
            >
              En attente d'événements Zeek...
            </div>

          )}


          {events.map(
            event => (

              <article
                className={
                  `cyber-live-event `
                  + (
                    event.severity
                    || "info"
                  )
                }
                key={
                  event.event_id
                  || `${event.timestamp}-${Math.random()}`
                }
              >

                <div
                  className="cyber-live-time"
                >
                  {formatTime(
                    event.timestamp
                  )}
                </div>


                <div
                  className="cyber-live-body"
                >

                  <strong>
                    {eventTitle(
                      event
                    )}
                  </strong>

                  <div>
                    {
                      event.source?.id
                      || event.source?.ip
                      || "?"
                    }

                    {" → "}

                    {
                      event.destination?.id
                      || event.destination?.ip
                      || "?"
                    }
                  </div>

                  <small>
                    {eventDescription(
                      event
                    )}
                  </small>

                </div>

              </article>

            )
          )}

        </div>

      )}

    </section>
  );
}
