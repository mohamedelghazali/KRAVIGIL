#include "scanner.hpp"
#include <iostream>
#include <chrono>

AsyncScanner::AsyncScanner(boost::asio::io_context& io_context,
                           const std::string& target_ip,
                           const std::vector<uint32_t>& ports,
                           std::function<void(uint32_t, bool)> callback)
    : io_context_(io_context),
      target_ip_(target_ip),
      ports_(ports),
      current_port_index_(0),
      callback_(callback) {}

void AsyncScanner::start() {
    schedule_next();
}

void AsyncScanner::stop() {
    stopped_ = true;
}

void AsyncScanner::schedule_next() {
    if (stopped_) return;

    while (current_port_index_ < ports_.size() && in_flight_ < max_in_flight_) {
        uint32_t port = ports_[current_port_index_++];
        in_flight_++;
        try_connect(port);
    }
}

void AsyncScanner::try_connect(uint32_t port) {
    auto socket = std::make_shared<tcp::socket>(io_context_);
    auto endpoint = tcp::endpoint(boost::asio::ip::make_address(target_ip_), port);

    auto timer = std::make_shared<boost::asio::steady_timer>(io_context_);
    timer->expires_after(std::chrono::milliseconds(1500));

    auto completed = std::make_shared<std::atomic<bool>>(false);

    timer->async_wait([socket, completed, this, port](const boost::system::error_code& ec) {
        if (!ec && !(*completed)) {
            *completed = true;
            boost::system::error_code ignored_ec;
            socket->close(ignored_ec);
            in_flight_--;
            callback_(port, false);
            schedule_next();
        }
    });

    socket->async_connect(endpoint, [this, socket, timer, completed, port](const boost::system::error_code& ec) {
        if (*completed) return;
        *completed = true;
        timer->cancel();

        in_flight_--;
        callback_(port, !ec);
        schedule_next();
    });
}
