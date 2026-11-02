import grpc
from shared.protocols import network_engine_pb2, network_engine_pb2_grpc

class NetworkEngineClient:
    def __init__(self, host='localhost', port=50051):
        self.channel = grpc.insecure_channel(f'{host}:{port}')
        self.stub = network_engine_pb2_grpc.NetworkScannerStub(self.channel)

    def start_scan(self, scan_id: str, target_ip: str, ports: list, timeout_ms: int = 1500):
        request = network_engine_pb2.ScanRequest(
            scan_id=scan_id,
            authorization_id="auth-dummy",
            target_ip=target_ip,
            ports=ports,
            timeout_ms=timeout_ms
        )
        try:
            for event in self.stub.StartScan(request):
                yield event
        except grpc.RpcError as e:
            raise RuntimeError(f"gRPC Error: {e.code()} - {e.details()}")

    def close(self):
        self.channel.close()
