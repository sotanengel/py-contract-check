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
        python3 \
        python3-pip \
        python3-venv \
    && cargo install --locked cargo-audit cargo-deny \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

ENV PYO3_PYTHON=python3

CMD ["bash"]
