import json

with open("nordelia_events.json", "r", encoding="utf-8") as f:
    events = json.load(f)

for cat in events.get("categories", []):
    if cat.get("id") in ("olimpiade-9-cabang", "osn"):
        cat["id"] = "osn"
        cat["name"] = "OSN"
        cat["description"] = "Olimpiade Sains Nasional (9 Cabang Sains & Humaniora)"
        cat["hasSubEvents"] = True
        # Filter out AI from subEvents
        cat["subEvents"] = [s for s in cat.get("subEvents", []) if s.get("id") != "olimpiade-ai"]
        print(f"OSN subEvents count: {len(cat['subEvents'])}")
        for s in cat["subEvents"]:
            print(" -", s["id"], "|", s["name"])

with open("nordelia_events.json", "w", encoding="utf-8") as f:
    json.dump(events, f, indent=2, ensure_ascii=False)

print("nordelia_events.json updated: OSN separated from AI!")
