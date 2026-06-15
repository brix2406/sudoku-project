use serde::{Serialize, Deserialize};

pub type Board = Vec<Vec<String>>;

#[derive(Serialize, Deserialize, Debug)]
pub struct Sudoku {
    pub is_solved: bool,
    pub k: u16,
    pub n: u16,
    pub board: Board,
}

impl Sudoku {
    pub fn new(k: u16, n: u16, board: Board) -> Self {
        Self {
            is_solved: false,
            k,
            n,
            board,
        }
    }
}

pub fn prettyprint(sudoku: &Board) {
    for (i, l) in sudoku.iter().enumerate() {
        for (j, c) in l.iter().enumerate() {
            print!("{} ", c);
            if j % 3 == 2 {
                print!("|")
            }
        }
        println!("");
        if i % 3 == 2 {
            for _ in 0..sudoku.len() {
                print!("--");
            }
            println!("---");
        }
    }
    println!("\n")
}

fn get_candidates(sudoku: &Sudoku, x: usize, y: usize) -> Vec<u16> {
    let mut candidates: Vec<u16> = (1..sudoku.n * sudoku.n + 1).collect();

    for i in 0..sudoku.n * sudoku.k {
        let c = &sudoku.board[i as usize][x];
        if c != "." {
            if let Ok(num) = c.parse::<u16>() {
                if let Some(pos) = candidates.iter().position(|&val| val == num) {
                    candidates.remove(pos);
                }
            }
        }

        let c = &sudoku.board[y][i as usize];
        if c != "." {
            if let Ok(num) = c.parse::<u16>() {
                if let Some(pos) = candidates.iter().position(|&val| val == num) {
                    candidates.remove(pos);
                }
            }
        }
    }

    let square_x = x / sudoku.k as usize;
    let square_y = y / sudoku.k as usize;
    for i in 0..sudoku.n {
        for j in 0..sudoku.n {
            let c =
                &sudoku.board[square_y * sudoku.n as usize + i as usize][square_x * sudoku.n as usize + j as usize];
            if c != "." {
                if let Ok(num) = c.parse::<u16>() {
                    if let Some(pos) = candidates.iter().position(|&val| val == num) {
                        candidates.remove(pos);
                    }
                }
            }
        }
    }
    candidates
}

fn find_best_candidate(sudoku: &mut Sudoku) -> Option<(u16, u16, Vec<u16>)> {
    let mut best_option: usize = usize::MAX;
    let mut best_coords: (u16, u16) = (0, 0);
    let mut candidates = Vec::<u16>::new();
    let mut has_free = false;
    for i in 0..sudoku.k * sudoku.n {
        for j in 0..sudoku.k * sudoku.n {
            if sudoku.board[i as usize][j as usize] == "." {
                has_free = true;
                let v = get_candidates(sudoku, j as usize, i as usize);
                if v.len() < best_option {
                    best_option = v.len();
                    best_coords = (j, i);
                    candidates = v;
                }
            }
        }
    }
    if best_option == usize::MAX {
        sudoku.is_solved = !has_free;
        return None;
    }
    Some((best_coords.0, best_coords.1, candidates))
}

pub fn solve(sudoku: &mut Sudoku) -> bool {
    let candidate = find_best_candidate(sudoku);
    match candidate {
        Some((x, y, candidates)) => {
            for i in candidates {
                sudoku.board[y as usize][x as usize] = i.to_string();
                if solve(sudoku) {
                    return true;
                } else {
                    sudoku.board[y as usize][x as usize] = ".".to_string();
                }
            }
            false
        }
        None => sudoku.is_solved,
    }
}

/// Checks that the given (pre-filled) cells do not conflict: no duplicate
/// value in any row, column, or block, and every non-empty cell is a valid
/// number in 1..=n². Empty cells (".") are skipped. A puzzle that fails this
/// check has no solution, so it must never be handed to the solver.
pub fn validate_givens(sudoku: &Sudoku) -> bool {
    let size = (sudoku.k * sudoku.n) as usize;
    let max_value = (sudoku.n * sudoku.n) as usize;
    if sudoku.board.len() != size {
        return false;
    }
    if sudoku.board.iter().any(|row| row.len() != size) {
        return false;
    }

    let mut seen = vec![false; max_value + 1];

    // Rows
    for row in &sudoku.board {
        seen.fill(false);
        for cell in row {
            if cell == "." {
                continue;
            }
            let Ok(value) = cell.parse::<usize>() else {
                return false;
            };
            if value == 0 || value > max_value || seen[value] {
                return false;
            }
            seen[value] = true;
        }
    }

    // Columns
    for col in 0..size {
        seen.fill(false);
        for row in 0..size {
            let cell = &sudoku.board[row][col];
            if cell == "." {
                continue;
            }
            let Ok(value) = cell.parse::<usize>() else {
                return false;
            };
            if value == 0 || value > max_value || seen[value] {
                return false;
            }
            seen[value] = true;
        }
    }

    // Blocks
    let block = sudoku.n as usize;
    for block_y in 0..sudoku.k as usize {
        for block_x in 0..sudoku.k as usize {
            seen.fill(false);
            for dy in 0..block {
                for dx in 0..block {
                    let cell = &sudoku.board[block_y * block + dy][block_x * block + dx];
                    if cell == "." {
                        continue;
                    }
                    let Ok(value) = cell.parse::<usize>() else {
                        return false;
                    };
                    if value == 0 || value > max_value || seen[value] {
                        return false;
                    }
                    seen[value] = true;
                }
            }
        }
    }

    true
}

pub fn verify_solution(sudoku: &Sudoku) -> bool {
    let size = (sudoku.k * sudoku.n) as usize;
    if sudoku.board.len() != size {
        return false;
    }
    if sudoku.board.iter().any(|row| row.len() != size) {
        return false;
    }

    let mut row_seen = vec![false; size + 1];
    for row in &sudoku.board {
        row_seen.fill(false);
        for cell in row {
            let Ok(value) = cell.parse::<usize>() else {
                return false;
            };
            if value == 0 || value > size || row_seen[value] {
                return false;
            }
            row_seen[value] = true;
        }
    }

    let mut col_seen = vec![false; size + 1];
    for col in 0..size {
        col_seen.fill(false);
        for row in 0..size {
            let Ok(value) = sudoku.board[row][col].parse::<usize>() else {
                return false;
            };
            if value == 0 || value > size || col_seen[value] {
                return false;
            }
            col_seen[value] = true;
        }
    }

    let block = sudoku.n as usize;
    let mut block_seen = vec![false; size + 1];
    for block_y in 0..sudoku.k as usize {
        for block_x in 0..sudoku.k as usize {
            block_seen.fill(false);
            for dy in 0..block {
                for dx in 0..block {
                    let row = block_y * block + dy;
                    let col = block_x * block + dx;
                    let Ok(value) = sudoku.board[row][col].parse::<usize>() else {
                        return false;
                    };
                    if value == 0 || value > size || block_seen[value] {
                        return false;
                    }
                    block_seen[value] = true;
                }
            }
        }
    }

    true
}

#[cfg(test)]
mod tests {
    use super::*;

    fn board_from(rows: &[&str]) -> Board {
        rows.iter()
            .map(|row| row.split(',').map(|s| s.to_string()).collect())
            .collect()
    }

    fn empty_board(size: usize) -> Board {
        vec![vec![".".to_string(); size]; size]
    }

    #[test]
    fn empty_board_is_valid() {
        let sudoku = Sudoku::new(3, 3, empty_board(9));
        assert!(validate_givens(&sudoku));
    }

    #[test]
    fn single_given_is_valid() {
        let mut board = empty_board(9);
        board[0][0] = "1".to_string();
        let sudoku = Sudoku::new(3, 3, board);
        assert!(validate_givens(&sudoku));
    }

    #[test]
    fn duplicate_in_row_is_invalid() {
        let mut board = empty_board(9);
        board[0][0] = "1".to_string();
        board[0][5] = "1".to_string();
        let sudoku = Sudoku::new(3, 3, board);
        assert!(!validate_givens(&sudoku));
    }

    #[test]
    fn duplicate_in_column_is_invalid() {
        let mut board = empty_board(9);
        board[0][0] = "7".to_string();
        board[8][0] = "7".to_string();
        let sudoku = Sudoku::new(3, 3, board);
        assert!(!validate_givens(&sudoku));
    }

    #[test]
    fn duplicate_in_block_is_invalid() {
        let mut board = empty_board(9);
        // (0,0) and (1,1) are in the same 3x3 block but different row/column.
        board[0][0] = "5".to_string();
        board[1][1] = "5".to_string();
        let sudoku = Sudoku::new(3, 3, board);
        assert!(!validate_givens(&sudoku));
    }

    #[test]
    fn out_of_range_given_is_invalid() {
        let mut board = empty_board(9);
        board[0][0] = "10".to_string();
        let sudoku = Sudoku::new(3, 3, board);
        assert!(!validate_givens(&sudoku));
    }

    #[test]
    fn valid_distinct_givens_pass() {
        let board = board_from(&[
            "5,3,.,.,7,.,.,.,.",
            "6,.,.,1,9,5,.,.,.",
            ".,9,8,.,.,.,.,6,.",
            "8,.,.,.,6,.,.,.,3",
            "4,.,.,8,.,3,.,.,1",
            "7,.,.,.,2,.,.,.,6",
            ".,6,.,.,.,.,2,8,.",
            ".,.,.,4,1,9,.,.,5",
            ".,.,.,.,8,.,.,7,9",
        ]);
        let sudoku = Sudoku::new(3, 3, board);
        assert!(validate_givens(&sudoku));
    }
}