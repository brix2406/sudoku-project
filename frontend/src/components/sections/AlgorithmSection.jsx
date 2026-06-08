import { memo } from 'react';
import PruningTreeGraphic from '../algorithm/PruningTreeGraphic';

function AlgorithmSection() {
  return (
    <section id="algorithm" className="page-section algorithm-section">
      <div className="section-inner">
        <h2>Algorithm: MRV Backtracking Solver</h2>
        <p className="section-copy">
          The solver scans all empty cells, computes candidates from current row, column, and sub-grid constraints,
          then chooses the cell with the fewest legal values (MRV). It tries those values recursively and backtracks
          immediately when a branch reaches a cell with zero candidates.
        </p>

        <PruningTreeGraphic />

        <div className="algorithm-steps">
          <p>1. Find every empty cell (`.`) and compute its legal candidates.</p>
          <p>2. Select the empty cell with the smallest candidate list (MRV choice).</p>
          <p>3. Try each candidate in that cell and recurse.</p>
          <p>4. If recursion fails, reset that cell to `.` and try the next candidate.</p>
          <p>5. If no empty cells remain, return solved.</p>
        </div>
      </div>
    </section>
  );
}

export default memo(AlgorithmSection);
