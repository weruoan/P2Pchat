import streamlit as st
import asyncio
import socket
import threading
import json
import time

# Initialize session state for chat history and peer info
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'peers' not in st.session_state:
    st.session_state.peers = []
if 'username' not in st.session_state:
    st.session_state.username = None

# P2P Server to listen for incoming messages
async def p2p_server(host='127.0.0.1', port=12345):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    server.setblocking(False)
    loop = asyncio.get_event_loop()

    st.write(f"Server running on {host}:{port}")

    while True:
        client, addr = await loop.sock_accept(server)
        loop.create_task(handle_client(client, addr))

# Handle incoming client messages
async def handle_client(client, addr):
    loop = asyncio.get_event_loop()
    while True:
        try:
            data = await loop.sock_recv(client, 1024)
            if not data:
                break
            message = json.loads(data.decode())
            st.session_state.messages.append(f"{message['username']} ({addr[0]}:{addr[1]}): {message['text']}")
            st.rerun()  # Refresh Streamlit to update chat
        except:
            break
    client.close()

# Send message to a peer
async def send_message(peer_host, peer_port, username, message):
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(2)
        client.connect((peer_host, peer_port))
        data = json.dumps({'username': username, 'text': message})
        client.send(data.encode())
        client.close()
        st.session_state.messages.append(f"You ({username}): {message}")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to send message to {peer_host}:{peer_port}: {e}")

# Start the P2P server in a separate thread
def start_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(p2p_server())

# Streamlit UI
st.title("P2P Chat Application")

# Username input
if not st.session_state.username:
    username = st.text_input("Enter your username:")
    if username:
        st.session_state.username = username
        st.rerun()

if st.session_state.username:
    # Start P2P server if not already running
    if not hasattr(st, 'server_started'):
        threading.Thread(target=start_server, daemon=True).start()
        st.server_started = True

    # Peer connection input
    st.subheader("Connect to a Peer")
    peer_host = st.text_input("Peer Host (e.g., 127.0.0.1):")
    peer_port = st.number_input("Peer Port (e.g., 12345):", min_value=1024, max_value=65535, step=1)
    if st.button("Add Peer"):
        if peer_host and peer_port:
            st.session_state.peers.append((peer_host, peer_port))
            st.success(f"Added peer {peer_host}:{peer_port}")

    # Display connected peers
    if st.session_state.peers:
        st.subheader("Connected Peers")
        for peer in st.session_state.peers:
            st.write(f"{peer[0]}:{peer[1]}")

    # Chat input
    st.subheader("Chat")
    message = st.text_input("Your message:")
    if st.button("Send"):
        if message:
            for peer_host, peer_port in st.session_state.peers:
                asyncio.run(send_message(peer_host, peer_port, st.session_state.username, message))

    # Display chat history
    st.subheader("Messages")
    for msg in st.session_state.messages:
        st.write(msg)