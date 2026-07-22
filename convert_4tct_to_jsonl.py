import json
from pathlib import Path

DATA_DIR = Path("4TCT/data/saves")
OUT_DIR = Path("data")
OUT_DIR.mkdir(exist_ok=True)

for day_dir in sorted(DATA_DIR.iterdir()):
    if not day_dir.is_dir():
        continue
    date_str = day_dir.name
    thread_dir = day_dir / "threads" / "pol"
    if not thread_dir.exists():
        continue

    out_path = OUT_DIR / f"pol_{date_str}.jsonl"
    count = 0
    with open(out_path, "w") as out:
        for json_file in sorted(thread_dir.glob("*.json")):
            try:
                with open(json_file) as f:
                    thread = json.load(f)
            except Exception:
                continue
            posts = thread if isinstance(thread, list) else thread.get("posts", [])
            for post in posts:
                out.write(json.dumps(post) + "\n")
                count += 1
    print(f"{date_str}: {count} posts -> {out_path}")
