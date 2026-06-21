use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use futures::StreamExt;
use sudoku_engine::{prettyprint, solve, Sudoku};

const SOLVE_TIMEOUT_SECS: u64 = 9;

#[tokio::main]
async fn main() -> Result<(), async_nats::Error> {
    println!("Hello, world!");

    let nats_url = std::env::var("NATS_URL").unwrap_or_else(|_| "nats://localhost:4222".to_string());

    let client = async_nats::connect(nats_url).await?;
    let mut subscription = client
        .queue_subscribe("sudoku.solve", "sudoku.solve.pool".into())
        .await?;

    while let Some(message) = subscription.next().await {
        let client = client.clone();
        tokio::spawn(async move {
            println!("Received: {}B", message.length);

            let mut game: Sudoku = match serde_json::from_slice(&message.payload) {
                Ok(g) => g,
                Err(e) => {
                    eprintln!("Failed to deserialize Sudoku: {e}");
                    return;
                }
            };

            let cancel = Arc::new(AtomicBool::new(false));
            let cancel_for_solver = Arc::clone(&cancel);

            let handle = tokio::task::spawn_blocking(move || {
                let solved = solve(&mut game, &cancel_for_solver);
                (solved, game)
            });

            match tokio::time::timeout(Duration::from_secs(SOLVE_TIMEOUT_SECS), handle).await {
                Ok(Ok((solved, game))) => {
                    println!("Solve stats: {solved}");
                    prettyprint(&game.board);
                    println!("Responding");
                    if let Some(reply_subject) = message.reply {
                        match serde_json::to_vec(&game) {
                            Ok(payload) => {
                                if let Err(e) = client.publish(reply_subject, payload.into()).await {
                                    eprintln!("Failed to send reply: {e}");
                                } else {
                                    println!("Sent back solved sudoku to service layer!");
                                }
                            }
                            Err(e) => eprintln!("Failed to serialize solved sudoku: {e}"),
                        }
                    }
                }
                Ok(Err(e)) => eprintln!("Solver thread panicked: {e}"),
                Err(_elapsed) => {
                    cancel.store(true, Ordering::Relaxed);
                    eprintln!(
                        "Solve exceeded {SOLVE_TIMEOUT_SECS}s deadline; cancelled. Ready for next request."
                    );
                }
            }
        });
    }
    Ok(())
}
