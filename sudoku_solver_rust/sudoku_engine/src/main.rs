type Board = Vec<Vec<String>>;
struct Sudoku{
    is_solved: bool,
    k:u16,
    n:u16,
    board:Board
}
fn main() {
    let mut sudokudo= Sudoku{is_solved:false,k:3,n:3,board: vec![
        vec!["5","3",".",".","7",".",".",".","."].iter().map(|s| s.to_string()).collect(),
        vec!["6",".",".","1","9","5",".",".",".",].iter().map(|s| s.to_string()).collect(),
        vec![".","9","8",".",".",".",".","6","."].iter().map(|s| s.to_string()).collect(),
        vec!["8",".",".",".","6",".",".",".","3"].iter().map(|s| s.to_string()).collect(),
        vec!["4",".",".","8",".","3",".",".","1"].iter().map(|s| s.to_string()).collect(),
        vec!["7",".",".",".","2",".",".",".","6"].iter().map(|s| s.to_string()).collect(),
        vec![".","6",".",".",".",".","2","8","."].iter().map(|s| s.to_string()).collect(),
        vec![".",".",".","4","1","9",".",".","5"].iter().map(|s| s.to_string()).collect(),
        vec![".",".",".",".","8",".",".","7","9"].iter().map(|s| s.to_string()).collect()
        ]};
        let sudokudo_sol: Board = vec![
        vec!["5","3","4","6","7","8","9","1","2"].iter().map(|s| s.to_string()).collect(),
        vec!["6","7","2","1","9","5","3","4","8"].iter().map(|s| s.to_string()).collect(),
        vec!["1","9","8","3","4","2","5","6","7"].iter().map(|s| s.to_string()).collect(),
        vec!["8","5","9","7","6","1","4","2","3"].iter().map(|s| s.to_string()).collect(),
        vec!["4","2","6","8","5","3","7","9","1"].iter().map(|s| s.to_string()).collect(),
        vec!["7","1","3","9","2","4","8","5","6"].iter().map(|s| s.to_string()).collect(),
        vec!["9","6","1","5","3","7","2","8","4"].iter().map(|s| s.to_string()).collect(),
        vec!["2","8","7","4","1","9","6","3","5"].iter().map(|s| s.to_string()).collect(),
        vec!["3","4","5","2","8","6","1","7","9"].iter().map(|s| s.to_string()).collect()
        ];
    prettyprint(&sudokudo.board);
    solve(&mut sudokudo);
    prettyprint(&sudokudo.board);
    prettyprint(&sudokudo_sol);
}

fn prettyprint(sudoku: &Board){
    for (i,l) in sudoku.iter().enumerate(){
        for (j, c) in l.iter().enumerate(){
            print!("{} ", c);
            if j%3 == 2 {print!("|")}
        }
        println!("");
        if i%3 == 2 {
            for _ in 0..sudoku.len(){
                print!("--");
            }
            println!("---");
        }
    }
    println!("\n")
}

fn get_candidates(sudoku:&Sudoku, x:usize,y:usize) -> Vec<u16>{
    let mut candidates: Vec<u16> = (1..sudoku.n*sudoku.n+1).collect();
        
        // Check columns and rows
        for i in 0..sudoku.n*sudoku.k {
            // Check column
            let c = &sudoku.board[i as usize][x];
            if c != "." {
                if let Ok(num) = c.parse::<u16>() {
                    if let Some(pos) = candidates.iter().position(|&val| val == num) {
                        candidates.remove(pos);
                    }
                }
            }
            
            // Check row
            let c = &sudoku.board[y][i as usize];
            if c != "." {
                if let Ok(num) = c.parse::<u16>() {
                    if let Some(pos) = candidates.iter().position(|&val| val == num) {
                        candidates.remove(pos);
                    }
                }
            }
        }

            //check square
        let square_x = x /sudoku.k as usize;
        let square_y = y /sudoku.k as usize;
        println!("In square: {}, {}", square_x,square_y);
            for i in 0..sudoku.n{
                for j in 0..sudoku.n{
                    let c = &sudoku.board[square_y*sudoku.n as usize + i as usize][square_x* sudoku.n as usize + j as usize];
                    if c != "." {
                        if let Ok(num) = c.parse::<u16>() {
                            if let Some(pos) = candidates.iter().position(|&val| val == num) {
                                candidates.remove(pos);
                            }
                        }
                    }
        }
        }
    return candidates
}

fn find_best_candidate(sudoku: &mut Sudoku) -> Option<(u16,u16,Vec<u16>)>{
    let mut best_option: usize= std::usize::MAX;
    let mut best_coords: (u16,u16) = (0,0);
    let mut candidates = Vec::<u16>::new();
    let mut has_free = false;
    for i in 0..sudoku.k*sudoku.n{
        for j in 0..sudoku.k*sudoku.n{
            if sudoku.board[i as usize][j as usize] == "."{
                has_free = true;
                let v = get_candidates(sudoku, j as usize, i as usize);
                if v.len() < best_option {
                    best_option = v.len();
                    best_coords = (j,i);
                    candidates = v;
                }
            }
        }
    }
    if best_option == std::usize::MAX{
        sudoku.is_solved = !has_free;
        return None
    }
    return Some((best_coords.0, best_coords.1, candidates))
}

fn solve(sudoku: &mut Sudoku) -> Option<&Sudoku>{
    let candidate = find_best_candidate(sudoku);
    match candidate{
        Some((x,y,candidates)) => {
            for i in candidates{
                sudoku.board[y as usize][x as usize] = i.to_string();
                solve(sudoku);
                if sudoku.is_solved{
                    return Some(sudoku)
                }
            }
            return None
        }
        None => {if sudoku.is_solved {
            return Some(sudoku)
            }
            return None
        }
    }
}