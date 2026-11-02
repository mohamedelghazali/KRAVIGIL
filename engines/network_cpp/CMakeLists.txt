cmake_minimum_required(VERSION 3.15)
project(kravigil_network_engine)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Boost REQUIRED COMPONENTS system)
find_package(gRPC REQUIRED)
find_package(Protobuf REQUIRED)

set(PROTO_SRCS ${CMAKE_CURRENT_SOURCE_DIR}/../../shared/protocols/network_engine.pb.cc)
set(GRPC_SRCS ${CMAKE_CURRENT_SOURCE_DIR}/../../shared/protocols/network_engine.grpc.pb.cc)

include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/../../shared/protocols)

add_executable(network_engine
    src/main.cpp
    src/scanner.cpp
    ${PROTO_SRCS}
    ${GRPC_SRCS}
)

target_link_libraries(network_engine
    Boost::system
    gRPC::grpc++
    protobuf::libprotobuf
    pthread
)
