# Create Backend Folder Structure
mkdir backend_fastapi && cd backend_fastapi
mkdir -p app/ app/core app/api/ app/api/v1 app/models app/schemas app/services app/utils app/agents
cd app
touch main.py
cd core
touch logging.py
touch config.py
touch database.py
touch startup.py
cd ../api/v1
touch api.py
cd models
touch user.py
touch auth.py

# Create python environment
cd ../../../..
uv init
uv add "fastapi[standard]" "pyjwt[crypto]" "pwdlib[argon2]" "pydantic-settings" "slowapi" "sqlmodel" "alembic" "psycopg"

- fastapi[standard] : server
- pyjwt : to generate and verify the JWT tokens 
- pwdlib[argon2] : handle password hashe
- pydantic-settings: for settings with type validation
- slowapi : for rate limiting
- sqlmodel : for Data models
- alembic : database migration
- psycopg : PostgreSQL database adapter for Python
- prometheus-fastapi-instrumentator : 
- httpx : general HTTP exceptions etc
- authlib : for google oauth2
- itsdangerous : for Starlette’s SessionMiddleware uses it to sign session cookies.



# Secret Key Generation (JWT) for SECRET_KEY
- Command Line: "openssl rand -hex 32"
- Python: "cd backend_fastapi && uv run python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# Encryption Key Generation (Fernet encryption key for database credentials) for ENCRYPTION_KEY
cd backend_fastapi && uv run python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```


# Create Frontend Folder Structure
# Fresh setup
mkdir frontend_nextjs && cd frontend_nextjs


### Frontend Setup
```bash
# Create Next.js app with TypeScript and Tailwind
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"

# for self signing cert
export NODE_TLS_REJECT_UNAUTHORIZED=0 

# Initialize shadcn/ui
npx shadcn init

# Add login component
npx shadcn@latest add login-02

# Add signup component
npx shadcn@latest add signup-02

# Add Dashboard
npx shadcn@latest add dashboard-01

# Video
npm i media-chrome

# Avatar
npm i @rive-app/react-webgl2

# 
npm i ansi-to-react

# Install dependencies
npm install
```



# Spin Up 

# Quick Test
uv run app.main

# Run Server
uv run uvicorn app.main:app --reload --host 0.0.0.0

# Alembic commands
cd backend_fastapi
uv run alembic init alembic
# Go to alembic.ini, and change database URL 
sqlalchemy.url = 
# go to alembic/env.py
from app.core.config import settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

from sqlmodel import SQLModel
from app.models.user import User, AuthIdentity  # import all models
target_metadata = SQLModel.metadata

uv run alembic revision --autogenerate -m "init"
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "Added changed to UserEnum"
# if error with sqlmodel, change  sqlmodel.sql.sqltypes.AutoString to sa.String
uv run alembic upgrade head
uv run alembic current
uv run alembic history
uv run alembic downgrade base
uv run alembic downgrade -1

uv run alembic revision --autogenerate -m "chat"

# Spin up database
docker-compose up -d
cd backend_fastapi
uv run alembic upgrade head

# Spin up backend
uv run uvicorn app.main:app --reload --host 0.0.0.0

# Spin up frontend
cd frontend_nextjs
npm install
npm run dev

# Spin up Sandbox
cd backend_fastapi
uv run modal token new



# Docker 
docker compose build --no-cache
docker compose up -d 
docker compose up --build -d
docker compose up -d postgres


# 
nano .env
nano .env
mkdir secrets
nano "cm-sales-ai-agent-sa.json"


# Docker (sudo in prod)
docker system prune
sudo docker compose build --no-cache
sudo docker compose up -d 
sudo docker compose ps
sudo docker compose logs -f

sudo docker compose down
sudo docker compose up --build -d

sudo docker compose build web
sudo docker compose build --no-cache web
sudo docker compose up -d web



sudo git pull



34.142.149.155:3000
