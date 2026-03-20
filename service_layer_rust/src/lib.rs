use async_nats::Client;
use sudoku_engine::Sudoku;

pub async fn solve_sudoku_with_worker(sudoku_puzzle: &Sudoku, client: &Client) -> Result<Sudoku, String> {
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
