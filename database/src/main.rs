use sqlx::{Row, sqlite::SqlitePool};
use database::{add_sudoku, find_sudoku};
use sudoku_engine::{Sudoku};

#[tokio::main]
async fn main() -> Result<(), sqlx::Error> {
    // 1. Create the connection pool to the file
    let pool = SqlitePool::connect("sqlite://database.db?mode=rwc").await?;
    // Note: ?mode=rwc stands for Read/Write/Create

    // 2. Create a table if it doesn't exist (Initial Setup)
    sqlx::query(
        "CREATE TABLE IF NOT EXISTS sudokus (
            unsolved TEXT NOT NULL,
            solved TEXT NOT NULL
        );"
    )
    .execute(&pool)
    .await?;

    // 3. Insert a new Sudoku board into the file
    let sudoku = Sudoku::new(
        3,
        3,
        vec![
            vec![".", "3", ".", ".", "7", ".", ".", ".", "."],
            vec!["6", ".", ".", "1", "9", "5", ".", ".", "."],
            vec![".", "9", "8", ".", ".", ".", ".", "6", "."],
            vec!["8", ".", ".", ".", ".", ".", ".", ".", "3"],
            vec![".", ".", ".", ".", ".", "3", ".", ".", "1"],
            vec!["7", ".", ".", ".", ".", ".", ".", ".", "6"],
            vec![".", "6", ".", ".", ".", ".", "2", "8", "."],
            vec![".", ".", ".", "4", "1", "9", ".", ".", "5"],
            vec![".", ".", ".", ".", "8", ".", ".", "7", "9"],
        ]
        .into_iter()
        .map(|row| row.into_iter().map(|s| s.to_string()).collect())
        .collect(),
    );
    
    
    let sudoku_board: String;
    match find_sudoku(&sudoku, &pool).await{
        Ok(sudoku_sol) => sudoku_board = sudoku_sol,
        Err(e) => {eprintln!("{}", e);
                sudoku_board = "Failed to find board".to_string();
                add_sudoku(&sudoku, &sudoku, &pool).await?;
            },
    }

    println!("Found board: {}",sudoku_board);
    Ok(())
}