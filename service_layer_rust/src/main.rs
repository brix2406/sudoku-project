use futures::StreamExt;
use serde::{Deserialize, Serialize};
use sudoku_engine::{Sudoku, prettyprint, Board};
use service_layer_rust::solve_sudoku_with_worker;
use database::{add_sudoku, find_sudoku, init_pool, print_wal_status};

// Define the incoming payload expected from Python
#[derive(Deserialize)]
struct SolveRequest {
    board: Board,
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("Starting Rust Service Layer (NATS Orchestrator)...");

    let nats_url = std::env::var("NATS_URL").unwrap_or_else(|_| "nats://localhost:4222".to_string());
    let client = async_nats::connect(nats_url).await?;

    // TEMPORARY DB OVERWRITE FOR TESTING
    let database_url = std::env::var("DATABASE_URL").unwrap_or_else(|_| "sqlite:sudoku.db?mode=rwc".to_string());
    let pool = init_pool(&database_url).await?;

    // Subscribe to the API requests instead of looping!
    let mut subscription = client.queue_subscribe("sudoku.process", "service.pool".into()).await?;
    println!("Listening for API requests on 'sudoku.process'...");

    while let Some(message) = subscription.next().await {
        println!(">>> Received OCR Sudoku from Python API!");

        // 1. Parse the incoming request from Python
        let req: SolveRequest = match serde_json::from_slice(&message.payload) {
            Ok(r) => r,
            Err(e) => {
                eprintln!("Failed to parse incoming payload: {}", e);
                continue;
            }
        };

        let user_sudoku = Sudoku::new(3, 3, req.board);
        prettyprint(&user_sudoku.board);

        // 2. Delegate to the heavy-lifting Worker
        let sudoku_solution = match solve_sudoku_with_worker(&user_sudoku, &client).await {
            Ok(solved) => {
                println!("<<< Received solved sudoku from Worker!");
                solved
            },
            Err(e) => {
                eprintln!("Failed to get solve: {}", e);
                continue;
            }
        };

        // 3. Database Caching
        match find_sudoku(&user_sudoku, &pool).await {
            Ok(_) => println!("Found sudoku in DB (Cache hit)"),
            Err(_) => {
                println!("Sudoku not in DB. Adding it now...");
                if let Err(e) = add_sudoku(&user_sudoku, &sudoku_solution, &pool).await {
                    eprintln!("DB Add Error: {}", e);
                }
                let _ = print_wal_status(&pool).await;
            }
        }

        // 4. Reply directly back to the Python API
        if let Some(reply_subject) = message.reply {
            // We serialize the whole struct or just the board based on what Python expects
            match serde_json::to_vec(&sudoku_solution) {
                Ok(response_payload) => {
                    if let Err(e) = client.publish(reply_subject, response_payload.into()).await {
                        eprintln!("Failed to send reply to Python API: {}", e);
                    } else {
                        println!("Sent solution back to Python API!");
                    }
                },
                Err(e) => eprintln!("Failed to serialize solution: {}", e),
            }
        }
    }

    Ok(())
}