import { memo } from 'react';

function HeroSection() {
  return (
    <section id="hero" className="page-section hero-section">
      <div className="section-inner">
        <p className="eyebrow">Sudokudo</p>
        <h1>From Phone Snapshot To Solved Grid</h1>
        <p className="section-copy">
          Drop a Sudoku image, run OCR solve, and inspect how MRV plus forward checking prunes huge chunks
          of the search tree before brute force even starts.
        </p>
      </div>
    </section>
  );
}

export default memo(HeroSection);
