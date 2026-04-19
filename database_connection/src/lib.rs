use sqlx::{Row, sqlite::{SqliteConnectOptions, SqlitePool, SqlitePoolOptions}};
use sudoku_engine::{Sudoku};
use std::{hash::{DefaultHasher, Hash, Hasher}, str::FromStr};

fn hash_object<T: Hash> (t: &T)-> i64{
    let mut s = DefaultHasher::new();
    t.hash(&mut s);
    s.finish() as i64
}
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
    let hash = hash_object(&format!("{}{}{:?}",unsolved_sudoku.k,unsolved_sudoku.n,&unsolved_sudoku.board));

    sqlx::query("INSERT INTO sudokus (hash, squares, nums, unsolved, solved) VALUES (?, ?, ?, ?, ?)")
        .bind(&hash)
        .bind(unsolved_sudoku.k)
        .bind(unsolved_sudoku.n)
        .bind(hash_object(&unsolved_sudoku.board).to_string())
        .bind(hash_object(&solved_sudoku.board).to_string())
        .execute(pool)
        .await?;

    println!("Successfully saved puzzle to database.db!");
    Ok(())
}

pub async fn find_sudoku (unsolved_sudoku: &Sudoku, pool: &SqlitePool) -> Result<String, sqlx::Error> {
    let hash = hash_object(&format!("{}{}{:?}",unsolved_sudoku.k,unsolved_sudoku.n,&unsolved_sudoku.board));

    let row = sqlx::query("SELECT solved FROM sudokus WHERE hash = ?")
        .bind(hash)
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

