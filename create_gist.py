from github import Github, Auth, InputFileContent
from dotenv import load_dotenv
import os
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

load_dotenv()

token = os.getenv("GITHUB_TOKEN")
g = Github(auth=Auth.Token(token))

# In CI the token belongs to github-actions[bot]; let the workflow override.
username = os.getenv("GITHUB_USER") or g.get_user().login
print(f"Fetching PRs for: {username}")

two_years_ago = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
query = f"author:{username} type:pr created:>={two_years_ago}"

# PRs closed on GitHub but commits were applied directly to main by the maintainer
INDIRECT_MERGES = {
    "osdldbt/dbt5#29",
    "pgmoneta/pgmoneta_mcp#97",
}

EXCLUDE_ORGS = {
    "PalisadoesFoundation",
    "antiwork",
    "asyncapi",
    "code100x",
    "dubinc",
    "json-schema-org",
    "mrhashcoder",
}

# Display order. Orgs not in this list are dropped from the site/gist.
ORG_ORDER = [
    "calcom",
    "ruxailab",
    "kubernetes-sigs",
    "kubernetes",
    "git",
    "lima-vm",
    "kubeescape",
    "kagent-dev",
    "volcano-sh",
    "binodiwal",
    "osdldbt",
    "pgmoneta",
    "anomalyco",
    "InternetHealthReport",
    "middlewarehq",
    "excalidraw",
]

# Manual entries for non-GitHub contributions (e.g. git patches via lore.kernel.org).
# Add more dicts to the "git" list for additional patches.
MANUAL_ORG_ENTRIES = {
    "git": [
        {
            "title": "[PATCH] pack-redundant: fix memory leak when open_pack_index() fails",
            "url": "https://github.com/git/git/commit/7451864bfac0fc7ac829aceecd7f339b80dac732",
            "state": "Merged",
            "created_at": "2026-02-21",
            "merged_at": "2026-02-21",
            "number": None,
            "repo": "git",
        },
    ],
}

print(f"Search query: {query}")

def is_quality_pr(full_pr, pr_issue, org_name):
    merged = full_pr.merged_at is not None
    comments = (pr_issue.comments or 0) + (full_pr.review_comments or 0)

    # All merged calcom PRs — primary contribution org
    if org_name.lower() == "calcom" and merged:
        return True

    # For everything else: merged PRs are good by default
    if merged:
        return True

    # Open or closed: only if there's real engagement (discussion/review happened)
    if comments >= 2:
        return True

    return False

prs_by_org = defaultdict(list)
total_fetched = 0
total_included = 0

print("Fetching PRs...")
prs = g.search_issues(query=query)

for pr in prs:
    total_fetched += 1
    org_name = pr.repository.full_name.split("/")[0]

    if org_name in EXCLUDE_ORGS or org_name == username:
        print(f"  [x] excluded {pr.repository.full_name} #{pr.number}")
        continue

    try:
        repo = g.get_repo(pr.repository.full_name)
        full_pr = repo.get_pull(pr.number)

        pr_key = f"{pr.repository.full_name}#{pr.number}"
        indirect = pr_key in INDIRECT_MERGES

        if indirect or is_quality_pr(full_pr, pr, org_name):
            total_included += 1
            if indirect:
                state = "Merged (indirect)"
                merged_at = pr.closed_at.strftime("%Y-%m-%d") if pr.closed_at else None
            elif full_pr.merged_at:
                state = "Merged"
                merged_at = full_pr.merged_at.strftime("%Y-%m-%d")
            else:
                state = pr.state.capitalize()
                merged_at = None

            prs_by_org[org_name].append({
                "repo": pr.repository.name,
                "full_name": pr.repository.full_name,
                "number": pr.number,
                "title": pr.title,
                "state": state,
                "url": pr.html_url,
                "created_at": pr.created_at.strftime("%Y-%m-%d"),
                "merged_at": merged_at,
                "comments": (pr.comments or 0) + (full_pr.review_comments or 0),
            })
            print(f"  [+] {pr.repository.full_name} #{pr.number} ({prs_by_org[org_name][-1]['state']})")
        else:
            print(f"  [-] skipped {pr.repository.full_name} #{pr.number} (state={pr.state}, comments={pr.comments})")

    except Exception as e:
        print(f"  [!] Error on {pr.repository.full_name} #{pr.number}: {e}")

print(f"\nFetched: {total_fetched} | Included (before manual + filter): {total_included}")

# Merge manual (non-GitHub) entries
for org_name, entries in MANUAL_ORG_ENTRIES.items():
    for entry in entries:
        prs_by_org[org_name].append(entry)
        print(f"  [m] manual {org_name} :: {entry['title']}")

# Whitelist: keep only orgs in ORG_ORDER
dropped = [o for o in prs_by_org if o not in ORG_ORDER]
for o in dropped:
    print(f"  [x] dropped (not in ORG_ORDER) {o} ({len(prs_by_org[o])} PRs)")
prs_by_org = defaultdict(list, {k: v for k, v in prs_by_org.items() if k in ORG_ORDER})

total_included = sum(len(v) for v in prs_by_org.values())
print(f"After manual + whitelist: {total_included} entries across {len(prs_by_org)} orgs")

# ── Build gist markdown ────────────────────────────────────────────────────────

total_merged = sum(
    sum(1 for p in prs if p["state"] in ("Merged", "Merged (indirect)")) for prs in prs_by_org.values()
)
total_open = sum(
    sum(1 for p in prs if p["state"] == "Open") for prs in prs_by_org.values()
)
total_closed = sum(
    sum(1 for p in prs if p["state"] == "Closed") for prs in prs_by_org.values()
)

lines = []
lines.append("# Open Source Contributions (2024–2026)")
lines.append("")
lines.append("> Curated pull requests from the last 2 years across public organizations.")
lines.append("")
lines.append(f"**{total_included} PRs** — {total_merged} Merged · {total_open} Open · {total_closed} Closed")
lines.append("")

# Follow the explicit ORG_ORDER (already filtered to whitelist above)
ordered_orgs = [o for o in ORG_ORDER if o in prs_by_org]

for org in ordered_orgs:
    prs_list = sorted(prs_by_org[org], key=lambda x: x["created_at"], reverse=True)
    merged_count = sum(1 for p in prs_list if p["state"] in ("Merged", "Merged (indirect)"))

    lines.append(f"## {org}  ({len(prs_list)} PRs, {merged_count} merged)")
    lines.append("")
    lines.append("| # | Repository | Title | Status | Date | Merged |")
    lines.append("|---|------------|-------|--------|------|--------|")

    for p in prs_list:
        title = p["title"].replace("|", "\\|")
        merged_at = p["merged_at"] or "—"
        status_badge = {"Merged": "✅ Merged", "Merged (indirect)": "✅ Merged (indirect)", "Open": "🔵 Open", "Closed": "❌ Closed"}.get(p["state"], p["state"])
        lines.append(
            f"| [#{p['number']}]({p['url']}) | {p['repo']} | {title} | {status_badge} | {p['created_at']} | {merged_at} |"
        )

    lines.append("")

gist_content = "\n".join(lines)

# ── Create the gist ────────────────────────────────────────────────────────────
# Gist edits require a PAT with `gist` scope; built-in GITHUB_TOKEN can't do this.
# Set UPDATE_GIST=1 (and use a PAT) when you want to refresh the gist.

GIST_ID = "4dc5097ee57ce159b8d32e050b843be9"

if os.getenv("UPDATE_GIST") == "1":
    print("\nUpdating gist...")
    gist = g.get_gist(GIST_ID)
    gist.edit(
        description="Open Source Contributions — Proof of Work (2024–2026)",
        files={"open-source-contributions.md": InputFileContent(gist_content)},
    )
    print(f"Gist updated: {gist.html_url}")
else:
    print("\nSkipping gist update (set UPDATE_GIST=1 to enable).")

# ── Write docs/data.json for the github.io page ───────────────────────────────

site_orgs = []
for org in ordered_orgs:
    prs_list = sorted(prs_by_org[org], key=lambda x: x["created_at"], reverse=True)
    merged_count = sum(1 for p in prs_list if p["state"] in ("Merged", "Merged (indirect)"))
    site_orgs.append({
        "name": org,
        "merged": merged_count,
        "prs": [
            {
                "number": p["number"],
                "title": p["title"],
                "url": p["url"],
                "state": p["state"],
                "created_at": p["created_at"],
                "merged_at": p["merged_at"],
                "repo": p["repo"],
            }
            for p in prs_list
        ],
    })

site_data = {
    "username": username,
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    "totals": {
        "prs": total_included,
        "merged": total_merged,
        "open": total_open,
        "closed": total_closed,
    },
    "orgs": site_orgs,
}

docs_path = os.path.join(os.path.dirname(__file__), "docs", "data.json")
os.makedirs(os.path.dirname(docs_path), exist_ok=True)
with open(docs_path, "w", encoding="utf-8") as f:
    json.dump(site_data, f, indent=2, ensure_ascii=False)
print(f"Wrote site data: {docs_path}")
