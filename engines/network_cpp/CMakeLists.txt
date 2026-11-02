cmake_minimum_required(VERSION 3.15)
project(kravigil_network_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Boost 1.74 REQUIRED COMPONENTS system)
find_package(gRPC CONFIG REQUIRED)
find_package(Protobuf CONFIG REQUIRED)
find_package(Threads REQUIRED)

set(PROTO_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../shared/protocols)
set(PROTO_FILE ${PROTO_DIR}/network_engine.proto)
set(GENERATED_DIR ${CMAKE_CURRENT_BINARY_DIR}/generated)

file(MAKE_DIRECTORY ${GENERATED_DIR})

set(PROTO_SRCS
    ${GENERATED_DIR}/network_engine.pb.cc
    ${GENERATED_DIR}/network_engine.grpc.pb.cc
)
set(PROTO_HDRS
    ${GENERATED_DIR}/network_engine.pb.h
    ${GENERATED_DIR}/network_engine.grpc.pb.h
)

add_custom_command(
    OUTPUT ${PROTO_SRCS} ${PROTO_HDRS}
    COMMAND protobuf::protoc
    ARGS
        --proto_path=${PROTO_DIR}
        --cpp_out=${GENERATED_DIR}
        --grpc_out=${GENERATED_DIR}
        --plugin=protoc-gen-grpc=$<TARGET_FILE:gRPC::grpc_cpp_plugin>
        ${PROTO_FILE}
    DEPENDS ${PROTO_FILE} protobuf::protoc gRPC::grpc_cpp_plugin
    VERBATIM
)

add_executable(network_engine
    src/main.cpp
    src/scanner.cpp
    ${PROTO_SRCS}
    ${PROTO_HDRS}
)

target_include_directories(network_engine PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${GENERATED_DIR}
)

target_link_libraries(network_engine PRIVATE
    Boost::system
    gRPC::grpc++
    protobuf::libprotobuf
    Threads::Threads
)

if(TARGET gRPC::grpc++_reflection)
    target_link_libraries(network_engine PRIVATE gRPC::grpc++_reflection)
endif()
