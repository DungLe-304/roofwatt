"""Download Vexcel roof images for the top-ranked buildings ahead of the demo, so the app can show them offline.

Usage: python tools/prefetch_images.py [--city Houston] [--type Office] [--top 20]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.tools import getRoofImage, rankBuildings  # noqa: E402


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--city", default="Houston")
	parser.add_argument("--type", default="Office")
	parser.add_argument("--top", type=int, default=20)
	args = parser.parse_args()
	ranking = rankBuildings(args.city, args.type, limit=args.top)
	if "error" in ranking:
		print("ranking failed:", ranking["error"])
		return 1
	failures = 0
	for row in ranking["ranked"]:
		result = getRoofImage(row["buildingId"])
		failures += "error" in result
		print(row["rank"], row["buildingId"], result.get("imagePath") or "ERROR: " + result["error"])
	print(f"{len(ranking['ranked']) - failures}/{len(ranking['ranked'])} images cached")
	return 1 if failures else 0


if __name__ == "__main__":
	sys.exit(main())
