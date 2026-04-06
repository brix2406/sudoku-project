FROM rust:latest AS builder

WORKDIR /usr/src/app
COPY database_connection ./database_connection
COPY sudoku_solver_rust ./sudoku_solver_rust

WORKDIR /usr/src/app/database_connection

RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/src/app/database_connection/target/release/database /usr/local/bin/database
COPY database_connection/data.db /usr/local/bin/

WORKDIR /usr/local/bin

CMD ["database"]
