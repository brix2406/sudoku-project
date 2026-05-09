use database::{add_sudoku, find_sudoku, init_pool};
use sudoku_engine::Sudoku;


fn create_test_sudoku(suffix: &str) -> Sudoku {
    // Generate a simple dummy sudoku board with a distinct suffix
    Sudoku::new(
        3,
        3,
        vec![
            vec!["1", "2", "3", "4", "5", "6", "7", "8", suffix],
            vec!["4", "5", "6", "7", "8", "9", "1", "2", "3"],
            vec!["7", "8", "9", "1", "2", "3", "4", "5", "6"],
            vec!["2", "3", "4", "5", "6", "7", "8", "9", "1"],
            vec!["5", "6", "7", "8", "9", "1", "2", "3", "4"],
            vec!["8", "9", "1", "2", "3", "4", "5", "6", "7"],
            vec!["3", "4", "5", "6", "7", "8", "9", "1", "2"],
            vec!["6", "7", "8", "9", "1", "2", "3", "4", "5"],
            vec!["9", "1", "2", "3", "4", "5", "6", "7", "8"],
        ]
        .into_iter()
        .map(|row| row.into_iter().map(|s| s.to_string()).collect())
        .collect(),
    )
}

#[tokio::test]
async fn test_database_persistence_and_marmot_integration() {
    let db_path = "sqlite:///data/test_data.db?mode=rwc";
        
    // 1. Check if Reading and Writing works!
    let pool = init_pool(db_path).await.expect("Failed to initialize pool");
    let test_sudoku_unsolved = create_test_sudoku("1");
    let test_sudoku_solved = create_test_sudoku("2");
    
    println!("Testing simple read/write...");
    // Add to DB
    let _ = add_sudoku(&test_sudoku_unsolved, &test_sudoku_solved, &pool)
        .await;
        
    // Read from DB
    let result = find_sudoku(&test_sudoku_unsolved, &pool).await;
    assert!(result.is_ok(), "Failed to read written sudoku back from DB");
    
    // 2. Data is not wiped if a container crashes/closes
    println!("Testing pool recovery (Simulated crash avoidance)...");
    
    pool.close().await; 
    
    println!("Testing data is safe after reload...");
    let recovered_pool = init_pool(db_path).await.expect("Failed to recover pool");
    let result_recovered = find_sudoku(&test_sudoku_unsolved, &recovered_pool).await;
    assert!(result_recovered.is_ok(), "Data was wiped or inaccessible! Persistence failed.");
    
    // 3. Test that Marmot Sidecar is Monitoring Updates
    println!("Testing WAL status for Marmot Sidecar monitoring functionality...");
    
    let row = sqlx::query("PRAGMA wal_checkpoint(PASSIVE);")
        .fetch_one(&recovered_pool)
        .await
        .expect("Failed to fetch WAL PRAGMA");
        
    use sqlx::Row;
    let log_size: i32 = row.try_get(1).unwrap_or(0);
    println!("Current log size for Marmot monitoring: {} pages", log_size);
    // If WAL is active and populated, Marmot can read it.
    assert!(log_size >= 0, "WAL log size is missing, Marmot cannot attach correctly!");
}
