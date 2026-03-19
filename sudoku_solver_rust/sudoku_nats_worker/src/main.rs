use async_nats::jetstream::message;
use sudoku_engine::{solve, Sudoku, prettyprint};


use futures::StreamExt;

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), async_nats::Error> {
    println!("Hello, world!");

    let nats_url = std::env::var("NATS_URL").unwrap_or_else(|_| "nats://localhost:4222".to_string());

    let client = async_nats::connect(nats_url).await?;
    let mut subscription = client.subscribe("sudoku.solve").await?;

    while let Some(message) = subscription.next().await {
        println!("Received: {}B", message.length);

        let mut game: Sudoku = serde_json::from_slice(&message.payload)?;

        let solved = solve(&mut game);

        println!("Solve stats: {}", game.is_solved);
        prettyprint(&game.board);
    }
    Ok(())
}
