use async_nats::Client;
use sudoku_engine::{Board, Sudoku};
use tokio::time::{timeout, Duration};

fn rows_to_board(rows: Vec<Vec<&str>>) -> Board {
    rows.into_iter()
        .map(|row| row.into_iter().map(|s| s.to_string()).collect())
        .collect()
}

fn test_puzzle() -> Sudoku {
    Sudoku::new(
        3,
        3,
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
        ]),
    )
}

fn expected_solution() -> Board {
    rows_to_board(vec![
        vec!["5", "3", "4", "6", "7", "8", "9", "1", "2"],
        vec!["6", "7", "2", "1", "9", "5", "3", "4", "8"],
        vec!["1", "9", "8", "3", "4", "2", "5", "6", "7"],
        vec!["8", "5", "9", "7", "6", "1", "4", "2", "3"],
        vec!["4", "2", "6", "8", "5", "3", "7", "9", "1"],
        vec!["7", "1", "3", "9", "2", "4", "8", "5", "6"],
        vec!["9", "6", "1", "5", "3", "7", "2", "8", "4"],
        vec!["2", "8", "7", "4", "1", "9", "6", "3", "5"],
        vec!["3", "4", "5", "2", "8", "6", "1", "7", "9"],
    ])
}

async fn request_solution(client: &Client, puzzle: &Sudoku) -> Result<Sudoku, String> {
    let payload = serde_json::to_vec(puzzle).map_err(|e| e.to_string())?;
    let response = timeout(
        Duration::from_secs(10),
        client.request("sudoku.solve", payload.into()),
    )
    .await
    .map_err(|_| "Timed out waiting for worker reply".to_string())
    .and_then(|result| result.map_err(|e| e.to_string()))?;

    serde_json::from_slice(&response.payload).map_err(|e| e.to_string())
}

#[tokio::test]
async fn worker_solves_sudoku_via_nats_request_reply() {
    let nats_url = std::env::var("NATS_URL").unwrap_or_else(|_| "nats://localhost:4222".to_string());
    let client = async_nats::connect(nats_url)
        .await
        .expect("Failed to connect to NATS");

    let solved = request_solution(&client, &test_puzzle())
        .await
        .expect("Worker did not return a valid solved Sudoku");

    assert_eq!(solved.board, expected_solution());
}
