#!/usr/bin/env python3
"""
PostgreSQL Database Initializer for Open-WebUI
Reads SQL template, substitutes environment variables, and generates executable SQL
"""

import os
import sys
from pathlib import Path
from string import Template
from dotenv import load_dotenv
import argparse


class PostgresInitializer:
    def __init__(self, env_file=".env", template_file="init_template.sql"):
        self.env_file = env_file
        self.template_file = template_file
        self.required_vars = [
            "OPENWEBUI_DB_USER",
            "OPENWEBUI_DB_PASSWORD",
            "OPENWEBUI_DB_NAME"
        ]

    def load_environment(self):
        """Load environment variables from .env file"""
        if not Path(self.env_file).exists():
            print(f"Error: {self.env_file} file not found", file=sys.stderr)
            sys.exit(1)

        load_dotenv(self.env_file)

        # Validate required variables
        missing_vars = []
        env_vars = {}

        for var in self.required_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            else:
                env_vars[var] = value

        if missing_vars:
            print(f"Error: Missing required environment variables: {', '.join(missing_vars)}", file=sys.stderr)
            sys.exit(1)

        return env_vars

    def load_template(self):
        """Load SQL template file"""
        if not Path(self.template_file).exists():
            print(f"Error: Template file {self.template_file} not found", file=sys.stderr)
            sys.exit(1)

        with open(self.template_file, 'r', encoding='utf-8') as f:
            return f.read()

    def generate_sql(self, template_content, env_vars):
        """Generate SQL by substituting template variables"""
        try:
            # First escape dollar quotes, then substitute, then restore dollar quotes
            template_content = template_content.replace('\\$\\$', '__DOLLAR_QUOTE__')
            template = Template(template_content)
            sql_content = template.substitute(env_vars)
            sql_content = sql_content.replace('__DOLLAR_QUOTE__', '$$')
            return sql_content
        except KeyError as e:
            print(f"Error: Missing template variable {e}", file=sys.stderr)
            sys.exit(1)

    def write_output(self, sql_content, output_file):
        """Write generated SQL to output file"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(sql_content)

    def run(self, output_file="init_openwebui_db.sql", dry_run=False):
        """Main execution method"""
        # Load environment variables
        env_vars = self.load_environment()

        # Load template
        template_content = self.load_template()

        # Generate SQL
        sql_content = self.generate_sql(template_content, env_vars)

        if dry_run:
            print("Generated SQL:")
            print("-" * 50)
            print(sql_content)
            return

        # Write output
        self.write_output(sql_content, output_file)

        print(f"✓ Generated SQL file: {output_file}")
        print(f"✓ Database user: {env_vars['OPENWEBUI_DB_USER']}")
        print(f"✓ Database name: {env_vars['OPENWEBUI_DB_NAME']}")
        print()
        print("To execute:")
        print(f"  psql -U postgres -f {output_file}")
        print("Or with connection string:")
        print(f"  psql 'postgresql://postgres@localhost:5432/postgres' -f {output_file}")


def create_template_file():
    """Create the SQL template file if it doesn't exist"""
    template_content = """-- PostgreSQL initialization script for Open-WebUI
-- Generated from template with environment variables

-- Create database if it doesn't exist
SELECT 'CREATE DATABASE $OPENWEBUI_DB_NAME'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$OPENWEBUI_DB_NAME')\\gexec

-- Connect to the database
\\c $OPENWEBUI_DB_NAME

-- Create user if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = '$OPENWEBUI_DB_USER') THEN
        CREATE USER $OPENWEBUI_DB_USER WITH PASSWORD '$OPENWEBUI_DB_PASSWORD';
    END IF;
END
$$;

-- Grant necessary permissions for Open-WebUI
GRANT CONNECT ON DATABASE $OPENWEBUI_DB_NAME TO $OPENWEBUI_DB_USER;
GRANT USAGE ON SCHEMA public TO $OPENWEBUI_DB_USER;
GRANT CREATE ON SCHEMA public TO $OPENWEBUI_DB_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $OPENWEBUI_DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $OPENWEBUI_DB_USER;

-- Grant default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $OPENWEBUI_DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $OPENWEBUI_DB_USER;

-- Optional: Create extensions that Open-WebUI might need
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Set user as owner of the database for full control
ALTER DATABASE $OPENWEBUI_DB_NAME OWNER TO $OPENWEBUI_DB_USER;

\\echo 'Database initialization completed successfully!'
\\echo 'User: $OPENWEBUI_DB_USER'
\\echo 'Database: $OPENWEBUI_DB_NAME'
"""

    with open("init_template.sql", 'w', encoding='utf-8') as f:
        f.write(template_content)

    print("✓ Created init_template.sql")


def create_env_example():
    """Create example .env file"""
    env_content = """# PostgreSQL configuration for Open-WebUI
OPENWEBUI_DB_USER=openwebui_user
OPENWEBUI_DB_PASSWORD=your_secure_password_here
OPENWEBUI_DB_NAME=openwebui_db

# Optional: Database connection settings
# DB_HOST=localhost
# DB_PORT=5432
"""

    with open(".env.example", 'w', encoding='utf-8') as f:
        f.write(env_content)

    print("✓ Created .env.example")


def main():
    parser = argparse.ArgumentParser(
        description="Initialize PostgreSQL database for Open-WebUI"
    )
    parser.add_argument(
        "-o", "--output",
        default="init_openwebui_db.sql",
        help="Output SQL file (default: init_openwebui_db.sql)"
    )
    parser.add_argument(
        "-t", "--template",
        default="init_template.sql",
        help="SQL template file (default: init_template.sql)"
    )
    parser.add_argument(
        "-e", "--env-file",
        default=".env",
        help="Environment file (default: .env)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated SQL instead of writing to file"
    )
    parser.add_argument(
        "--init-files",
        action="store_true",
        help="Create template and example files"
    )

    args = parser.parse_args()

    if args.init_files:
        create_template_file()
        create_env_example()
        print("\nNext steps:")
        print("1. Copy .env.example to .env")
        print("2. Edit .env with your database credentials")
        print("3. Run this script again to generate SQL")
        return

    # Initialize and run
    initializer = PostgresInitializer(args.env_file, args.template)
    initializer.run(args.output, args.dry_run)


if __name__ == "__main__":
    main()
