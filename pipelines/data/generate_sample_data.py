"""One-off script: creates data/sample_sales.csv with clean, realistic
rows matching EXPECTED_COLUMNS in pipeline/stages.py.

Run:  python data/generate_sample_data.py
"""

import random
from datetime import datetime, timedelta

import pandas as pd

random.seed(42)
PRODUCTS = ["Widget A", "Widget B", "Gadget C", "Gizmo D", "Doohickey E"]


def generate(n_rows: int = 500) -> pd.DataFrame:
    start = datetime(2026, 9, 1)
    rows = []
    for i in range(n_rows):
        rows.append(
            {
                "order_id": f"ORD-{i:05d}",
                "customer_id": f"CUST-{random.randint(1, 120):04d}",
                "product": random.choice(PRODUCTS),
                "quantity": random.randint(1, 10),
                "price": round(random.uniform(5, 250), 2),
                "order_date": (start + timedelta(minutes=random.randint(0, 60 * 24 * 20))).isoformat(),
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate()
    df.to_csv("data/sample_sales.csv", index=False)
    print(f"Wrote {len(df)} rows to data/sample_sales.csv")
