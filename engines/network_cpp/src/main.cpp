#include <iostream>
#include <memory>
#include <string>
#include <thread>
#include <grpcpp/grpcpp.h>
#include <boost/asio.hpp>
#include "network_engine.grpc.pb.h"
#include "scanner.hpp"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::ServerWriter;
using kravigil::network::v1::NetworkScanner;
using kravigil::network::v1::ScanRequest;
using kravigil::network::v1::ScanEvent;
using kravigil::network::v1::CancelRequest;
using kravigil::network::v1::CancelResponse;

class NetworkScannerServiceImpl final : public NetworkScanner::Service {
public:
    Status StartScan(ServerContext* context, const ScanRequest* request, 
                     ServerWriter<ScanEvent>* writer) override {
        
        boost::asio::io_context io_context;
        std::vector<uint32_t> ports(request->ports().begin(), request->ports().end());
        std::mutex writer_mutex;

        auto callback = [&](uint32_t port, bool is_open) {
            if (is_open) {
                ScanEvent event;
                event.set_scan_id(request->scan_id());
                event.set_event_type("PORT_OPEN");
                event.set_target_ip(request->target_ip());
                event.set_port(port);
                event.set_status("OPEN");
                
                std::lock_guard<std::mutex> lock(writer_mutex);
                writer->Write(event);
            }
        };

        auto scanner = std::make_shared<AsyncScanner>(io_context, request->target_ip(), ports, callback);
        scanner->start();

        std::thread io_thread([&io_context]() { io_context.run(); });
        
        while (!context->IsCancelled() && io_thread.joinable()) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }

        scanner->stop();
        io_context.stop();
        if (io_thread.joinable()) io_thread.join();

        return Status::OK;
    }
};

void RunServer() {
    std::string server_address("0.0.0.0:50051");
    NetworkScannerServiceImpl service;

    ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    builder.RegisterService(&service);

    std::unique_ptr<Server> server(builder.BuildAndStart());
    std::cout << "Network Engine listening on " << server_address << std::endl;
    server->Wait();
}

int main(int argc, char** argv) {
    RunServer();
    return 0;
}
