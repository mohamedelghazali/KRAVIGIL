#include <gtest/gtest.h>
#include <gmock/gmock.h>
#include <stdexcept>
#include <boost/asio.hpp>
#include "scanner.hpp"

using ::testing::_;
using ::testing::Invoke;

class AsyncScannerTest : public ::testing::Test {
protected:
    boost::asio::io_context io_context;
};

TEST_F(AsyncScannerTest, RejectsInvalidPorts) {
    const std::vector<uint32_t> zero_port = {0};
    const std::vector<uint32_t> oversized_port = {70000};

    EXPECT_THROW(
        std::make_shared<AsyncScanner>(
            io_context, "127.0.0.1", zero_port, 1000,
            [](uint32_t, bool) {}
        ),
        std::invalid_argument
    );
    EXPECT_THROW(
        std::make_shared<AsyncScanner>(
            io_context, "127.0.0.1", oversized_port, 1000,
            [](uint32_t, bool) {}
        ),
        std::invalid_argument
    );
}

TEST_F(AsyncScannerTest, ScansLocalhostClosedPort) {
    std::vector<uint32_t> ports = {9999}; // Assuming port 9999 is closed on localhost
    int open_count = 0;

    auto scanner = std::make_shared<AsyncScanner>(
        io_context,
        "127.0.0.1",
        ports,
        500,
        [&](uint32_t port, bool is_open) {
            if (is_open) open_count++;
        }
    );

    scanner->start();
    io_context.run();

    EXPECT_EQ(open_count, 0);
}
