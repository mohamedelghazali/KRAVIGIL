#include "scanner.hpp"

#include <algorithm>
#include <chrono>
#include <stdexcept>
#include <utility>

AsyncScanner::AsyncScanner(
    boost::asio::io_context& io_context,
    const std::string& target_ip,
    const std::vector<uint32_t>& ports,
    uint32_t timeout_ms,
    ResultCallback callback,
    std::size_t max_in_flight
)
    : io_context_(io_context),
      target_ip_(target_ip),
      ports_(ports),
      timeout_ms_(timeout_ms),
      callback_(std::move(callback)),
      current_port_index_(0),
      max_in_flight_(std::max<std::size_t>(1, max_in_flight)) {}

void AsyncScanner::start() {
    if (!stopped_) {
        schedule_next();
    }
}

void AsyncScanner::stop() {
    if (stopped_.exchange(true)) {
        return;
    }

    auto self = shared_from_this();
    boost::asio::post(io_context_, [self]() {
        std::lock_guard<std::mutex> lock(self->state_mutex_);
        for (const auto& socket : self->active_sockets_) {
            if (socket && socket->is_open()) {
                boost::system::error_code ignored;
                socket->cancel(ignored);
                socket->close(ignored);
            }
        }
    });
}

bool AsyncScanner::is_finished() const {
    std::lock_guard<std::mutex> lock(state_mutex_);
    return current_port_index_ >= ports_.size() && in_flight_.load() == 0;
}

void AsyncScanner::schedule_next() {
    if (stopped_) {
        return;
    }

    std::vector<uint32_t> pending_ports;
    {
        std::lock_guard<std::mutex> lock(state_mutex_);
        while (current_port_index_ < ports_.size() &&
               in_flight_.load() < max_in_flight_) {
            pending_ports.push_back(ports_[current_port_index_++]);
            in_flight_.fetch_add(1);
        }
    }

    for (const uint32_t port : pending_ports) {
        if (stopped_) {
            in_flight_.fetch_sub(1);
            continue;
        }
        try_connect(port);
    }
}

void AsyncScanner::try_connect(uint32_t port) {
    auto self = shared_from_this();
    auto socket = std::make_shared<tcp::socket>(io_context_);
    auto timer = std::make_shared<boost::asio::steady_timer>(io_context_);
    auto completed = std::make_shared<std::atomic<bool>>(false);

    {
        std::lock_guard<std::mutex> lock(state_mutex_);
        active_sockets_.push_back(socket);
    }

    try {
        const auto address = boost::asio::ip::make_address(target_ip_);
        const tcp::endpoint endpoint(address, static_cast<unsigned short>(port));
        timer->expires_after(std::chrono::milliseconds(timeout_ms_));

        timer->async_wait([self, socket, completed, port](
            const boost::system::error_code& ec
        ) {
            if (ec || completed->exchange(true)) {
                return;
            }
            boost::system::error_code ignored;
            socket->cancel(ignored);
            socket->close(ignored);
            self->in_flight_.fetch_sub(1);
            if (!self->stopped_) {
                self->callback_(port, false);
                self->schedule_next();
            }
        });

        socket->async_connect(endpoint, [self, socket, timer, completed, port](
            const boost::system::error_code& ec
        ) {
            if (completed->exchange(true)) {
                return;
            }
            boost::system::error_code ignored;
            timer->cancel(ignored);
            self->in_flight_.fetch_sub(1);
            if (!self->stopped_) {
                self->callback_(port, !ec);
                self->schedule_next();
            }
        });
    } catch (const std::exception&) {
        if (!completed->exchange(true)) {
            boost::system::error_code ignored;
            timer->cancel(ignored);
            socket->close(ignored);
            in_flight_.fetch_sub(1);
            if (!stopped_) {
                callback_(port, false);
                schedule_next();
            }
        }
    }
}
