
import { useEffect, useState } from 'react';

function createBoard(size) {
	return Array.from({ length: size }, () => Array.from({ length: size }, () => ''));
}

function serializeSudoku(k, n, board) {
	const cells = board.flat().map((cell) => (cell === '' ? '0' : cell));
	return `Sudoku{(${k},${n})(${cells.join(',')})}`;
}

function parseSudokuString(value) {
	const trimmedValue = value.trim();
	const match = /^Sudoku\{\((\d+),(\d+)\)\((.*)\)\}$/.exec(trimmedValue);

	if (!match) {
		return { valid: false };
	}

	const parsedK = Number(match[1]);
	const parsedN = Number(match[2]);

	if (!Number.isInteger(parsedK) || !Number.isInteger(parsedN) || parsedK < 1 || parsedN < 1) {
		return { valid: false };
	}

	const boardSize = parsedK * parsedN;
	const expectedCellCount = boardSize * boardSize;
	const rawCells = match[3].length > 0 ? match[3].split(',') : [];

	if (rawCells.length !== expectedCellCount) {
		return { valid: false };
	}

	const maxValue = parsedN * parsedN;
	const board = [];

	for (let rowIndex = 0; rowIndex < boardSize; rowIndex += 1) {
		const row = [];

		for (let colIndex = 0; colIndex < boardSize; colIndex += 1) {
			const cellValue = rawCells[rowIndex * boardSize + colIndex].trim();

			if (!/^\d+$/.test(cellValue)) {
				return { valid: false };
			}

			const numericValue = Number(cellValue);

			if (numericValue < 0 || numericValue > maxValue) {
				return { valid: false };
			}

			row.push(numericValue === 0 ? '' : String(numericValue));
		}

		board.push(row);
	}

	return {
		valid: true,
		k: parsedK,
		n: parsedN,
		board,
	};
}

function ManualSudokuSection() {
	const [k, setK] = useState(3);
	const [n, setN] = useState(3);
	const [board, setBoard] = useState(() => createBoard(9));
	const [sudokuText, setSudokuText] = useState(() => serializeSudoku(3, 3, createBoard(9)));
	const [parseError, setParseError] = useState('');

	const boardSize = Math.max(1, k) * Math.max(1, n);
	const maxValue = Math.max(1, n) * Math.max(1, n);
	const boardString = serializeSudoku(k, n, board);

	useEffect(() => {
		setSudokuText(boardString);
	}, [boardString]);

	function handleCellChange(rowIndex, colIndex, value) {
		const trimmedValue = value.trim();

		if (trimmedValue === '') {
			setBoard((currentBoard) =>
				currentBoard.map((row, currentRowIndex) =>
					currentRowIndex === rowIndex
						? row.map((cell, currentColIndex) => (currentColIndex === colIndex ? '' : cell))
						: row,
				),
			);
			return;
		}

		if (!/^\d+$/.test(trimmedValue)) {
			return;
		}

		const numericValue = Number(trimmedValue);

		if (numericValue < 1 || numericValue > maxValue) {
			return;
		}

		setBoard((currentBoard) =>
			currentBoard.map((row, currentRowIndex) =>
				currentRowIndex === rowIndex
					? row.map((cell, currentColIndex) => (currentColIndex === colIndex ? String(numericValue) : cell))
					: row,
			),
		);
	}

	function handleDimensionChange(nextK, nextN) {
		setK(nextK);
		setN(nextN);
		setBoard(createBoard(nextK * nextN));
		setParseError('');
	}

	function handleSudokuTextChange(event) {
		const nextValue = event.target.value;
		setSudokuText(nextValue);

		const parsedSudoku = parseSudokuString(nextValue);

		if (!parsedSudoku.valid) {
			setParseError('The current string does not correspond to a valid sudoku.');
			return;
		}

		setParseError('');
		setK(parsedSudoku.k);
		setN(parsedSudoku.n);
		setBoard(parsedSudoku.board);
	}

	return (
		<section id="manual-sudoku" className="page-section manual-sudoku-section">
			<div className="section-inner">
				<h2>Manual Sudoku Input</h2>
				<p className="section-copy">
					A [k, n]-sudoku consists of k² squares of size n × n arranged in k rows of k squares and uses numbers 1
					through n².
				</p>

				<div className="manual-sudoku-controls" aria-label="Sudoku size controls">
					<label className="manual-sudoku-field" htmlFor="manual-sudoku-k">
						<span>k</span>
						<input
							id="manual-sudoku-k"
							type="number"
							min="1"
							step="1"
							value={k}
							onChange={(event) => handleDimensionChange(Math.max(1, Number(event.target.value) || 1), n)}
						/>
					</label>

					<label className="manual-sudoku-field" htmlFor="manual-sudoku-n">
						<span>n</span>
						<input
							id="manual-sudoku-n"
							type="number"
							min="1"
							step="1"
							value={n}
							onChange={(event) => handleDimensionChange(k, Math.max(1, Number(event.target.value) || 1))}
						/>
					</label>

					<div className="manual-sudoku-meta">
						<p>
							Board size: {boardSize} × {boardSize}
						</p>
						<p>Allowed values: 1 to {maxValue}</p>
					</div>
				</div>

				<div
					className="manual-sudoku-board"
					style={{ gridTemplateColumns: `repeat(${boardSize}, minmax(2rem, 1fr))` }}
					role="grid"
					aria-label={`Manual sudoku board with size ${boardSize} by ${boardSize}`}
				>
					{board.map((row, rowIndex) =>
						row.map((cell, colIndex) => {
							const isBlockBoundaryRight = (colIndex + 1) % Math.max(1, n) === 0 && colIndex !== boardSize - 1;
							const isBlockBoundaryBottom = (rowIndex + 1) % Math.max(1, n) === 0 && rowIndex !== boardSize - 1;

							return (
								<input
									key={`manual-cell-${rowIndex}-${colIndex}`}
									className="manual-sudoku-cell"
									style={{
										borderRightWidth: isBlockBoundaryRight ? '3px' : '1px',
										borderBottomWidth: isBlockBoundaryBottom ? '3px' : '1px',
									}}
									type="text"
									inputMode="numeric"
									maxLength={String(maxValue).length}
									value={cell}
									onChange={(event) => handleCellChange(rowIndex, colIndex, event.target.value)}
									aria-label={`Row ${rowIndex + 1}, column ${colIndex + 1}`}
								/>
							);
						}),
					)}
				</div>

				<div className="manual-sudoku-string-field">
					<label htmlFor="manual-sudoku-string">Sudoku string</label>
					<textarea
						id="manual-sudoku-string"
						className="manual-sudoku-string-input"
						rows={2}
						value={sudokuText}
						onChange={handleSudokuTextChange}
						spellCheck={false}
						aria-label="Sudoku string representation"
					/>
					<p className="manual-sudoku-string-hint">{'Format: Sudoku{(k,n)(%board)}'}</p>
				</div>

				{parseError && (
					<div className="manual-sudoku-error" role="alert">
						{parseError}
					</div>
				)}
			</div>
		</section>
	);
}

export default ManualSudokuSection;