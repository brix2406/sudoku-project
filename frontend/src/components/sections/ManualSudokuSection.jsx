
import { memo, useCallback, useState, startTransition, useRef } from 'react';

// Upper bound on the board side length (k * n). The grid renders one <input> per
// cell, so the DOM node count grows as boardSize². Capping it keeps the page from
// freezing/crashing on very large dimensions (e.g. k=30, n=3 -> 8,100 inputs).
const MAX_BOARD_SIZE = 50; // 50 × 50 = 2,500 cells

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
	const [kInput, setKInput] = useState('3');
	const [nInput, setNInput] = useState('3');
	const [board, setBoard] = useState(() => createBoard(9));
	const [sudokuText, setSudokuText] = useState(() => serializeSudoku(3, 3, createBoard(9)));
	const [parseError, setParseError] = useState('');
	const [dimensionNotice, setDimensionNotice] = useState('');

	const boardSize = Math.max(1, k) * Math.max(1, n);
	const maxValue = Math.max(1, n) * Math.max(1, n);
	const cellMaxLength = String(maxValue).length;

    const parseTimer = useRef(null);

	const updateBoardState = useCallback((nextK, nextN, nextBoard) => {
		setK(nextK);
		setN(nextN);
		setKInput(String(nextK));
		setNInput(String(nextN));
		setBoard(nextBoard);
		setSudokuText(serializeSudoku(nextK, nextN, nextBoard));
		setParseError('');
		setDimensionNotice('');
	}, []);

	const handleCellChange = useCallback((rowIndex, colIndex, value) => {
        const trimmedValue = value.trim();
        let cellValueToSet = '';

        // If the input is not empty, validate it before setting the value
        if (trimmedValue !== '') {
            if (!/^\d+$/.test(trimmedValue)) {
                return; // Exit early if not a number
            }

            const numericValue = Number(trimmedValue);

            if (numericValue < 1 || numericValue > maxValue) {
                return; // Exit early if out of bounds
            }
            
            cellValueToSet = String(numericValue);
        }

        setBoard((currentBoard) => {
            const nextBoard = [...currentBoard];
            nextBoard[rowIndex] = [...nextBoard[rowIndex]];
            nextBoard[rowIndex][colIndex] = cellValueToSet;
            
            //Makes updating the sudoku-string a lower priority for more smooth user experience
            startTransition(() => {
                setSudokuText(serializeSudoku(k, n, nextBoard));
            });
            
            return nextBoard;
        });
    }, [k, n, maxValue]);

	const handleDimensionChange = useCallback((nextK, nextN) => {
		if (nextK * nextN > MAX_BOARD_SIZE) {
			setDimensionNotice(
				`Board size is capped at ${MAX_BOARD_SIZE} × ${MAX_BOARD_SIZE}. Reduce k or n so that k × n ≤ ${MAX_BOARD_SIZE}.`,
			);
			return;
		}

		updateBoardState(nextK, nextN, createBoard(nextK * nextN));
	}, [updateBoardState]);

	const handleDimensionInputChange = useCallback((axis, rawValue) => {
		// Only accept integer input: strip anything that is not a digit. This keeps
		// the controlled value clean even if non-integer text is pasted in.
		const sanitizedValue = rawValue.replace(/\D/g, '');

		if (axis === 'k') {
			setKInput(sanitizedValue);
		} else {
			setNInput(sanitizedValue);
		}

		if (sanitizedValue === '') {
			return;
		}

		const numericValue = Number(sanitizedValue);

		if (numericValue < 1) {
			return;
		}

		if (axis === 'k') {
			if (numericValue === k) return;
			handleDimensionChange(numericValue, n);
		} else {
			if (numericValue === n) return;
			handleDimensionChange(k, numericValue);
		}
	}, [k, n, handleDimensionChange]);

	const blockNonIntegerKeys = useCallback((event) => {
		// number inputs natively allow '.', 'e', '+', '-'; reject them so only integers can be typed.
		if (['e', 'E', '+', '-', '.', ','].includes(event.key)) {
			event.preventDefault();
		}
	}, []);

	const handleSudokuTextChange = useCallback((event) => {
		const nextValue = event.target.value;
		setSudokuText(nextValue);

        if (parseTimer.current){
            clearTimeout(parseTimer.current)
        };

         
        parseTimer.current = setTimeout(()=> {
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

            if (parsedSudoku.k * parsedSudoku.n > MAX_BOARD_SIZE) {
                setParseError(
                    `This sudoku is too large to display. The board size (k × n) must be at most ${MAX_BOARD_SIZE} × ${MAX_BOARD_SIZE}.`,
                );
                return;
            }

		setParseError('');
		updateBoardState(parsedSudoku.k, parsedSudoku.n, parsedSudoku.board);
        },500)
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
							value={kInput}
							onKeyDown={blockNonIntegerKeys}
							onChange={(event) => handleDimensionInputChange('k', event.target.value)}
						/>
					</label>

					<label className="manual-sudoku-field" htmlFor="manual-sudoku-n">
						<span>n</span>
						<input
							id="manual-sudoku-n"
							type="number"
							min="1"
							step="1"
							value={nInput}
							onKeyDown={blockNonIntegerKeys}
							onChange={(event) => handleDimensionInputChange('n', event.target.value)}
						/>
					</label>

					<div className="manual-sudoku-meta">
						<p>
							Board size: {boardSize} × {boardSize}
						</p>
						<p>Allowed values: 1 to {maxValue}</p>
					</div>
				</div>

				{dimensionNotice && (
					<div className="manual-sudoku-error" role="alert">
						{dimensionNotice}
					</div>
				)}

                <div className="manual-sudoku-board-scroll" aria-label="Scrollable sudoku board container">
					<div
						className="manual-sudoku-board"
						style={{ gridTemplateColumns: `repeat(${boardSize}, var(--manual-sudoku-cell-size))` }}
						role="grid"
						aria-label={`Manual sudoku board with size ${boardSize} by ${boardSize}`}
					>
					{/* Flat Array Render Loop */}
					{Array.from({ length: boardSize * boardSize }).map((_, index) => {
						const rowIndex = Math.floor(index / boardSize);
						const colIndex = index % boardSize;
						const cellValue = board[rowIndex][colIndex];

						const isBlockBoundaryRight = (colIndex + 1) % Math.max(1, n) === 0 && colIndex !== boardSize - 1;
						const isBlockBoundaryBottom = (rowIndex + 1) % Math.max(1, n) === 0 && rowIndex !== boardSize - 1;

						return (
							<SudokuCell
								key={`manual-cell-${rowIndex}-${colIndex}`}
								rowIndex={rowIndex}
								colIndex={colIndex}
								value={cellValue}
								maxLength={cellMaxLength}
								isBlockBoundaryRight={isBlockBoundaryRight}
								isBlockBoundaryBottom={isBlockBoundaryBottom}
								onCellChange={handleCellChange}
							/>
						);
					})}
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

export default memo(ManualSudokuSection);