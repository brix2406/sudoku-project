FROM rust:latest AS builder

WORKDIR /usr/src/app
# Copy the entire sudoku_solver_rust directory to include the local sibling dependencies
COPY . .

# Build the specific package
RUN cd sudoku_nats_worker && cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/src/app/sudoku_nats_worker/target/release/sudoku_nats_worker /usr/local/bin/sudoku_nats_worker

CMD ["sudoku_nats_worker"]
