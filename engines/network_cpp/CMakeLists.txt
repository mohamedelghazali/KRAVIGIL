cmake_minimum_required(VERSION 3.20)
project(kravigil_network_engine LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
add_executable(kravigil-network
  src/main.cpp
  src/scanner.cpp
  src/resource_budget.cpp
  src/fingerprint.cpp
)
target_include_directories(kravigil-network PRIVATE include)
if(MSVC)
  target_compile_options(kravigil-network PRIVATE /W4 /permissive-)
else()
  target_compile_options(kravigil-network PRIVATE -Wall -Wextra -Wpedantic)
endif()
