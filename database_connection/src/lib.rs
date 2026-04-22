use sqlx::{Row, sqlite::{SqliteConnectOptions, SqlitePool, SqlitePoolOptions}};
use sudoku_engine::Sudoku;
use std::str::FromStr;

pub async fn init_pool(db_path: &str) -> Result<SqlitePool, sqlx::Error> {
    let options = SqliteConnectOptions::from_str(db_path)?
        .create_if_missing(true)
        .pragma("journal_mode", "WAL")      // Turn on write ahead log (WAL) – Required by Marmot
        .pragma("synchronous", "NORMAL");   // Recommended for WAL performance

    let pool = SqlitePoolOptions::new()
        .max_connections(5)
        .connect_with(options)
        .await?;

    sqlx::query(
    "CREATE TABLE IF NOT EXISTS sudokus (
        hash INTEGER NOT NULL,
        squares INTEGER NOT NULL,
        nums INTEGER NOT NULL,
        unsolved TEXT NOT NULL,
        solved TEXT NOT NULL
        );"
    )
    .execute(&pool)
    .await?;

    Ok(pool)
}

pub async fn add_sudoku (unsolved_sudoku: &Sudoku, solved_sudoku: &Sudoku, pool: &SqlitePool) -> Result<(), sqlx::Error> {
    let board_str = format!("{:?}", unsolved_sudoku.board);
    let solved_str = format!("{:?}", solved_sudoku.board);
    
    // Using 0 for the legacy hash column
    let hash: i64 = 0;

    sqlx::query("INSERT INTO sudokus (hash, squares, nums, unsolved, solved) VALUES (?, ?, ?, ?, ?)")
        .bind(&hash)
        .bind(unsolved_sudoku.k)
        .bind(unsolved_sudoku.n)
        .bind(&board_str)
        .bind(&solved_str)
        .execute(pool)
        .await?;

    println!("Successfully saved puzzle to database.db!");
    Ok(())
}

pub async fn find_sudoku (unsolved_sudoku: &Sudoku, pool: &SqlitePool) -> Result<String, sqlx::Error> {
    let board_str = format!("{:?}", unsolved_sudoku.board);

    let row = sqlx::query("SELECT solved FROM sudokus WHERE unsolved = ?")
        .bind(&board_str)
        .fetch_one(pool)
        .await?;
    
    Ok(row.get::<String, &str>("solved"))
}

pub async fn print_wal_status(pool: &SqlitePool) -> Result<(), sqlx::Error> {
    let row = sqlx::query("PRAGMA wal_checkpoint(PASSIVE);")
        .fetch_one(pool)
        .await?;
    
    // The pragma returns 3 columns:
    // 0: busy (0 for success, 1 for active readers/writers)
    // 1: log size in pages
    // 2: checkpointed pages
    let busy: i32 = row.try_get(0)?;
    let log_size: i32 = row.try_get(1)?;
    let checkpointed: i32 = row.try_get(2)?;

    println!("WAL Status: busy={}, log_size={} pages, checkpointed={} pages", busy, log_size, checkpointed);
    Ok(())
}

