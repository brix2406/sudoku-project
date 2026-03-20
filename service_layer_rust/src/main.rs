use async_nats::Client;
use tokio::time::{sleep, Duration};
use sudoku_engine::{Sudoku, prettyprint};

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

    loop {
        match solve_sudoku_with_worker(&sudoku, &client).await
        {
            Ok(solved_sudoku) => {
                println!("Received solved sudoku!");
                prettyprint(&solved_sudoku.board);
            }
            Err(e) => println!("Failed to get solve: {}", e)
        }
        sleep(Duration::from_secs(5)).await;
    }
}

async fn solve_sudoku_with_worker(sudoku_puzzle: &Sudoku, client: &Client) -> Result<Sudoku, String> {
    let incoming = serde_json::to_vec(&sudoku_puzzle);
    let payload: Vec<u8>;
    match incoming {
        Ok(success_payload) => payload = success_payload,
        Err(e) => {
            eprintln!("failed to encode sudoku_puzzle: {}", e);
            return Err(e.to_string());
        }
    }
    match client.request("sudoku.solve", payload.into()).await {
        Ok(response) => {
            println!("Received solution!");
            match serde_json::from_slice(&response.payload)
            {
                Ok(sudoku) => return Ok(sudoku),
                Err(e) => return Err(e.to_string())
            }
        }
        Err(e) => 
        {
            eprintln!("Request failed or timed out: {}", e.to_string());
            return Err(e.to_string());
        }
    }
}
