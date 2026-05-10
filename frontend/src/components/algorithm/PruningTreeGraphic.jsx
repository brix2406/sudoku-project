function PruningTreeGraphic() {
  return (
    <svg className="pruning-tree" viewBox="0 0 860 390" role="img" aria-label="MRV branch selection and pruning">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="currentColor" />
        </marker>
      </defs>

      <g className="tree-edges" strokeWidth="2.5" fill="none">
        <path d="M430 52 L250 132" className="normal" />
        <path d="M430 52 L430 132" className="selected" />
        <path d="M430 52 L610 132" className="normal" />

        <path d="M430 132 L355 230" className="selected" />
        <path d="M430 132 L505 230" className="pruned" />

        <path d="M355 230 L315 314" className="selected" />
        <path d="M355 230 L395 314" className="normal" />

        <path d="M250 132 L195 230" className="normal" />
        <path d="M610 132 L665 230" className="normal" />
      </g>

      <g className="tree-nodes">
        <circle cx="430" cy="52" r="20" className="selected-node" />
        <text x="430" y="48">State S0</text>
        <text x="430" y="63">pick MRV</text>

        <circle cx="250" cy="132" r="20" />
        <text x="250" y="128">Cell A</text>
        <text x="250" y="143">3 cand</text>

        <circle cx="430" cy="132" r="20" className="selected-node" />
        <text x="430" y="128">Cell B</text>
        <text x="430" y="143">2 cand</text>

        <circle cx="610" cy="132" r="20" />
        <text x="610" y="128">Cell C</text>
        <text x="610" y="143">4 cand</text>

        <circle cx="355" cy="230" r="20" className="selected-node" />
        <text x="355" y="226">B=4</text>
        <text x="355" y="241">continue</text>

        <circle cx="505" cy="230" r="20" className="pruned-node" />
        <text x="505" y="226">B=7</text>
        <text x="505" y="241">0 cand</text>

        <circle cx="315" cy="314" r="18" className="selected-node" />
        <text x="315" y="319">Solved</text>

        <circle cx="395" cy="314" r="18" />
        <text x="395" y="319">Backtrack</text>

        <circle cx="195" cy="230" r="18" />
        <text x="195" y="235">Later</text>

        <circle cx="665" cy="230" r="18" />
        <text x="665" y="235">Later</text>
      </g>

      <g className="tree-labels">
        <text x="42" y="358">MRV chooses the node with the fewest candidates first (Cell B: 2).</text>
        <text x="42" y="376">If a choice creates a zero-candidate state, that branch is pruned immediately.</text>
        <line x1="640" y1="350" x2="515" y2="246" markerEnd="url(#arrow)" />
      </g>

      <g className="tree-legend">
        <rect x="642" y="20" width="196" height="88" rx="10" />
        <line x1="658" y1="45" x2="700" y2="45" className="selected" />
        <text x="712" y="49">Chosen by MRV</text>
        <line x1="658" y1="69" x2="700" y2="69" className="pruned" />
        <text x="712" y="73">Pruned branch</text>
        <line x1="658" y1="93" x2="700" y2="93" className="normal" />
        <text x="712" y="97">Unexplored branch</text>
      </g>
    </svg>
  );
}

export default PruningTreeGraphic;
