# Visa Agentic Commerce Testing Platform

A comprehensive testing environment for Visa's agentic commerce APIs, combining the Trusted Agent Protocol (TAP) for merchant authentication and the Model Context Protocol (MCP) for Visa Intelligent Commerce API integration.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Browser                                 │
│  ┌─────────────────────┐         ┌─────────────────────────────┐   │
│  │   Agent Frontend    │         │   Mock Merchant Frontend    │   │
│  │   (localhost:3000)  │         │   (localhost:3001)          │   │
│  └──────────┬──────────┘         └──────────────┬──────────────┘   │
└─────────────┼───────────────────────────────────┼───────────────────┘
              │                                   │
              ▼                                   ▼
┌─────────────────────────┐         ┌─────────────────────────────────┐
│    Agent Service        │         │      Mock Merchant Backend      │
│    (localhost:8000)     │         │      (localhost:8001)           │
│                         │         │                                 │
│  ┌───────────────────┐  │   TAP   │  ┌───────────────────────────┐ │
│  │  TAP Signer       │──┼─────────┼─▶│  TAP Signature Verifier   │ │
│  │  (RFC 9421)       │  │ Signed  │  │                           │ │
│  └───────────────────┘  │ Request │  └───────────────────────────┘ │
│                         │         │                                 │
│  ┌───────────────────┐  │         │  ┌───────────────────────────┐ │
│  │  MCP Client       │  │         │  │  Product Catalog          │ │
│  │  (Visa VIC APIs)  │  │         │  │  Cart Management          │ │
│  └─────────┬─────────┘  │         │  │  Checkout Flow            │ │
│            │            │         │  └───────────────────────────┘ │
└────────────┼────────────┘         └─────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Visa Sandbox APIs                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
│  │  MCP Server     │  │  VIC APIs       │  │  VTS APIs           │ │
│  │  (mcp.visa.com) │  │                 │  │                     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
TAP_VIC/
├── agent-service/           # Shopping Agent Backend (FastAPI)
│   ├── app/
│   │   ├── core/           # Configuration, security
│   │   ├── services/       # Business logic
│   │   ├── routes/         # API endpoints
│   │   ├── models/         # Pydantic models
│   │   ├── static/         # Static files
│   │   └── templates/      # Jinja2 templates
│   ├── requirements.txt
│   └── Dockerfile
│
├── mock-merchant/           # Mock Merchant Backend (FastAPI)
│   ├── app/
│   │   ├── routes/         # API endpoints
│   │   ├── models/         # Data models
│   │   ├── security/       # TAP verification
│   │   ├── database/       # SQLite/products
│   │   ├── static/         # Static files
│   │   └── templates/      # Jinja2 templates
│   ├── requirements.txt
│   └── Dockerfile
│
├── shared/                  # Shared libraries
│   ├── tap/                # TAP signing/verification
│   ├── mcp/                # MCP client wrapper
│   └── models/             # Shared data models
│
├── config/                  # Configuration files
│   ├── .env.example
│   └── keys/               # Cryptographic keys
│
├── scripts/                 # Utility scripts
│   ├── generate_keys.py
│   └── seed_products.py
│
├── docker-compose.yml
└── README.md
```

## Components

### 1. Agent Service (Port 8000)
The AI shopping assistant that:
- Provides a chat interface for users
- Generates TAP signatures for merchant requests
- Connects to Visa MCP server for payment operations
- Orchestrates the shopping flow

### 2. Mock Merchant (Port 8001)
A simulated e-commerce site that:
- Hosts a product catalog
- Verifies TAP signatures on incoming requests
- Provides cart and checkout APIs
- Accepts Visa tokenized credentials

## Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend if separate)
- Visa Developer Account with:
  - VIC API credentials
  - VTS API credentials
  - MLE certificates
  - TAP agent registration

### 1. Clone and Setup

```bash
cd TAP_VIC

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp config/.env.example config/.env
# Edit config/.env with your Visa credentials
```

### 3. Generate Keys (for TAP)

```bash
python scripts/generate_keys.py
```

### 4. Seed Product Catalog

```bash
python scripts/seed_products.py
```

### 5. Run Services

```bash
# Option A: Docker Compose (recommended)
docker-compose up

# Option B: Manual
# Terminal 1 - Agent Service
cd agent-service && uvicorn app.main:app --reload --port 8000

# Terminal 2 - Mock Merchant
cd mock-merchant && uvicorn app.main:app --reload --port 8001
```

### 6. Access

- Agent UI: http://localhost:8000
- Merchant Site: http://localhost:8001
- API Docs: http://localhost:8000/docs

## User Flow

1. **User opens Agent UI** at localhost:8000
2. **User enrolls Visa card** via chat command
   - Agent calls Visa MCP `enroll-card`
   - User completes Passkey verification
3. **User requests product search**
   - Agent signs request with TAP
   - Agent calls Merchant catalog API
   - Merchant verifies TAP signature
   - Results displayed in chat
4. **User selects product and initiates purchase**
   - Agent calls Visa MCP `initiate-purchase-instruction`
   - User authenticates with Passkey
   - Agent calls `retrieve-payment-credentials`
5. **Agent completes checkout**
   - Agent signs checkout request with TAP
   - Merchant verifies and processes order
   - Agent reports outcome via `share-commerce-signals`

## API Reference

### Agent Service APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Agent chat UI |
| `/api/chat` | POST | Send message to agent |
| `/api/enroll-card` | POST | Start card enrollment |
| `/api/auth-callback` | GET | Passkey auth callback |

### Mock Merchant APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Merchant storefront |
| `/api/products` | GET | List products |
| `/api/products/{id}` | GET | Get product details |
| `/api/cart` | POST | Add to cart |
| `/api/checkout` | POST | Process checkout |

## Configuration

### Environment Variables

```bash
# Visa API Credentials
VIC_API_KEY=your_vic_api_key
VIC_API_KEY_SS=your_vic_shared_secret
VTS_API_KEY=your_vts_api_key
VTS_API_KEY_SS=your_vts_shared_secret
MLE_SERVER_CERT=path_to_cert
MLE_PRIVATE_KEY=path_to_key
KEY_ID=your_key_id
EXTERNAL_CLIENT_ID=your_client_id
EXTERNAL_APP_ID=your_app_id

# MCP Configuration
MCP_BASE_URL=https://sandbox.mcp.visa.com

# TAP Configuration
TAP_AGENT_ID=your_agent_id
TAP_PRIVATE_KEY_PATH=config/keys/agent_private.pem
TAP_PUBLIC_KEY_PATH=config/keys/agent_public.pem

# Application
DEBUG=true
```

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Style

```bash
ruff check .
ruff format .
```

## Security Notes

- Never commit real Visa credentials
- Use sandbox APIs for testing only
- TAP private keys should be secured
- Passkey authentication is required for payments

## License

MIT License - For testing and development purposes only.
