FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    libboost-all-dev \
    libprotobuf-dev \
    protobuf-compiler \
    libgrpc++-dev \
    libgrpc-dev \
    protobuf-compiler-grpc \
    pkg-config \
    python3 \
    python3-pip \
    libgtest-dev \
    libgmock-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install grpcio-tools

WORKDIR /app

COPY shared/protocols/network_engine.proto /app/shared/protocols/
COPY engines/network_cpp/ /app/engines/network_cpp/

WORKDIR /app/shared/protocols
RUN python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. network_engine.proto
RUN protoc -I . --cpp_out=. --grpc_out=. --plugin=protoc-gen-grpc=`which grpc_cpp_plugin` network_engine.proto

WORKDIR /app/engines/network_cpp
# البحث الديناميكي عن مسار gRPCConfig.cmake
RUN GRPC_CMAKE_DIR=$(find /usr -name "gRPCConfig.cmake" -o -name "grpc-config.cmake" | head -n 1 | xargs dirname) && \
    echo "Found gRPC CMake config in: $GRPC_CMAKE_DIR" && \
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
    -DgRPC_DIR=$GRPC_CMAKE_DIR \
    -DCMAKE_PREFIX_PATH=$GRPC_CMAKE_DIR \
    && cmake --build build --parallel

FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    libboost-system1.74.0 \
    libprotobuf23 \
    libgrpc++1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/engines/network_cpp/build/network_engine /app/network_engine

EXPOSE 50051

CMD ["./network_engine"]
