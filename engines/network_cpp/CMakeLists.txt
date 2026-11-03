cmake_minimum_required(VERSION 3.15)
project(kravigil_network_engine)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Boost 1.74 REQUIRED COMPONENTS system)
find_package(gRPC CONFIG REQUIRED)
find_package(Protobuf REQUIRED)
find_package(Threads REQUIRED)
find_package(GTest REQUIRED)

set(PROTO_FILE ${CMAKE_CURRENT_SOURCE_DIR}/../../shared/protocols/network_engine.proto)
set(PROTO_SRCS ${CMAKE_CURRENT_SOURCE_DIR}/../../shared/protocols/network_engine.pb.cc)
set(GRPC_SRCS ${CMAKE_CURRENT_SOURCE_DIR}/../../shared/protocols/network_engine.grpc.pb.cc)

add_custom_command(
    OUTPUT ${PROTO_SRCS} ${GRPC_SRCS}
    COMMAND ${Protobuf_PROTOC_EXECUTABLE}
    ARGS --grpc_out=${CMAKE_CURRENT_SOURCE_DIR}/../../shared/protocols
         --cpp_out=${CMAKE_CURRENT_SOURCE_DIR}/../../shared/protocols
         -I ${CMAKE_CURRENT_SOURCE_DIR}/../../shared/protocols
         --plugin=protoc-gen-grpc=$<TARGET_FILE:gRPC::grpc_cpp_plugin>
         ${PROTO_FILE}
    DEPENDS ${PROTO_FILE}
)

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
    gRPC::grpc++_reflection
    protobuf::libprotobuf
    Threads::Threads
)

enable_testing()

add_executable(scanner_test
    tests/scanner_test.cpp
    src/scanner.cpp
)

target_link_libraries(scanner_test
    Boost::system
    Threads::Threads
    GTest::gtest_main
    GTest::gmock_main
)

add_test(NAME ScannerTest COMMAND scanner_test)
