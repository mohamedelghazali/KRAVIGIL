import os
import logging
import sys
from agents.communication.agent_client import AgentClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    control_plane_url = os.getenv("CONTROL_PLANE_URL", "https://kravigil.yourdomain.com")
    agent_name = os.getenv("AGENT_NAME", "kravigil-agent-01")
    agent_version = "1.0.0"
    ip_address = os.getenv("AGENT_IP", "127.0.0.1")
    admin_token = os.getenv("KRAVIGIL_ADMIN_TOKEN")

    if not admin_token:
        logger.error("KRAVIGIL_ADMIN_TOKEN is required for agent enrollment.")
        sys.exit(1)

    logger.info(f"Starting KRAVIGIL Agent: {agent_name}")

    client = AgentClient(control_plane_url)

    if not client.enroll(agent_name, agent_version, ip_address, admin_token):
        logger.error("Failed to enroll agent. Exiting.")
        sys.exit(1)

    logger.info("Agent enrolled successfully. Starting heartbeat and task loop...")
    client.run_loop()

if __name__ == "__main__":
    main()
