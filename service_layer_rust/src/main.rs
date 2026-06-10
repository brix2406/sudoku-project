use futures::StreamExt;
use serde::Serialize;
use sudoku_engine::{Sudoku, prettyprint, Board};
use service_layer_rust::{solve_sudoku_with_worker, delegate_to_ocr};
use database::{add_sudoku, find_sudoku, init_pool, print_wal_status};

#[derive(Serialize)]
struct ProcessResponse {
    original_board: Board,
    solved_board: Board,
}

#[derive(Serialize)]
struct ErrorResponse {
    error: String,
}

async fn send_error(
    client: &async_nats::Client,
    reply: &Option<async_nats::subject::Subject>,
    msg: &str,
) {
    if let Some(subject) = reply {
        let payload = serde_json::to_vec(&ErrorResponse {
            error: msg.to_string(),
        })
        .unwrap_or_default();
        let _ = client.publish(subject.clone(), payload.into()).await;
    }
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("Starting Rust Service Layer (NATS Orchestrator)...");

    let nats_url =
        std::env::var("NATS_URL").unwrap_or_else(|_| "nats://localhost:4222".to_string());
    let client = async_nats::connect(nats_url).await?;

    let database_url =
        std::env::var("DATABASE_URL").unwrap_or_else(|_| "sqlite:sudoku.db?mode=rwc".to_string());
    let pool = init_pool(&database_url).await?;

    let mut subscription = client
        .queue_subscribe("sudoku.process", "service.pool".into())
        .await?;
    println!("Listening for API requests on 'sudoku.process'...");

    while let Some(message) = subscription.next().await {
        println!(">>> Received image from Python API!");

        let error_reply = message.reply.clone();

        // Read n,k from headers (default 3)
        let n: u16 = message
            .headers
            .as_ref()
            .and_then(|h| h.get("n"))
            .and_then(|v| v.to_string().parse().ok())
            .unwrap_or(3);
        let k: u16 = message
            .headers
            .as_ref()
            .and_then(|h| h.get("k"))
            .and_then(|v| v.to_string().parse().ok())
            .unwrap_or(3);

        // 1. Delegate OCR
        let board = match delegate_to_ocr(&message.payload, n, k, &client).await {
            Ok(b) => b,
            Err(e) => {
                eprintln!("OCR failed: {}", e);
                send_error(&client, &error_reply, &format!("OCR failed: {}", e)).await;
                continue;
            }
        };

        let user_sudoku = Sudoku::new(k, n, board.clone());
        prettyprint(&user_sudoku.board);

        // 2. Check database cache BEFORE solving
        let solved_board = match find_sudoku(&user_sudoku, &pool).await {
            Ok(cached_solved_str) => {
                println!("Found sudoku in DB (Cache hit) — skipping solver.");
                match serde_json::from_str::<Board>(&cached_solved_str) {
                    Ok(board) => board,
                    Err(e) => {
                        eprintln!("Failed to parse cached solution: {}", e);
                        send_error(&client, &error_reply, "DB cache corruption").await;
                        continue;
                    }
                }
            }
            Err(_) => {
                // Cache miss — delegate to solver
                println!("Sudoku not in DB. Delegating to solver...");
                match solve_sudoku_with_worker(&user_sudoku, &client).await {
                    Ok(solved) => {
                        println!("<<< Received solved sudoku from Worker!");
                        if let Err(e) = add_sudoku(&user_sudoku, &solved, &pool).await {
                            eprintln!("DB Add Error: {}", e);
                        }
                        let _ = print_wal_status(&pool).await;
                        solved.board
                    }
                    Err(e) => {
                        eprintln!("Solver failed: {}", e);
                        send_error(
                            &client,
                            &error_reply,
                            &format!("Solver failed: {}", e),
                        )
                        .await;
                        continue;
                    }
                }
            }
        };

        // 3. Reply with both boards
        if let Some(subject) = message.reply {
            let response = ProcessResponse {
                original_board: board,
                solved_board,
            };
            match serde_json::to_vec(&response) {
                Ok(payload) => {
                    if let Err(e) = client.publish(subject, payload.into()).await {
                        eprintln!("Failed to send reply: {}", e);
                    } else {
                        println!("Sent solution back to Python API!");
                    }
                }
                Err(e) => eprintln!("Failed to serialize response: {}", e),
            }
        }
    }

    Ok(())
}
