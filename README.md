# Python-Load-Balancer

A basic implementation of a load balancer in Python, designed to distribute HTTP GET requests across multiple backend servers, ensuring efficient load distribution and improved fault tolerance.

## Features

- **Session Persistence**: Ensures that client requests are consistently directed to the same backend server for the duration of the session.
- **Rate Limiting**: Prevents any single client from overwhelming the server by limiting the number of requests from a single IP address.
- **Health Checks**: Periodically checks the health of backend servers to ensure traffic is only directed to operational servers.
- **Multithreading**: Handles incoming requests and server health checks in separate threads to maximize efficiency.

## Getting Started

### Prerequisites

Ensure you have Python 3.6 or later installed on your system. You can check your Python version by running:

```bash
python --version
```
### Installation
Clone the repository to your local machine:
```
git clone https://github.com/Arkay92/Python-Load-Balancer.git
cd your-repository-folder
```
Install the required Python packages:
```
pip install -r requirements.txt
```
## Usage
To start a backend server, run:

```
python main.py --mode backend --port 8000
```

To start the load balancer, run:
```
python main.py --mode balancer --port 5000 --backend_ports 8000 8001 8002
```

Replace 8000 8001 8002 with the ports of your backend servers.

## Configuration
- Backend Servers: Define the ports for your backend Flask applications in the --backend_ports argument when starting the load balancer.
- Rate Limiting: Adjust the rate limiting settings within the RateLimiter class as needed.

## Contributing
Contributions are welcome! Feel free to open an issue or submit a pull request.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
