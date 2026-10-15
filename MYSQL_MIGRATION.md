# FlowPilot MySQL migration

The application now defaults to MySQL 8.0 through SQLAlchemy + PyMySQL.
Explicit SQLite URLs remain supported for isolated unit tests.

1. Install requirements: `python -m pip install -r requirements.txt`.
2. As a MySQL administrator, create a dedicated database and account (replace the password):

```sql
CREATE DATABASE flowpilot CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE USER 'flowpilot'@'127.0.0.1' IDENTIFIED BY 'your_password';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, REFERENCES, INDEX ON flowpilot.* TO 'flowpilot'@'127.0.0.1';
```

3. In the existing .env file, configure MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE,
   MYSQL_USER and MYSQL_PASSWORD as shown in .env.example. Remove an existing
   SQLite DATABASE_URL or replace it with a mysql+pymysql URL.
4. Stop the old application before copying data so that no SQLite writes occur.
   Back up data/smart_appointment.db and any SQLite WAL/SHM files together.
5. With the target database empty, run:
   `python scripts/migrate_sqlite_to_mysql.py --source sqlite:///data/smart_appointment.db`.
   This preserves IDs, JSON and timestamps, validates string limits, checks row
   counts, and copies rows in one transaction. Existing target data causes refusal.
   All ORM tables must exist in the source. No source data is deleted.
6. Restart the application with its existing startup command, then verify workflow
   submission, audit logs, prompt versions and knowledge retrieval. Existing FAISS
   artifacts remain in place; their document IDs are preserved by migration.

The migration command does not create MySQL users or databases. create_all creates
missing tables, but does not alter existing schemas. Use an empty target database.
Avoid running two migrations concurrently. Keep SQLite backups for recovery.

Validation: MySQL DDL compilation plus isolated workflow, prompt, database and
enterprise tool regression tests. A live MySQL migration requires credentials.

Reference: https://docs.sqlalchemy.org/en/14/dialects/mysql.html
