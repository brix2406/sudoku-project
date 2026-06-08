
import { memo, useCallback, useState } from 'react';

function createBoard(size) {
	return Array.from({ length: size }, () => Array.from({ length: size }, () => ''));
}

function serializeSudoku(k, n, board) {
	const cells = board.flat().map((cell) => (cell === '' ? '0' : cell));
	return `Sudoku{(${k},${n})(${cells.join(',')})}`;
}

const SudokuCell = memo(
	function SudokuCell({ rowIndex, colIndex, value, maxLength, isBlockBoundaryRight, isBlockBoundaryBottom, onCellChange }) {
		return (
			<input
				className="manual-sudoku-cell"
				style={{
					borderRightWidth: isBlockBoundaryRight ? '3px' : '1px',
					borderBottomWidth: isBlockBoundaryBottom ? '3px' : '1px',
				}}
				type="text"
				inputMode="numeric"
				maxLength={maxLength}
				value={value}
				onChange={(event) => onCellChange(rowIndex, colIndex, event.target.value)}
				aria-label={`Row ${rowIndex + 1}, column ${colIndex + 1}`}
			/>
		);
	},
	(previousProps, nextProps) =>
		previousProps.rowIndex === nextProps.rowIndex &&
		previousProps.colIndex === nextProps.colIndex &&
		previousProps.value === nextProps.value &&
		previousProps.maxLength === nextProps.maxLength &&
		previousProps.isBlockBoundaryRight === nextProps.isBlockBoundaryRight &&
		previousProps.isBlockBoundaryBottom === nextProps.isBlockBoundaryBottom,
);

function parseSudokuString(value) {
	const trimmedValue = value.trim();
	const match = /^Sudoku\{\((\d+),(\d+)\)\((.*)\)\}$/.exec(trimmedValue);

	if (!match) {
		return { valid: false, reason: 'invalid-format' };
	}

	const parsedK = Number(match[1]);
	const parsedN = Number(match[2]);

	if (!Number.isInteger(parsedK) || !Number.isInteger(parsedN) || parsedK < 1 || parsedN < 1) {
		return { valid: false, reason: 'invalid-dimensions' };
	}

	const boardSize = parsedK * parsedN;
	const expectedCellCount = boardSize * boardSize;
	const rawCells = match[3].length > 0 ? match[3].split(',') : [];

	const maxValue = parsedN * parsedN;
	const board = createBoard(boardSize);

	for (let cellIndex = 0; cellIndex < Math.min(rawCells.length, expectedCellCount); cellIndex += 1) {
		const cellValue = rawCells[cellIndex].trim();

		if (!/^\d+$/.test(cellValue)) {
			return { valid: false, reason: 'non-numeric-cell' };
		}

		const numericValue = Number(cellValue);

		if (numericValue < 0 || numericValue > maxValue) {
			return { valid: false, reason: 'cell-out-of-range' };
		}

		const rowIndex = Math.floor(cellIndex / boardSize);
		const colIndex = cellIndex % boardSize;
		board[rowIndex][colIndex] = numericValue === 0 ? '' : String(numericValue);
	}

	return {
		valid: true,
		k: parsedK,
		n: parsedN,
		board,
		rawCellCount: rawCells.length,
		expectedCellCount,
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

	const updateBoardState = useCallback((nextK, nextN, nextBoard) => {
		setK(nextK);
		setN(nextN);
		setBoard(nextBoard);
		setSudokuText(serializeSudoku(nextK, nextN, nextBoard));
		setParseError('');
	}, []);

	const handleCellChange = useCallback((rowIndex, colIndex, value) => {
		const trimmedValue = value.trim();

		if (trimmedValue === '') {
			setBoard((currentBoard) => {
				const nextBoard = currentBoard.map((row, currentRowIndex) =>
					currentRowIndex === rowIndex
						? row.map((cell, currentColIndex) => (currentColIndex === colIndex ? '' : cell))
						: row,
				);
				setSudokuText(serializeSudoku(k, n, nextBoard));
				return nextBoard;
			});
			return;
		}

		if (!/^\d+$/.test(trimmedValue)) {
			return;
		}

		const numericValue = Number(trimmedValue);

		if (numericValue < 1 || numericValue > maxValue) {
			return;
		}

		setBoard((currentBoard) => {
			const nextBoard = currentBoard.map((row, currentRowIndex) =>
				currentRowIndex === rowIndex
					? row.map((cell, currentColIndex) => (currentColIndex === colIndex ? String(numericValue) : cell))
					: row,
			);
			setSudokuText(serializeSudoku(k, n, nextBoard));
			return nextBoard;
		});
	}, [k, n, maxValue]);

	const handleDimensionChange = useCallback((nextK, nextN) => {
		updateBoardState(nextK, nextN, createBoard(nextK * nextN));
	}, [updateBoardState]);

	const handleSudokuTextChange = useCallback((event) => {
		const nextValue = event.target.value;
		setSudokuText(nextValue);

		const parsedSudoku = parseSudokuString(nextValue);

		if (!parsedSudoku.valid) {
			if (parsedSudoku.reason === 'cell-out-of-range') {
				setParseError('The current string does not correspond to a valid sudoku. A cell value is larger than n².');
			} else {
				setParseError('The current string does not correspond to a valid sudoku.');
			}
			return;
		}

		if (parsedSudoku.rawCellCount !== parsedSudoku.expectedCellCount) {
			if (parsedSudoku.k === k && parsedSudoku.n === n) {
				setParseError('The current string does not correspond to a valid sudoku.');
				return;
			}
		}

		setParseError('');
		updateBoardState(parsedSudoku.k, parsedSudoku.n, parsedSudoku.board);
	}, [k, n, updateBoardState]);

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

				<div className="manual-sudoku-board-scroll" aria-label="Scrollable sudoku board container">
					<div
						className="manual-sudoku-board"
						style={{ gridTemplateColumns: `repeat(${boardSize}, var(--manual-sudoku-cell-size))` }}
						role="grid"
						aria-label={`Manual sudoku board with size ${boardSize} by ${boardSize}`}
					>
					{board.map((row, rowIndex) =>
						row.map((cell, colIndex) => {
							const isBlockBoundaryRight = (colIndex + 1) % Math.max(1, n) === 0 && colIndex !== boardSize - 1;
							const isBlockBoundaryBottom = (rowIndex + 1) % Math.max(1, n) === 0 && rowIndex !== boardSize - 1;

							return (
								<SudokuCell
									key={`manual-cell-${rowIndex}-${colIndex}`}
									rowIndex={rowIndex}
									colIndex={colIndex}
									value={cell}
									maxLength={String(maxValue).length}
									isBlockBoundaryRight={isBlockBoundaryRight}
									isBlockBoundaryBottom={isBlockBoundaryBottom}
									onCellChange={handleCellChange}
								/>
							);
						}),
					)}
					</div>
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