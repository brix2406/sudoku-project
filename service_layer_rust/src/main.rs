use tokio::time::{sleep, Duration};
use sudoku_engine::{Sudoku, prettyprint};
use service_layer_rust::solve_sudoku_with_worker;
use database::{add_sudoku, find_sudoku, init_pool, print_wal_status};

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), async_nats::Error> {
    println!("Hello, world!");

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

    let nats_url = std::env::var("NATS_URL").unwrap_or_else(|_| "nats://localhost:4222".to_string());

    let client = async_nats::connect(nats_url).await?;

    let database_url = std::env::var("DATABASE_URL").unwrap_or_else(|_| "sqlite://data.db?mode=rwc".to_string());

    let pool = init_pool(&database_url).await?;

    loop {
        let sudoku_solution = match solve_sudoku_with_worker(&sudoku, &client).await
        {
            Ok(solved_sudoku) => {
                println!("Received solved sudoku!");
                prettyprint(&solved_sudoku.board);
                Some(solved_sudoku)
            },
            Err(e) => {
                println!("Failed to get solve: {}", e);
                None
            },
        };

        if let Some(solved_sudoku) = sudoku_solution {
            match find_sudoku(&sudoku, &pool).await{
                Ok(_) => println!("Found sudoko in DB"),
                Err(e) => {eprintln!("{}", e);
                            println!( "Failed to find sudoku in DB\nAdding it to DB now");
                            add_sudoku(&sudoku, &solved_sudoku, &pool).await?;
                            let _ = print_wal_status(&pool).await;
            },
    }
        }
        sleep(Duration::from_secs(5)).await;
    }
}
