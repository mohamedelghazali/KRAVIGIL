#pragma once
#include <boost/asio.hpp>
#include <memory>
#include <vector>
#include <atomic>
#include <functional>

using boost::asio::ip::tcp;

class AsyncScanner : public std::enable_shared_from_this<AsyncScanner> {
public:
    AsyncScanner(boost::asio::io_context& io_context, 
                 const std::string& target_ip,
                 const std::vector<uint32_t>& ports,
                 std::function<void(uint32_t, bool)> callback);

    void start();
    void stop();

private:
    void schedule_next();
    void try_connect(uint32_t port);

    boost::asio::io_context& io_context_;
    std::string target_ip_;
    std::vector<uint32_t> ports_;
    std::size_t current_port_index_;
    std::function<void(uint32_t, bool)> callback_;
    std::atomic<bool> stopped_{false};
    std::atomic<std::size_t> in_flight_{0};
    const std::size_t max_in_flight_ = 512;
};
