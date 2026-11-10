"""
The chat socket as the app opens it, for tests that talk to /chat.
"""


def open_chat(client, token: str):
    """Open /chat with the token in the Sec-WebSocket-Protocol header ("bearer", then the token)."""
    return client.websocket_connect("/chat", subprotocols=["bearer", token])
