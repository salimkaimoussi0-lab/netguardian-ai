import {
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";

import cytoscape from "cytoscape";


function number(value) {
  const n = Number(value);

  return Number.isFinite(n)
    ? n
    : 0;
}


function BgpTopology({
  visible,
  onClose
}) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  const [data, setData] =
    useState(null);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  const [selectedId, setSelectedId] =
    useState(null);

  const [search, setSearch] =
    useState("");

  const [
    onlyFranceIx,
    setOnlyFranceIx
  ] = useState(false);

  const [
    neighbourLimit,
    setNeighbourLimit
  ] = useState(50);


  /*
   * =========================================
   * LOAD BGP GRAPH
   * =========================================
   */

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);

        const response =
          await fetch(
            "/data/bgp_franceix_graph.json"
          );

        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}`
          );
        }

        const json =
          await response.json();

        if (cancelled) {
          return;
        }

        setData(json);

        const members =
          (json.nodes ?? [])
            .filter(
              node =>
                node.franceix_member === true
            );

        if (members.length) {
          setSelectedId(
            members[0].id
          );
        }

        setLoading(false);

      } catch (e) {
        if (!cancelled) {
          setError(
            e.message
          );

          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, []);


  /*
   * =========================================
   * INDEXES
   * =========================================
   */

  const nodeById =
    useMemo(() => {
      const map = new Map();

      for (
        const node
        of data?.nodes ?? []
      ) {
        map.set(
          node.id,
          node
        );
      }

      return map;
    }, [data]);


  const memberNodes =
    useMemo(() => {
      return (
        data?.nodes ?? []
      )
        .filter(
          node =>
            node.franceix_member === true
        )
        .sort(
          (a, b) =>
            String(
              a.name ?? ""
            ).localeCompare(
              String(
                b.name ?? ""
              )
            )
        );
    }, [data]);


  const selectedNode =
    selectedId
      ? nodeById.get(selectedId)
      : null;


  /*
   * =========================================
   * EDGES CONNECTED TO SELECTED ASN
   * =========================================
   */

  const connectedEdges =
    useMemo(() => {
      if (
        !data ||
        !selectedId
      ) {
        return [];
      }

      let result =
        data.edges.filter(
          edge =>
            edge.source === selectedId ||
            edge.target === selectedId
        );

      if (onlyFranceIx) {
        result =
          result.filter(
            edge => {
              const neighbourId =
                edge.source === selectedId
                  ? edge.target
                  : edge.source;

              const node =
                nodeById.get(
                  neighbourId
                );

              return (
                node?.franceix_member === true
              );
            }
          );
      }

      result.sort(
        (a, b) =>
          number(
            b.path_count
          )
          -
          number(
            a.path_count
          )
      );

      return result.slice(
        0,
        neighbourLimit
      );

    }, [
      data,
      selectedId,
      onlyFranceIx,
      neighbourLimit,
      nodeById
    ]);


  /*
   * =========================================
   * CYTOSCAPE RENDER
   * =========================================
   */

  useEffect(() => {
    if (
      !visible ||
      !data ||
      !selectedId ||
      !containerRef.current
    ) {
      return;
    }

    if (cyRef.current) {
      cyRef.current.destroy();
      cyRef.current = null;
    }

    const selected =
      nodeById.get(
        selectedId
      );

    if (!selected) {
      return;
    }

    const nodeIds =
      new Set([
        selectedId
      ]);

    const cytoscapeEdges = [];

    for (
      const edge
      of connectedEdges
    ) {
      nodeIds.add(
        edge.source
      );

      nodeIds.add(
        edge.target
      );

      cytoscapeEdges.push(
        {
          data: {
            id:
              `${edge.source}-${edge.target}`,

            source:
              edge.source,

            target:
              edge.target,

            pathCount:
              number(
                edge.path_count
              ),

            internal:
              Boolean(
                edge.both_franceix_members
              )
          }
        }
      );
    }

    const cytoscapeNodes =
      [...nodeIds]
        .map(id => {
          const node =
            nodeById.get(id);

          if (!node) {
            return null;
          }

          const isSelected =
            id === selectedId;

          return {
            data: {
              id:
                node.id,

              asn:
                node.asn,

              label:
                node.name &&
                node.name !==
                  `AS${node.asn}`
                  ? `AS${node.asn}\n${node.name}`
                  : `AS${node.asn}`,

              selected:
                isSelected,

              member:
                Boolean(
                  node.franceix_member
                ),

              prefixCount:
                number(
                  node.prefix_count
                ),

              neighbourCount:
                number(
                  node.neighbour_count
                )
            }
          };
        })
        .filter(Boolean);


    const cy = cytoscape({
      container:
        containerRef.current,

      elements: [
        ...cytoscapeNodes,
        ...cytoscapeEdges
      ],

      minZoom: 0.15,

      maxZoom: 3,

      wheelSensitivity: 0.2,

      style: [
        {
          selector: "node",

          style: {
            "background-color":
              "#64748b",

            "border-color":
              "#ffffff",

            "border-width":
              2,

            width:
              "mapData(neighbourCount, 0, 3000, 24, 54)",

            height:
              "mapData(neighbourCount, 0, 3000, 24, 54)",

            label:
              "data(label)",

            color:
              "#e2e8f0",

            "font-size":
              8,

            "text-wrap":
              "wrap",

            "text-max-width":
              90,

            "text-valign":
              "bottom",

            "text-margin-y":
              7,

            "overlay-opacity":
              0
          }
        },

        {
          selector:
            "node[member]",

          style: {
            "background-color":
              "#2563eb"
          }
        },

        {
          selector:
            "node[selected]",

          style: {
            "background-color":
              "#eab308",

            "border-width":
              4,

            width:
              64,

            height:
              64,

            "font-size":
              11,

            "font-weight":
              "bold"
          }
        },

        {
          selector: "edge",

          style: {
            width:
              "mapData(pathCount, 0, 5000, 1, 5)",

            "line-color":
              "#475569",

            "curve-style":
              "bezier",

            opacity:
              0.65
          }
        },

        {
          selector:
            "edge[internal]",

          style: {
            "line-color":
              "#3b82f6",

            opacity:
              0.9
          }
        }
      ],

      layout: {
        name:
          "cose",

        animate:
          false,

        fit:
          true,

        padding:
          45,

        nodeRepulsion:
          900000,

        idealEdgeLength:
          130,

        edgeElasticity:
          100,

        gravity:
          0.4,

        numIter:
          800
      }
    });


    /*
     * Cliquer sur un autre ASN
     * devient le nouveau centre.
     */

    cy.on(
      "tap",
      "node",
      event => {
        const id =
          event.target.id();

        setSelectedId(id);
      }
    );


    cyRef.current = cy;


    return () => {
      cy.destroy();

      if (
        cyRef.current === cy
      ) {
        cyRef.current = null;
      }
    };

  }, [
    visible,
    data,
    selectedId,
    connectedEdges,
    nodeById
  ]);


  /*
   * =========================================
   * SEARCH
   * =========================================
   */

  function executeSearch() {
    if (!data) {
      return;
    }

    const value =
      search
        .trim()
        .toLowerCase();

    if (!value) {
      return;
    }

    let match = null;

    const numeric =
      value
        .replace(/^as/, "")
        .trim();

    if (
      /^\d+$/.test(
        numeric
      )
    ) {
      match =
        data.nodes.find(
          node =>
            String(
              node.asn
            ) === numeric
        );
    }

    if (!match) {
      match =
        data.nodes.find(
          node =>
            String(
              node.name ?? ""
            )
              .toLowerCase()
              .includes(value)
        );
    }

    if (match) {
      setSelectedId(
        match.id
      );

      setSearch(
        `AS${match.asn}`
      );
    }
  }


  /*
   * =========================================
   * SELECTED ASN STATS
   * =========================================
   */

  const totalDegree =
    useMemo(() => {
      if (
        !data ||
        !selectedId
      ) {
        return 0;
      }

      return data.edges.filter(
        edge =>
          edge.source === selectedId ||
          edge.target === selectedId
      ).length;

    }, [
      data,
      selectedId
    ]);


  if (!visible) {
    return null;
  }


  return (
    <div className="bgp-panel">

      <div className="bgp-header">

        <div>
          <div className="bgp-eyebrow">
            LOGICAL INTERNET TOPOLOGY
          </div>

          <h2>
            BGP / RIPEstat
          </h2>
        </div>

        <button
          className="bgp-close"
          onClick={onClose}
          type="button"
        >
          ×
        </button>

      </div>


      {loading && (
        <div className="bgp-message">
          Chargement du graphe BGP...
        </div>
      )}


      {error && (
        <div className="bgp-message bgp-error">
          Erreur : {error}
        </div>
      )}


      {!loading &&
       !error &&
       data && (
        <>

          <div className="bgp-global-stats">

            <div>
              <strong>
                {
                  data.metadata
                    ?.member_asn_count ?? 0
                }
              </strong>

              <span>
                ASN France-IX
              </span>
            </div>

            <div>
              <strong>
                {
                  data.metadata
                    ?.node_count ?? 0
                }
              </strong>

              <span>
                ASN total
              </span>
            </div>

            <div>
              <strong>
                {
                  data.metadata
                    ?.edge_count ?? 0
                }
              </strong>

              <span>
                relations BGP
              </span>
            </div>

          </div>


          <div className="bgp-controls">

            <div className="bgp-search">

              <input
                value={search}
                onChange={
                  event =>
                    setSearch(
                      event.target.value
                    )
                }
                onKeyDown={
                  event => {
                    if (
                      event.key === "Enter"
                    ) {
                      executeSearch();
                    }
                  }
                }
                placeholder="AS714 ou Apple..."
                list="bgp-member-list"
              />

              <datalist id="bgp-member-list">
                {
                  memberNodes.map(
                    node => (
                      <option
                        key={node.id}
                        value={
                          `AS${node.asn}`
                        }
                      >
                        {node.name}
                      </option>
                    )
                  )
                }
              </datalist>

              <button
                onClick={executeSearch}
                type="button"
              >
                Rechercher
              </button>

            </div>


            <label className="bgp-check">

              <input
                type="checkbox"
                checked={onlyFranceIx}
                onChange={
                  event =>
                    setOnlyFranceIx(
                      event.target.checked
                    )
                }
              />

              seulement voisins France-IX

            </label>


            <label className="bgp-limit">

              <span>
                Voisins affichés
              </span>

              <select
                value={neighbourLimit}
                onChange={
                  event =>
                    setNeighbourLimit(
                      Number(
                        event.target.value
                      )
                    )
                }
              >
                <option value="25">
                  25
                </option>

                <option value="50">
                  50
                </option>

                <option value="80">
                  80
                </option>

                <option value="120">
                  120
                </option>
              </select>

            </label>

          </div>


          {selectedNode && (
            <div className="bgp-selected">

              <div className="bgp-selected-title">

                <div>
                  <span>
                    AUTONOMOUS SYSTEM
                  </span>

                  <h3>
                    AS{selectedNode.asn}
                  </h3>

                  <p>
                    {selectedNode.name}
                  </p>
                </div>

                {
                  selectedNode
                    .franceix_member
                    ? (
                      <span className="bgp-member-badge">
                        FRANCE-IX
                      </span>
                    )
                    : (
                      <span className="bgp-external-badge">
                        EXTERNAL
                      </span>
                    )
                }

              </div>


              <div className="bgp-selected-grid">

                <div>
                  <strong>
                    {
                      number(
                        selectedNode
                          .prefix_count
                      )
                    }
                  </strong>

                  <span>
                    préfixes
                  </span>
                </div>

                <div>
                  <strong>
                    {
                      number(
                        selectedNode
                          .ipv4_prefix_count
                      )
                    }
                  </strong>

                  <span>
                    IPv4
                  </span>
                </div>

                <div>
                  <strong>
                    {
                      number(
                        selectedNode
                          .ipv6_prefix_count
                      )
                    }
                  </strong>

                  <span>
                    IPv6
                  </span>
                </div>

                <div>
                  <strong>
                    {totalDegree}
                  </strong>

                  <span>
                    voisins BGP
                  </span>
                </div>

              </div>

            </div>
          )}


          <div
            ref={containerRef}
            className="bgp-cytoscape"
          />


          <div className="bgp-legend">

            <span>
              <i className="bgp-dot bgp-dot-selected" />
              ASN sélectionné
            </span>

            <span>
              <i className="bgp-dot bgp-dot-member" />
              membre France-IX
            </span>

            <span>
              <i className="bgp-dot bgp-dot-external" />
              ASN externe
            </span>

          </div>


          <div className="bgp-warning">

            Les liens représentent des adjacences
            observées dans les chemins BGP RIPE RIS.
            Ils ne prouvent ni un câble physique,
            ni un accord commercial direct entre
            les deux réseaux.

          </div>

        </>
      )}

    </div>
  );
}

export default BgpTopology;
