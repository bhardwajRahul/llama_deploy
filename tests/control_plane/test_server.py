from typing import Any
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from llama_deploy.control_plane import ControlPlaneConfig, ControlPlaneServer
from llama_deploy.message_queues import SimpleMessageQueueServer
from llama_deploy.types import TaskDefinition


def test_control_plane_init() -> None:
    mq = SimpleMessageQueueServer()
    cp = ControlPlaneServer(mq)  # type: ignore
    assert cp._state_store is not None
    assert cp._config is not None

    assert cp.message_queue == mq
    assert cp.publisher_id.startswith("ControlPlaneServer-")
    assert cp.publish_callback is None

    assert cp.get_topic("msg_type") == "llama_deploy.msg_type"


def test_control_plane_init_state_store() -> None:
    mocked_store = mock.MagicMock()
    with pytest.raises(ValueError):
        ControlPlaneServer(
            SimpleMessageQueueServer(),  # type: ignore
            state_store=mocked_store,
            config=ControlPlaneConfig(state_store_uri="test/uri"),
        )

    cp = ControlPlaneServer(SimpleMessageQueueServer(), state_store=mocked_store)  # type: ignore
    assert cp._state_store == mocked_store

    with mock.patch(
        "llama_deploy.control_plane.server.parse_state_store_uri"
    ) as mocked_parse:
        ControlPlaneServer(
            SimpleMessageQueueServer(),  # type: ignore
            config=ControlPlaneConfig(state_store_uri="test/uri"),
        )
        mocked_parse.assert_called_with("test/uri")


def test_add_task_to_session_not_found(http_client: TestClient, kvstore: Any) -> None:
    kvstore.aget.return_value = None
    td = TaskDefinition(input="")
    response = http_client.post("/sessions/test_session_id/tasks", json=td.model_dump())
    assert response.status_code == 404


def test_add_task_to_session_populate_session_id(
    http_client: TestClient, kvstore: Any
) -> None:
    kvstore.aget.return_value = {}
    td = TaskDefinition(input="", service_id="test-id")
    response = http_client.post("/sessions/test_session_id/tasks", json=td.model_dump())
    assert response.status_code == 200
    # The second call to aput() contains the updated task definition
    assert kvstore.aput.await_args_list[1].args[1]["session_id"] == "test_session_id"


def test_add_task_to_session_session_id_mismatch(
    http_client: TestClient, kvstore: Any
) -> None:
    kvstore.aget.return_value = {}
    td = TaskDefinition(input="", service_id="test-id", session_id="wrong-id")
    response = http_client.post("/sessions/test-session-id/tasks", json=td.model_dump())
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Wrong task definition: task.session_id is wrong-id but should be test-session-id"
    )


@pytest.mark.asyncio
async def test_launch_server(monkeypatch: Any) -> None:
    """Test the launch_server method with proper mocking."""
    # Create mocks
    mock_message_queue = mock.AsyncMock()

    # Create server with custom config
    config = ControlPlaneConfig(
        host="localhost", port=8000, internal_host="127.0.0.1", internal_port=8001
    )
    server = ControlPlaneServer(message_queue=mock_message_queue, config=config)
    # mock with MagicMock, not AsyncMock, otherwise mock will never be awaited
    monkeypatch.setattr(server, "_process_messages", mock.MagicMock())

    # Mock uvicorn and asyncio components
    with (
        mock.patch("llama_deploy.control_plane.server.uvicorn") as mock_uvicorn,
        mock.patch("llama_deploy.control_plane.server.asyncio") as mock_asyncio,
        mock.patch("llama_deploy.control_plane.server.logger") as mock_logger,
    ):
        # Setup mocks
        mock_server_instance = mock.AsyncMock()
        mock_uvicorn.Server.return_value = mock_server_instance
        mock_task = mock.AsyncMock()
        mock_asyncio.create_task.return_value = mock_task
        mock_asyncio.gather.return_value = None

        # Test normal execution path
        try:
            await server.launch_server()
        except Exception:
            # Expected since we're mocking the server.serve() call
            pass

        # Verify logging
        mock_logger.info.assert_called_with(
            "Launching control plane server at 127.0.0.1:8001"
        )

        # Verify task creation
        mock_asyncio.create_task.assert_called_once()

        # Verify uvicorn server setup
        mock_uvicorn.Config.assert_called_once_with(
            server.app, host="127.0.0.1", port=8001
        )
