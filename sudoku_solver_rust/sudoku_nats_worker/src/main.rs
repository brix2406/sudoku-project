use sudoku_engine::{solve, Sudoku, prettyprint};


use futures::StreamExt;

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), async_nats::Error> {
    println!("Hello, world!");

    let nats_url = std::env::var("NATS_URL").unwrap_or_else(|_| "nats://localhost:4222".to_string());

    let client = async_nats::connect(nats_url).await?;
    let mut subscription = client.queue_subscribe("sudoku.solve", "sudoku.solve.pool".into()).await?;

    while let Some(message) = subscription.next().await {
        println!("Received: {}B", message.length);

        let mut game: Sudoku = serde_json::from_slice(&message.payload)?;

        let solved = solve(&mut game);

        println!("Solve stats: {}", solved);
        prettyprint(&game.board);

        println!("Responding");

        if let Some(reply_subject) = message.reply {
            let response_payload = serde_json::to_vec(&game)?;
            client.publish(reply_subject, response_payload.into()).await?;
            println!("Sent back solved sudoku to service layer!")
        }
    }
    Ok(())
}
