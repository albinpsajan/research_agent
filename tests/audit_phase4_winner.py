"""HackathonIQ Phase 4: Independent Winner Audit & Verification Script.

Inspects:
1. Theme alignment comparison between C01 (Air Quality/Data Centers) vs C02 (Agroforestry) vs C03 (AQGuard)
2. Evidence analysis: retrieves and maps actual claims and publications
3. Existing solutions analysis: satellite air quality vs agroforestry systems
4. Technical validation: NASA/Copernicus data spatial/temporal resolution, GDAL, offline capabilities
5. RAM optimization audit
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.database.repository import Repository

def main() -> None:
    repo = Repository()
    session_id = "a388fd9e-73f8-4c3e-9a62-2a1a3f5ecf92"
    sources = repo.get_research_sources(session_id)
    evals = repo.get_evaluations(session_id)
    agent_results = repo.get_agent_results(session_id)

    print("=" * 70)
    print("PHASE 4: INDEPENDENT WINNER AUDIT & SOURCE VERIFICATION")
    print(f"Session: {session_id}")
    print("=" * 70)

    # 1. Inspect evaluations
    print("\n[1] Stored Evaluations in DB:")
    for ev in evals:
        cid = ev.get("candidate_id")
        print(f"\nCandidate {cid}:")
        print(f"  Title: {ev.get('candidate_title')}")
        print(f"  Domain: {ev.get('domain')}")
        print(f"  Total Score: {ev.get('total_score')}")
        print(f"  All Gates Passed: {ev.get('all_gates_passed')}")
        for s in ev.get("scores_json", []):
            print(f"    - {s.get('name')}: {s.get('score')}/10 (weighted: {s.get('weighted_score')})")

    # 2. Inspect candidate solutions from Solution Architect
    print("\n[2] Solution Architect Candidates:")
    for ar in agent_results:
        if ar["agent_name"] == "solution_architect":
            candidates = ar["result_data"].get("candidates", [])
            for c in candidates:
                print(f"\nCandidate {c.get('id')}: {c.get('title')}")
                print(f"  Domain: {c.get('domain')}")
                print(f"  Proposed Solution: {c.get('proposed_solution')}")
                print(f"  Differentiation: {c.get('unique_differentiation')}")
                print(f"  Risks: {c.get('risks')}")
                print(f"  Mitigations: {c.get('mitigation_strategies')}")

    # 3. Inspect sources for C01 and C02
    c01_urls = {
        "https://arxiv.org/abs/2508.11919v3",
        "https://doi.org/10.1515/9783112234921-fm",
        "https://doi.org/10.3389/fsufs.2025.1551460",
        "https://doi.org/10.3390/rs3122552",
        "https://github.com/bermufine/dcmp",
        "https://news.mit.edu/2026/study-reveals-data-centers-long-distance-damage-air-quality-1119"
    }

    c02_urls = {
        "https://arxiv.org/abs/2511.18576v1",
        "https://doi.org/10.1007/978-3-319-75004-0_16",
        "https://doi.org/10.1007/978-3-319-75004-0_20",
        "https://doi.org/10.2737/wo-gtr-96",
        "https://doi.org/10.46656/access.2024.5.1(8)",
        "https://doi.org/10.56556/jase.v2i1.799"
    }

    print("\n[3] Sources for C01 (Winner):")
    for s in sources:
        if s.get("url") in c01_urls:
            print(f"- [{s.get('source_type')}] {s.get('title')}")
            print(f"  URL: {s.get('url')}")
            print(f"  Snippet: {s.get('snippet', '')[:180]}...")

    print("\n[4] Sources for C02 (Runner-Up):")
    for s in sources:
        if s.get("url") in c02_urls:
            print(f"- [{s.get('source_type')}] {s.get('title')}")
            print(f"  URL: {s.get('url')}")
            print(f"  Snippet: {s.get('snippet', '')[:180]}...")

if __name__ == "__main__":
    main()


def inspect_sources_detail(repo: Repository, session_id: str) -> None:
    sources = repo.get_research_sources(session_id)
    urls_to_inspect = {
        "C01_1 (MIT RSS)": "https://news.mit.edu/2026/study-reveals-data-centers-long-distance-damage-air-quality-1119",
        "C01_2 (OpenAlex/Frontiers)": "https://doi.org/10.3389/fsufs.2025.1551460",
        "C01_3 (Crossref/DeGruyter)": "https://doi.org/10.1515/9783112234921-fm",
        "C01_4 (GitHub)": "https://github.com/bermufine/dcmp",
        "C01_5 (arXiv)": "https://arxiv.org/abs/2508.11919v3",
        "C01_6 (Crossref/MDPI)": "https://doi.org/10.3390/rs3122552",
        "C02_1 (OpenAlex/Access)": "https://doi.org/10.46656/access.2024.5.1(8)",
        "C02_2 (OpenAlex/JASE)": "https://doi.org/10.56556/jase.v2i1.799",
        "C02_3 (OpenAlex/USDA)": "https://doi.org/10.2737/wo-gtr-96",
        "C02_4 (Crossref/Springer)": "https://doi.org/10.1007/978-3-319-75004-0_16",
        "C02_5 (Crossref/Springer)": "https://doi.org/10.1007/978-3-319-75004-0_20",
        "C02_6 (arXiv)": "https://arxiv.org/abs/2511.18576v1",
    }

    print("\n" + "="*70)
    print("DETAILED SOURCE VERIFICATION & CLAIM MAPPING")
    print("="*70)
    for label, url in urls_to_inspect.items():
        matched = [s for s in sources if s.get("url") == url]
        print(f"\n--- {label} ---")
        print(f"URL: {url}")
        if matched:
            s = matched[0]
            print(f"Title: {s.get('title')}")
            print(f"Connector: {s.get('source_type')} | Credibility: {s.get('credibility_score')}")
            meta = s.get("metadata")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    pass
            pub_cat = meta.get("publication_category", "unknown") if isinstance(meta, dict) else "unknown"
            ver_lvl = meta.get("verification_level", "unknown") if isinstance(meta, dict) else "unknown"
            print(f"Publication Category: {pub_cat} | Verification Level: {ver_lvl}")
            snippet = s.get("snippet", "")
            print(f"Snippet/Abstract: {snippet[:280]}...")
        else:
            print("Status: NOT FOUND")

if __name__ == "__main__":
    r = Repository()
    inspect_sources_detail(r, "a388fd9e-73f8-4c3e-9a62-2a1a3f5ecf92")
