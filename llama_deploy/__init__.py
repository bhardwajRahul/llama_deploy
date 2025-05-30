# configure logger
import logging

from llama_deploy.client import Client
from llama_deploy.control_plane import ControlPlaneConfig, ControlPlaneServer
from llama_deploy.message_queues import (
    SimpleMessageQueue,
    SimpleMessageQueueConfig,
    SimpleMessageQueueServer,
)
from llama_deploy.services import (
    WorkflowService,
    WorkflowServiceConfig,
)
from llama_deploy.types import QueueMessage

root_logger = logging.getLogger("llama_deploy")

formatter = logging.Formatter("%(levelname)s:%(name)s - %(message)s")
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

root_logger.setLevel(logging.INFO)
root_logger.propagate = True


__all__ = [
    # client
    "Client",
    # services
    "WorkflowService",
    "WorkflowServiceConfig",
    # messages
    "QueueMessage",
    # message queues
    "SimpleMessageQueueServer",
    "SimpleMessageQueueConfig",
    "SimpleMessageQueue",
    # control planes
    "ControlPlaneServer",
    "ControlPlaneConfig",
]
