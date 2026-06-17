use async_nats::{Client, HeaderMap};
use serde::Deserialize;
use sudoku_engine::{Board, Sudoku};

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

#[derive(Deserialize)]
struct OcrResponse {
    board: Board,
}

pub async fn delegate_to_ocr(
    image_bytes: &[u8],
    n: u16,
    k: u16,
    client: &Client,
) -> Result<Board, String> {
    let mut headers = HeaderMap::new();
    headers.insert("n", n.to_string());
    headers.insert("k", k.to_string());

    let payload = image_bytes.to_vec().into();
    // payload is Bytes
    match client.request_with_headers("sudoku.ocr", headers, payload).await {
        Ok(response) => {
            let ocr: OcrResponse = serde_json::from_slice(&response.payload)
                .map_err(|e| format!("Failed to parse OCR response: {}", e))?;
            Ok(ocr.board)
        }
        Err(e) => Err(format!("OCR request failed: {}", e)),
    }
}
