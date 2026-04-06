use sqlx::{Row, sqlite::SqlitePool};
use sudoku_engine::{Sudoku};
use std::hash::{DefaultHasher, Hash, Hasher};

fn hash_object<T: Hash> (t: &T)-> i64{
    let mut s = DefaultHasher::new();
    t.hash(&mut s);
    s.finish() as i64
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
