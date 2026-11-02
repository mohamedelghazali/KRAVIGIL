import pytest
import grpc
from concurrent import futures
import time
from engines.network_cpp.grpc_client import NetworkEngineClient

# This test requires the C++ engine to be compiled and running on localhost:50051
# It serves as an integration test, not a unit test.

@pytest.mark.integration
def test_grpc_network_engine_connection():
    client = NetworkEngineClient(host='localhost', port=50051)

    try:
        # Test invalid target to ensure clean error handling
        with pytest.raises(RuntimeError):
            list(client.start_scan("test-scan-1", "invalid-ip", [80]))

        # Test valid scan (scanning localhost port 22, could be open or closed)
        results = list(client.start_scan("test-scan-2", "127.0.0.1", [22]))
        assert isinstance(results, list)

    finally:
        client.close()
