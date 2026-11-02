#include <gtest/gtest.h>
#include <gmock/gmock.h>
#include <boost/asio.hpp>
#include "scanner.hpp"

using ::testing::_;
using ::testing::Invoke;

class AsyncScannerTest : public ::testing::Test {
protected:
    boost::asio::io_context io_context;
};

TEST_F(AsyncScannerTest, HandlesInvalidPort) {
    std::vector<uint32_t> ports = {0, 70000};
    bool callback_called = false;

    auto scanner = std::make_shared<AsyncScanner>(
        io_context,
        "127.0.0.1",
        ports,
        1000,
        [&](uint32_t port, bool is_open) {
            callback_called = true;
            ASSERT_FALSE(is_open);
        }
    );

    scanner->start();
    io_context.run();
    // Should complete instantly without crashing
    EXPECT_TRUE(true);
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
