use futures::StreamExt;
use serde::{Deserialize, Serialize};

use sudoku_engine::{Sudoku, prettyprint, validate_givens, Board};
use service_layer_rust::{solve_sudoku_with_worker, delegate_to_ocr};
use database::{add_sudoku, find_sudoku, init_pool, print_wal_status};
use sha2::{Sha256, Digest};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Serialize)]
struct ProcessResponse {
    original_board: Board,
    solved_board: Board,
}

#[derive(Deserialize)]
struct ManualSolveRequest {
    k: u16,
    n: u16,
    board: Board,
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

async fn send_success(
    client: &async_nats::Client,
    reply: &Option<async_nats::subject::Subject>,
    original_board: &Board,
    solved_board: &Board,
) {
    if let Some(subject) = reply {
        let response = ProcessResponse {
            original_board: original_board.clone(),
            solved_board: solved_board.clone(),
        };
        let payload = serde_json::to_vec(&response).unwrap_or_default();
        let _ = client.publish(subject.clone(), payload.into()).await;
    }
}


fn save_contradiction_debug(payload: &[u8], board: &Board, _k: u16, _n: u16) {
    let mut hasher = Sha256::new();
    hasher.update(payload);
    let hash = format!("{:x}", hasher.finalize());
    let hash8 = &hash[..8];

    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    let dir = "/debug/contradictions";
    if std::fs::create_dir_all(dir).is_err() {
        return;
    }

    let prefix = format!("{dir}/{ts}_{hash8}");

    // 1. Original image (raw bytes from upload)
    let _ = std::fs::write(format!("{prefix}.png"), payload);

    // 2. Board as JSON
    if let Ok(json) = serde_json::to_string_pretty(board) {
        let _ = std::fs::write(format!("{prefix}.json"), json);
    }

    // 3. Copy OCR overlay from the shared /debug volume
    let overlay_src = format!("/debug/ocr_overlays/{ts}_{hash8}.png");
    let overlay_dst = format!("{prefix}_overlay.png");
    let _ = std::fs::copy(&overlay_src, &overlay_dst);
}


async fn handle_manual_solve(
    mut subscription: async_nats::Subscriber,
    client: async_nats::Client,
    pool: sqlx::SqlitePool,
) {
    while let Some(message) = subscription.next().await {
        println!(">>> Received manual solve request!");
        let error_reply = message.reply.clone();

        let req: ManualSolveRequest = match serde_json::from_slice(&message.payload) {
            Ok(r) => r,
            Err(e) => {
                eprintln!("Failed to parse manual solve request: {}", e);
                send_error(&client, &error_reply, &format!("Invalid request: {}", e)).await;
                continue;
            }
        };

        let board = req.board;
        prettyprint(&board);

        let user_sudoku = Sudoku::new(req.k, req.n, board.clone());

        if !validate_givens(&user_sudoku) {
            println!("Puzzle rejected: conflicting given values.");
            send_error(
                &client,
                &error_reply,
                "This puzzle is impossible: it contains conflicting values in a row, column, or block.",
            )
            .await;
            continue;
        }

        // Check DB cache first
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
                println!("Sudoku not in DB. Delegating to solver...");
                match solve_sudoku_with_worker(&user_sudoku, &client).await {
                    Ok(solved) => {
                        if !solved.is_solved {
                            println!("Worker reported puzzle as unsolvable.");
                            send_error(
                                &client,
                                &error_reply,
                                "This puzzle is impossible: no solution exists.",
                            )
                            .await;
                            continue;
                        }
                        println!("<<< Received solved sudoku from Worker!");
                        if let Err(e) = add_sudoku(&user_sudoku, &solved, &pool).await {
                            eprintln!("DB Add Error: {}", e);
                        }
                        let _ = print_wal_status(&pool).await;
                        solved.board
                    }
                    Err(e) => {
                        eprintln!("Solver failed: {}", e);
                        send_error(&client, &error_reply, &format!("Solver failed: {}", e)).await;
                        continue;
                    }
                }
            }
        };

        // Reply with both boards
        send_success(&client, &message.reply, &board, &solved_board).await;
    }
}

async fn handle_ping(
    mut subscription: async_nats::Subscriber,
    client: async_nats::Client,
) {
    while let Some(message) = subscription.next().await {
        if let Some(reply) = message.reply {
            if let Err(e) = client.publish(reply, b"ok".as_slice().into()).await {
                eprintln!("Failed to send ping reply: {}", e);
            }
        }
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
    let manual_subscription = client
        .queue_subscribe("sudoku.manual_solve", "service.pool".into())
        .await?;
    println!("Listening for manual solve requests on 'sudoku.manual_solve'...");

    let manual_client = client.clone();
    let manual_pool = pool.clone();
    let _manual_handle = tokio::spawn(async move {
        handle_manual_solve(manual_subscription, manual_client, manual_pool).await;
    });

    let ping_subscription = client
        .queue_subscribe("sudoku.ping", "service.pool".into())
        .await?;
    let ping_client = client.clone();
    let _ping_handle = tokio::spawn(async move {
        handle_ping(ping_subscription, ping_client).await;
    });

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

        if !validate_givens(&user_sudoku) {
            println!("Puzzle rejected: conflicting given values.");
            save_contradiction_debug(&message.payload, &board, k, n);
            send_error(
                &client,
                &error_reply,
                "This puzzle is impossible: it contains conflicting values in a row, column, or block.",
            )
            .await;
            continue;
        }

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
                        if !solved.is_solved {
                            println!("Worker reported puzzle as unsolvable.");
                            save_contradiction_debug(&message.payload, &board, k, n);
                            send_error(
                                &client,
                                &error_reply,
                                "This puzzle is impossible: no solution exists.",
                            )
                            .await;
                            continue;
                        }
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
