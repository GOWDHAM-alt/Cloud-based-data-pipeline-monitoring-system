from sqlalchemy import create_engine, text

engine = create_engine(
    "postgresql+psycopg2://monitor:monitor123@localhost:5432/pipeline_monitor"
)

with engine.connect() as conn:
    print(conn.execute(text("SELECT version()")).scalar())