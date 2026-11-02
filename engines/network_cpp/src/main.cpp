#include <grpcpp/grpcpp.h>
#include <boost/asio.hpp>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

#include "network_engine.grpc.pb.h"
#include "scanner.hpp"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::ServerWriter;
using grpc::Status;
using grpc::StatusCode;
using kravigil::network::v1::CancelRequest;
using kravigil::network::v1::CancelResponse;
using kravigil::network::v1::NetworkScanner;
using kravigil::network::v1::ScanEvent;
using kravigil::network::v1::ScanRequest;

namespace {

constexpr const char* ENGINE_VERSION = "1.1.0";
constexpr uint32_t MIN_TIMEOUT_MS = 100;
constexpr uint32_t MAX_TIMEOUT_MS = 30000;
constexpr std::size_t MAX_PORTS_PER_SCAN = 4096;
constexpr std::size_t MAX_WORKER_THREADS = 8;

std::string get_env(const char* name) {
    const char* value = std::getenv(name);
    return value ? std::string(value) : std::string();
}

bool constant_time_equal(const std::string& left, const std::string& right) {
    if (left.size() != right.size()) {
        return false;
    }

    unsigned char difference = 0;
    for (std::size_t i = 0; i < left.size(); ++i) {
        difference |= static_cast<unsigned char>(left[i] ^ right[i]);
    }
    return difference == 0;
}

}  // namespace

class NetworkScannerServiceImpl final : public NetworkScanner::Service {
public:
    explicit NetworkScannerServiceImpl(std::string authorization_token)
        : authorization_token_(std::move(authorization_token)) {}

    Status StartScan(
        ServerContext* context,
        const ScanRequest* request,
        ServerWriter<ScanEvent>* writer
    ) override {
        if (!authorized(request->authorization_id())) {
            return Status(StatusCode::UNAUTHENTICATED, "Invalid authorization");
        }

        if (request->scan_id().empty() || request->target_ip().empty()) {
            return Status(StatusCode::INVALID_ARGUMENT, "scan_id and target_ip are required");
        }

        if (request->ports_size() == 0 ||
            static_cast<std::size_t>(request->ports_size()) > MAX_PORTS_PER_SCAN) {
            return Status(StatusCode::INVALID_ARGUMENT, "Invalid number of ports");
        }

        if (request->timeout_ms() < MIN_TIMEOUT_MS ||
            request->timeout_ms() > MAX_TIMEOUT_MS) {
            return Status(StatusCode::INVALID_ARGUMENT, "timeout_ms is outside allowed limits");
        }

        try {
            boost::asio::ip::make_address(request->target_ip());
        } catch (const std::exception&) {
            return Status(StatusCode::INVALID_ARGUMENT, "target_ip must be a valid IP address");
        }

        std::vector<uint32_t> ports;
        ports.reserve(static_cast<std::size_t>(request->ports_size()));

        for (const uint32_t port : request->ports()) {
            if (port == 0 || port > 65535) {
                return Status(StatusCode::INVALID_ARGUMENT, "Ports must be between 1 and 65535");
            }
            ports.push_back(port);
        }

        boost::asio::io_context io_context;
        auto work_guard = boost::asio::make_work_guard(io_context);
        std::mutex writer_mutex;
        std::atomic<bool> stream_failed{false};
        std::atomic<uint32_t> completed_ports{0};

        auto callback = [&](uint32_t port, bool is_open) {
            ScanEvent event;
            event.set_scan_id(request->scan_id());
            event.set_event_type(is_open ? "PORT_OPEN" : "PORT_CLOSED");
            event.set_target_ip(request->target_ip());
            event.set_port(port);
            event.set_status(is_open ? "OPEN" : "CLOSED_OR_FILTERED");
            event.set_engine_version(ENGINE_VERSION);
            event.set_completed_ports(++completed_ports);
            event.set_total_ports(static_cast<uint32_t>(ports.size()));

            std::lock_guard<std::mutex> lock(writer_mutex);
            if (!stream_failed && !writer->Write(event)) {
                stream_failed = true;
            }
        };

        auto scanner = std::make_shared<AsyncScanner>(
            io_context,
            request->target_ip(),
            ports,
            request->timeout_ms(),
            callback
        );

        {
            std::lock_guard<std::mutex> lock(scans_mutex_);
            if (active_scans_.find(request->scan_id()) != active_scans_.end()) {
                return Status(StatusCode::ALREADY_EXISTS, "scan_id is already active");
            }
            active_scans_[request->scan_id()] = scanner;
        }

        const std::size_t hardware_threads =
            std::max<std::size_t>(2, std::thread::hardware_concurrency());
        const std::size_t worker_count =
            std::min<std::size_t>(hardware_threads, MAX_WORKER_THREADS);

        std::vector<std::thread> workers;
        workers.reserve(worker_count);

        scanner->start();

        for (std::size_t i = 0; i < worker_count; ++i) {
            workers.emplace_back([&io_context]() {
                io_context.run();
            });
        }

        while (
            !scanner->is_finished() &&
            !context->IsCancelled() &&
            !stream_failed.load()
        ) {
            std::this_thread::sleep_for(std::chrono::milliseconds(25));
        }

        const bool was_cancelled = context->IsCancelled();
        const bool was_stream_failed = stream_failed.load();
        scanner->stop();
        work_guard.reset();

        if (was_cancelled || was_stream_failed) {
            io_context.stop();
        }

        for (auto& worker : workers) {
            if (worker.joinable()) {
                worker.join();
            }
        }

        {
            std::lock_guard<std::mutex> lock(scans_mutex_);
            active_scans_.erase(request->scan_id());
        }

        if (!was_cancelled && !was_stream_failed) {
            ScanEvent final_event;
            final_event.set_scan_id(request->scan_id());
            final_event.set_target_ip(request->target_ip());
            final_event.set_engine_version(ENGINE_VERSION);
            final_event.set_completed_ports(completed_ports.load());
            final_event.set_total_ports(static_cast<uint32_t>(ports.size()));
            final_event.set_event_type("COMPLETED");
            final_event.set_status("COMPLETED");

            std::lock_guard<std::mutex> lock(writer_mutex);
            writer->Write(final_event);
        }

        return was_cancelled
            ? Status(StatusCode::CANCELLED, "Scan cancelled")
            : Status::OK;
    }

    Status CancelScan(
        ServerContext*,
        const CancelRequest* request,
        CancelResponse* response
    ) override {
        if (!authorized(request->authorization_id())) {
            return Status(StatusCode::UNAUTHENTICATED, "Invalid authorization");
        }

        std::shared_ptr<AsyncScanner> scanner;

        {
            std::lock_guard<std::mutex> lock(scans_mutex_);
            const auto it = active_scans_.find(request->scan_id());
            if (it == active_scans_.end()) {
                response->set_accepted(false);
                response->set_message("Scan not found");
                return Status::OK;
            }
            scanner = it->second;
        }

        scanner->stop();
        response->set_accepted(true);
        response->set_message("Cancellation requested");
        return Status::OK;
    }

private:
    bool authorized(const std::string& supplied_token) const {
        return !authorization_token_.empty() &&
               constant_time_equal(supplied_token, authorization_token_);
    }

    std::string authorization_token_;
    std::mutex scans_mutex_;
    std::unordered_map<std::string, std::shared_ptr<AsyncScanner>> active_scans_;
};

bool RunServer() {
    const std::string authorization_token = get_env("KRAVIGIL_ENGINE_AUTH_TOKEN");
    const std::string certificate = get_env("KRAVIGIL_TLS_CERT");
    const std::string private_key = get_env("KRAVIGIL_TLS_KEY");

    if (authorization_token.empty() || certificate.empty() || private_key.empty()) {
        std::cerr
            << "KRAVIGIL_ENGINE_AUTH_TOKEN, KRAVIGIL_TLS_CERT and "
            << "KRAVIGIL_TLS_KEY must be configured.\n";
        return false;
    }

    grpc::SslServerCredentialsOptions::PemKeyCertPair key_cert_pair{
        private_key,
        certificate
    };
    grpc::SslServerCredentialsOptions ssl_options;
    ssl_options.pem_key_cert_pairs.push_back(key_cert_pair);

    NetworkScannerServiceImpl service(authorization_token);
    ServerBuilder builder;

    builder.AddListeningPort(
        "0.0.0.0:50051",
        grpc::SslServerCredentials(ssl_options)
    );
    builder.RegisterService(&service);
    builder.SetMaxReceiveMessageSize(1024 * 1024 * 4);
    builder.SetMaxSendMessageSize(1024 * 1024 * 4);

    std::unique_ptr<Server> server(builder.BuildAndStart());
    if (!server) {
        std::cerr << "Failed to start NetworkScanner gRPC server.\n";
        return false;
    }

    std::cout << "KRAVIGIL Network Engine listening on port 50051.\n";
    server->Wait();
    return true;
}

int main() {
    return RunServer() ? 0 : 1;
}
