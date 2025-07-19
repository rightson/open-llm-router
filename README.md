# Open-WebUI PostgreSQL Service Manager

A complete service management solution for running Open-WebUI with PostgreSQL database. Includes database initialization, service management, and configuration templates.

## Features

- **Database Management**: Automatic PostgreSQL database and user setup
- **Service Management**: Start/stop Open-WebUI from virtual environment
- **Template System**: SQL templates with environment variable substitution
- **Multi-Platform**: Supports Homebrew PostgreSQL, system PostgreSQL, and Postgres.app
- **Idempotent Operations**: Safe to run multiple times
- **Status Monitoring**: Check database connectivity and service status

## Quick Start

1. **Setup environment:**
```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your database credentials

# Create virtual environment and install Open-WebUI
python3 -m venv venv
source venv/bin/activate
pip install open-webui
```

2. **Initialize database:**
```bash
# Generate and execute SQL initialization
./manage.sh init -x
```

3. **Start Open-WebUI:**
```bash
# Start the service
./manage.sh start
```

## Management Commands

### Database Commands
```bash
# Generate SQL file only
./manage.sh init

# Generate and execute SQL file
./manage.sh init -x
```

### Service Commands
```bash
# Start Open-WebUI service
./manage.sh start

# Check service and database status
./manage.sh status
```

## Configuration

### Environment Variables (.env)

```env
# PostgreSQL configuration for Open-WebUI
OPENWEBUI_DB_USER=openwebui_user
OPENWEBUI_DB_PASSWORD=your_secure_password_here
OPENWEBUI_DB_NAME=openwebui_db

# Database connection settings
DB_HOST=localhost
DB_PORT=5432

# Database URL for Open-WebUI (constructed from above variables)
DATABASE_URL=postgresql://${OPENWEBUI_DB_USER}:${OPENWEBUI_DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${OPENWEBUI_DB_NAME}
```

### Files Structure
```
├── manage.sh              # Main management script
├── pg_init.py             # Database initialization utility
├── init_template.sql      # SQL template with variables
├── .env.example          # Environment configuration template
├── requirements.txt      # Python dependencies
└── venv/                 # Virtual environment (created by user)
```

## Database Setup Details

The initialization creates:
- **Database**: Creates the specified database if it doesn't exist
- **User**: Creates database user with secure password
- **Permissions**: Grants full access to database and schema
- **Extensions**: Installs `uuid-ossp` and `pg_trgm` for Open-WebUI features
- **Ownership**: Sets user as database owner for complete control

## Troubleshooting

### Common Issues

**Environment file missing:**
```bash
❌ .env file not found. Copy .env.example to .env first.
```
Solution: `cp .env.example .env` and edit with your credentials

**PostgreSQL not found:**
```bash
❌ psql not found. Please install PostgreSQL.
```
Solution: Install PostgreSQL via Homebrew: `brew install postgresql`

**Database connection failed:**
```bash
❌ Database connection: FAILED
```
Solution: Ensure PostgreSQL is running: `brew services start postgresql`

**Virtual environment missing:**
```bash
❌ Virtual environment not found.
```
Solution: Create venv and install Open-WebUI:
```bash
python3 -m venv venv
source venv/bin/activate
pip install open-webui
```

### Manual Database Setup

If automatic initialization fails, run manually:
```bash
# Generate SQL file
./manage.sh init

# Execute manually (choose one):
psql -d postgres -f init_openwebui_db.sql
# OR for Homebrew PostgreSQL:
/opt/homebrew/bin/psql -d postgres -f init_openwebui_db.sql
```

## Advanced Usage

### Custom PostgreSQL Setup
The script automatically detects PostgreSQL installations:
- Homebrew PostgreSQL (`/opt/homebrew/bin/psql`)  
- System PostgreSQL (`/usr/bin/psql`, `/usr/local/bin/psql`)
- Postgres.app (`/Applications/Postgres.app/...`)

### Environment Customization
You can override default settings in `.env`:
```env
# Use different host/port
DB_HOST=192.168.1.100
DB_PORT=5433

# Custom database names
OPENWEBUI_DB_NAME=my_openwebui
OPENWEBUI_DB_USER=my_user
```

## License

This service manager is provided as-is for setting up Open-WebUI with PostgreSQL databases.
