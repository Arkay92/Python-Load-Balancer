import argparse
import logging
import threading
import time
import queue
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import requests
from flask import Flask, request
import hashlib
import functools

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
task_queue = queue.Queue()  # Global task queue

def worker():
    while True:
        client_id, path = task_queue.get()
        try:
            server_url = SecureLoadBalancerHandler.balancer.get_server_url(client_id)
            if server_url:
                # Forward the request to the appropriate backend server
                response = requests.get(server_url + path)
                logging.info(f"Request forwarded to {server_url + path}")
            else:
                logging.error("No healthy backend servers available.")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error forwarding request: {e}")
        finally:
            task_queue.task_done()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

class RateLimiter:
    def __init__(self, max_requests, window_size):
        self.max_requests = max_requests
        self.window_size = window_size
        self.access_records = {}

    def is_allowed(self, client_id):
        current_time = time.time()
        window_start = current_time - self.window_size

        if client_id not in self.access_records:
            self.access_records[client_id] = []

        access_times = self.access_records[client_id]
        access_times = [t for t in access_times if t >= window_start]

        allowed = len(access_times) < self.max_requests
        if allowed:
            access_times.append(current_time)

        self.access_records[client_id] = access_times
        return allowed

def rate_limit(max_requests, window_size):
    limiter = RateLimiter(max_requests, window_size)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            client_id = request.remote_addr
            if not limiter.is_allowed(client_id):
                return "Too Many Requests", 429
            return func(*args, **kwargs)
        return wrapper
    return decorator

class BackendServer:
    def __init__(self, url):
        self.url = url
        self.is_healthy = True

    def check_health(self):
        try:
            response = requests.get(self.url)
            self.is_healthy = response.status_code == 200
        except requests.exceptions.RequestException:
            self.is_healthy = False

def health_check_loop(servers, interval=30):
    """Periodically check the health of all servers."""
    while True:
        for server in servers:
            server.check_health()
        time.sleep(interval)

class SessionPersistenceBalancer:
    def __init__(self, servers):
        self.servers = [BackendServer(url) for url in servers]
        self.lock = threading.Lock()

    def get_server_url(self, client_id):
        with self.lock:
            healthy_servers = [server for server in self.servers if server.is_healthy]
            if not healthy_servers:
                return None
            hash_val = int(hashlib.md5(client_id.encode()).hexdigest(), 16)
            return healthy_servers[hash_val % len(healthy_servers)].url


class SecureLoadBalancerHandler(SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    balancer = None

    def do_GET(self):
        client_id = self.client_address[0]
        server_url = self.balancer.get_server_url(client_id)
        task_queue.put((self.client_address[0], self.path))
        if server_url:
            try:
                logging.info(f"SSL termination simulated for client {client_id}")
                response = requests.get(server_url)
                self.send_response(response.status_code)
                self.end_headers()
                self.wfile.write(response.content)
            except requests.exceptions.RequestException as e:
                logging.error(f"Error forwarding request: {e}")
                self.send_error(502, "Bad Gateway")
        else:
            logging.error("No healthy backend servers available.")
            self.send_error(503, "Service Unavailable")

@app.route('/')
@rate_limit(max_requests=5, window_size=60)  # Simple rate limiting: max 5 requests per minute per IP
def home():
    return "Response from secure server"

def run_flask_app(port):
    app.run(port=port, ssl_context='adhoc')  # Use 'adhoc' for on-the-fly SSL generation (not for production)

def run_load_balancer(port, server_urls):
    balancer = SessionPersistenceBalancer(server_urls)
    SecureLoadBalancerHandler.balancer = balancer

    # Start health check loop
    health_check_thread = threading.Thread(target=health_check_loop, args=(balancer.servers,))
    health_check_thread.daemon = True
    health_check_thread.start()

    # Start worker threads
    for _ in range(threading.cpu_count()):  # Adjust the number of workers as needed
        worker_thread = threading.Thread(target=worker)
        worker_thread.daemon = True
        worker_thread.start()

    server_address = ('', port)
    httpd = ThreadedHTTPServer(server_address, SecureLoadBalancerHandler)
    logging.info(f"SSL Load Balancer running on port {port} with multithreading...")
    httpd.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run a simple server or load balancer.')
       parser.add_argument('--mode', choices=['backend', 'balancer'], required=True, help='Run as a backend server or a load balancer.')
    parser.add_argument('--port', type=int, required=True, help='Port to run the server on.')
    parser.add_argument('--backend_ports', nargs='*', type=int, help='Ports for the backend servers (used in balancer mode).')

    args = parser.parse_args()

    if args.mode == 'backend':
        logging.info(f"Running backend server on port {args.port}...")
        run_flask_app(args.port)
    elif args.mode == 'balancer':
        if not args.backend_ports:
            logging.error("Error: --backend_ports is required when mode is 'balancer'")
            exit(1)
        server_urls = [f"http://localhost:{port}" for port in args.backend_ports]
        run_load_balancer(args.port, server_urls)
