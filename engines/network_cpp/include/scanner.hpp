#pragma once

#include <boost/asio.hpp>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

using boost::asio::ip::tcp;

class AsyncScanner : public std::enable_shared_from_this<AsyncScanner> {
public:
    using ResultCallback = std::function<void(uint32_t, bool)>;

    AsyncScanner(
        boost::asio::io_context& io_context,
        const std::string& target_ip,
        const std::vector<uint32_t>& ports,
        uint32_t timeout_ms,
        ResultCallback callback,
        std::size_t max_in_flight = 256
    );

    void start();
    void stop();
    bool is_finished() const;

private:
    void schedule_next();
    void try_connect(uint32_t port);

    boost::asio::io_context& io_context_;
    std::string target_ip_;
    std::vector<uint32_t> ports_;
    uint32_t timeout_ms_;
    ResultCallback callback_;

    mutable std::mutex state_mutex_;
    std::size_t current_port_index_;
    std::size_t max_in_flight_;
    std::atomic<std::size_t> in_flight_{0};
    std::atomic<bool> stopped_{false};
    std::vector<std::shared_ptr<tcp::socket>> active_sockets_;
};
