# Stage 1: The Builder
FROM golang:alpine AS builder

# Install git and C-compilers required for SQLite bindings
RUN apk update && apk add --no-cache git build-base

WORKDIR /app
# Clone the repository
RUN git clone https://github.com/maxpert/marmot.git .

# Pin to a known-good release tag to avoid broken main builds
RUN git checkout v2.9.13-beta

# Compile with CGO enabled for SQLite
RUN CGO_ENABLED=1 GOOS=linux go build -o /marmot .

# Stage 2: The Final, Tiny Image
FROM alpine:latest

# Copy the compiled binary from the builder
COPY --from=builder /marmot /usr/local/bin/marmot
RUN chmod +x /usr/local/bin/marmot

ENTRYPOINT ["marmot"]