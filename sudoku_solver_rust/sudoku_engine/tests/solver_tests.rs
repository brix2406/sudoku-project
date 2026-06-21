use std::sync::atomic::AtomicBool;
use sudoku_engine::{Board, Sudoku, solve, verify_solution};

fn rows_to_board(rows: Vec<Vec<&str>>) -> Board {
    rows.into_iter()
        .map(|row| row.into_iter().map(|s| s.to_string()).collect())
        .collect()
}

fn get_test_board() -> Board {
    rows_to_board(vec![
        vec![".", "3", ".", ".", "7", ".", ".", ".", "."],
        vec!["6", ".", ".", "1", "9", "5", ".", ".", "."],
        vec![".", "9", "8", ".", ".", ".", ".", "6", "."],
        vec!["8", ".", ".", ".", "6", ".", ".", ".", "3"],
        vec!["4", ".", ".", "8", ".", "3", ".", ".", "1"],
        vec!["7", ".", ".", ".", "2", ".", ".", ".", "6"],
        vec![".", "6", ".", ".", ".", ".", "2", "8", "."],
        vec![".", ".", ".", "4", "1", "9", ".", ".", "5"],
        vec![".", ".", ".", ".", "8", ".", ".", "7", "9"],
    ])
}

fn get_multi_solution_board() -> Board {
    rows_to_board(vec![
        vec!["5", "3", "4", "6", "7", "8", "9", ".", "."],
        vec!["6", "7", ".", ".", "9", "5", "3", "4", "8"],
        vec![".", "9", "8", "3", "4", ".", "5", "6", "7"],
        vec!["8", "5", "9", "7", "6", ".", "4", ".", "3"],
        vec!["4", ".", "6", "8", "5", "3", "7", "9", "."],
        vec!["7", ".", "3", "9", ".", "4", "8", "5", "6"],
        vec!["9", "6", ".", "5", "3", "7", ".", "8", "4"],
        vec![".", "8", "7", "4", ".", "9", "6", "3", "5"],
        vec!["3", "4", "5", ".", "8", "6", ".", "7", "9"],
    ])
}

fn assert_clues_preserved(initial: &Board, solved: &Board) {
    for row in 0..initial.len() {
        for col in 0..initial[row].len() {
            if initial[row][col] != "." {
                assert_eq!(
                    solved[row][col],
                    initial[row][col],
                    "Solver changed a fixed clue at row {}, col {}",
                    row,
                    col
                );
            }
        }
    }
}

#[test]
fn test_solve_standard_9x9() {
    let mut sudoku = Sudoku::new(3, 3, get_test_board());

    let expected_sol = rows_to_board(vec![
        vec!["5", "3", "4", "6", "7", "8", "9", "1", "2"],
        vec!["6", "7", "2", "1", "9", "5", "3", "4", "8"],
        vec!["1", "9", "8", "3", "4", "2", "5", "6", "7"],
        vec!["8", "5", "9", "7", "6", "1", "4", "2", "3"],
        vec!["4", "2", "6", "8", "5", "3", "7", "9", "1"],
        vec!["7", "1", "3", "9", "2", "4", "8", "5", "6"],
        vec!["9", "6", "1", "5", "3", "7", "2", "8", "4"],
        vec!["2", "8", "7", "4", "1", "9", "6", "3", "5"],
        vec!["3", "4", "5", "2", "8", "6", "1", "7", "9"],
    ]);

    let success = solve(&mut sudoku, &AtomicBool::new(false));

    assert!(success, "The solver failed to find a solution.");
    assert_eq!(
        sudoku.board, expected_sol,
        "The solved board does not match the expected solution."
    );
}

#[test]
fn test_already_solved_board() {
    let solved_board = rows_to_board(vec![
        vec!["5", "3", "4", "6", "7", "8", "9", "1", "2"],
        vec!["6", "7", "2", "1", "9", "5", "3", "4", "8"],
        vec!["1", "9", "8", "3", "4", "2", "5", "6", "7"],
        vec!["8", "5", "9", "7", "6", "1", "4", "2", "3"],
        vec!["4", "2", "6", "8", "5", "3", "7", "9", "1"],
        vec!["7", "1", "3", "9", "2", "4", "8", "5", "6"],
        vec!["9", "6", "1", "5", "3", "7", "2", "8", "4"],
        vec!["2", "8", "7", "4", "1", "9", "6", "3", "5"],
        vec!["3", "4", "5", "2", "8", "6", "1", "7", "9"],
    ]);

    let mut sudoku = Sudoku::new(3, 3, solved_board.clone());

    let success = solve(&mut sudoku, &AtomicBool::new(false));
    assert!(success);
    assert_eq!(sudoku.board, solved_board);
}

#[test]
fn test_multiple_solutions_returns_valid_grid() {
    let initial = get_multi_solution_board();
    let mut sudoku = Sudoku::new(3, 3, initial.clone());

    let success = solve(&mut sudoku, &AtomicBool::new(false));

    assert!(success, "The solver should return a valid solution.");
    assert!(
        verify_solution(&sudoku),
        "The solver produced a board that violates Sudoku rules."
    );
    assert_clues_preserved(&initial, &sudoku.board);
}

#[test]
fn test_unsolvable_9x9_returns_false() {
    let invalid_board = rows_to_board(vec![
        vec!["5", "3", "5", ".", "7", ".", ".", ".", "."],
        vec!["6", ".", ".", "1", "9", "5", ".", ".", "."],
        vec![".", "9", "8", ".", ".", ".", ".", "6", "."],
        vec!["8", ".", ".", ".", "6", ".", ".", ".", "3"],
        vec!["4", ".", ".", "8", ".", "3", ".", ".", "1"],
        vec!["7", ".", ".", ".", "2", ".", ".", ".", "6"],
        vec![".", "6", ".", ".", ".", ".", "2", "8", "."],
        vec![".", ".", ".", "4", "1", "9", ".", ".", "5"],
        vec![".", ".", ".", ".", "8", ".", ".", "7", "9"],
    ]);

    let mut sudoku = Sudoku::new(3, 3, invalid_board);

    let success = solve(&mut sudoku, &AtomicBool::new(false));
    assert!(!success, "Unsolvable puzzle should return false.");
}

#[test]
fn test_single_missing_cell_is_verified() {
    let almost_solved = rows_to_board(vec![
        vec!["5", "3", "4", "6", "7", "8", "9", "1", "."],
        vec!["6", "7", "2", "1", "9", "5", "3", "4", "8"],
        vec!["1", "9", "8", "3", "4", "2", "5", "6", "7"],
        vec!["8", "5", "9", "7", "6", "1", "4", "2", "3"],
        vec!["4", "2", "6", "8", "5", "3", "7", "9", "1"],
        vec!["7", "1", "3", "9", "2", "4", "8", "5", "6"],
        vec!["9", "6", "1", "5", "3", "7", "2", "8", "4"],
        vec!["2", "8", "7", "4", "1", "9", "6", "3", "5"],
        vec!["3", "4", "5", "2", "8", "6", "1", "7", "9"],
    ]);

    let mut sudoku = Sudoku::new(3, 3, almost_solved);
    assert!(solve(&mut sudoku, &AtomicBool::new(false)));
    assert!(verify_solution(&sudoku));
}

#[test]
fn test_cancel_flag_aborts_solve() {
    use std::sync::atomic::Ordering;
    let board = (0..9).map(|_| vec![".".to_string(); 9]).collect();
    let mut sudoku = Sudoku::new(3, 3, board);
    let cancel = AtomicBool::new(true); // pre-cancelled
    let result = solve(&mut sudoku, &cancel);
    assert!(!result, "Pre-cancelled solve must return false immediately");
}
