FROM rust:1.81-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        clang \
        git \
        libssl-dev \
        make \
        pkg-config \
    && cargo install --locked cargo-audit cargo-deny \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

CMD ["bash"]
