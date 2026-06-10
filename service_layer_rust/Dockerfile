FROM rust:latest AS builder

WORKDIR /usr/src/app
# Keep the crate folder layout so path dependencies resolve.
COPY service_layer_rust ./service_layer_rust
COPY sudoku_solver_rust ./sudoku_solver_rust
COPY database_connection ./database_connection

WORKDIR /usr/src/app/service_layer_rust

RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/src/app/service_layer_rust/target/release/service_layer_rust /usr/local/bin/service_layer_rust

WORKDIR /usr/local/bin

CMD ["service_layer_rust"]
